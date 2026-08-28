"""Single owner of agent-event persistence, replay and SSE projection.

**Interrupts are durable thread state, never a blocking await.**  When the
graph pauses for the learner we return, persist the status, and let the pending
question be read back from the checkpoint.  An SSE connection dying — which it
will — costs nothing.

**SSE serves from the persisted event log, not from the live stream.**  The run
writes projections with a monotonic per-session sequence; the endpoint replays
from ``Last-Event-ID``.  A reconnect resumes exactly where it left off.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from ..runtime.execution import (
    execution_timeline_total_tokens,
    replay_execution_timeline,
    require_execution_snapshot,
)
from ..runtime.public_projection import PublicProjector
from ..runtime.trajectory import build_trajectory_projection
from ..store.repositories.agent_tasks import AgentTaskRepository
from ..store.repositories.runtime import RuntimeRepository
from ..store.repositories.work_ledger import WorkLedgerRepository
from ..store.runtime_state import RuntimeStateRepository
from .shared import _event_timestamp, _utc_datetime

logger = logging.getLogger(__name__)

AGENT_EVENT_PAGE_SIZE = 5000
"""Maximum number of durable events loaded per execution snapshot page."""


def _project_public_events(
    projector: PublicProjector,
    events: list[dict[str, Any]],
    *,
    execution_id: str,
) -> list[dict[str, Any]]:
    """Project a V0 persistence buffer into Lingxi Mothership Stream V1 rows.

    The projector sanitizes every payload (denylist + per-tool projection), so
    it may safely consume raw tool events that never reach the V0 rows.  The
    ``seq`` placeholders are rewritten by the repository when the durable task
    sequence is assigned, keeping envelope seq == row sequence.
    """

    rows: list[dict[str, Any]] = []
    for event in events:
        try:
            for envelope in projector.consume(event):
                rows.append(
                    {
                        "kind": f"v1.{envelope['type']}",
                        "agent": "",
                        "payload": envelope,
                        "execution_id": execution_id,
                        "runtime": {},
                        "protocol_version": 1,
                        "turn_id": (envelope.get("stream") or {}).get("turnId") or None,
                        "agent_run_id": (envelope.get("scope") or {}).get("agentRunId")
                        or None,
                        "skill_run_id": (envelope.get("scope") or {}).get("skillRunId")
                        or None,
                    }
                )
        except Exception:  # noqa: BLE001 - projection must never fail the run
            logger.exception("public projection failed for %s", event.get("kind"))
    return rows


def _annotate_truncated_trajectory(
    trajectory: dict[str, Any],
    event_read: Mapping[str, Any],
) -> None:
    """Mark only the uncertain tail as inferred when event paging stops."""

    trajectory["eventLog"] = dict(event_read)
    if not event_read.get("truncated"):
        return
    boundary = _event_timestamp(event_read.get("truncatedAfter"))
    for lane in trajectory.get("lanes") or []:
        if not isinstance(lane, dict):
            continue
        for item in lane.get("items") or []:
            if not isinstance(item, dict) or lane.get("id") == "run":
                continue
            start = _event_timestamp(item.get("startTime"))
            if boundary is not None and start is not None and start < boundary:
                continue
            item["precision"] = "inferred"
            metadata = item.setdefault("metadata", {})
            if isinstance(metadata, dict):
                metadata["eventLogTruncated"] = True


class AgentEventService:
    """Append, replay and project the durable agent-event log."""

    def __init__(
        self,
        *,
        agent_task_repository: AgentTaskRepository,
        runtime_repository: RuntimeRepository,
        work_ledger: WorkLedgerRepository,
        runtime_state: RuntimeStateRepository,
    ) -> None:
        self._agent_tasks = agent_task_repository
        self._runtime = runtime_repository
        self._work_ledger = work_ledger
        self._runtime_state = runtime_state
        self._agent_waiters: dict[str, asyncio.Event] = defaultdict(asyncio.Event)
        # Publishing an interaction outbox row is idempotent across processes;
        # this lock only keeps one process from doing the same work twice.
        self._interaction_publish_locks: defaultdict[str, asyncio.Lock] = defaultdict(
            asyncio.Lock
        )

    # -- live waiters (SSE wake-ups) --------------------------------------

    def waiter(self, task_id: str) -> asyncio.Event:
        return self._agent_waiters[task_id]

    def notify(self, task_id: str) -> None:
        event = self._agent_waiters[task_id]
        event.set()
        event.clear()

    # -- persistence ------------------------------------------------------

    async def append(self, task_id: str, events: list[dict[str, Any]]) -> None:
        """Append rows to the durable log; sequence is assigned by the store."""

        await self._agent_tasks.append_agent_events(task_id, events)

    async def events_after(
        self, task_id: str, learner_id: str, after: int, *, protocol_version: int = 0
    ) -> list[dict[str, Any]]:
        """Replay persisted rows after ``after`` for the SSE endpoint."""

        return await self._agent_tasks.agent_events_after_for_learner(
            task_id, learner_id, after, protocol_version=protocol_version
        )

    async def replay_protocol(self, task_id: str, learner_id: str) -> int:
        """Return the authoritative reader protocol for this retained task."""

        return await self._agent_tasks.agent_event_protocol_for_learner(task_id, learner_id)

    # -- execution snapshots ----------------------------------------------

    async def _agent_events_for_execution_snapshot(
        self, execution_id: str, learner_id: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Read an execution's event log to completion, page by sequence.

        ``agent_events_for_execution`` historically defaulted to 5,000 rows.
        A one-shot call made long runs look complete while silently dropping
        their tail.  Keep paging until the repository reports a short page or
        the durable count is satisfied, and return an explicit read status if
        a legacy repository cannot page or makes no progress.
        """

        expected_count: int | None = None
        count_reader = getattr(self._agent_tasks, "agent_event_count_for_execution", None)
        if callable(count_reader):
            try:
                expected_count = max(0, int(await count_reader(execution_id)))
            except Exception:  # noqa: BLE001 - snapshot remains useful without a count index
                expected_count = None

        records: list[dict[str, Any]] = []
        seen_sequences: set[int] = set()
        cursor = 0
        truncated = False
        legacy_reader = False
        pages = 0

        while True:
            pages += 1
            try:
                page = await self._agent_tasks.agent_events_for_execution(
                    execution_id,
                    learner_id,
                    limit=AGENT_EVENT_PAGE_SIZE,
                    after=cursor,
                )
            except TypeError:
                # Keep compatibility with an older repository implementation,
                # but never treat its 5,000-row result as complete when there
                # is no cursor support for a follow-up page.
                legacy_reader = True
                if cursor:
                    truncated = True
                    break
                page = await self._agent_tasks.agent_events_for_execution(execution_id, learner_id)

            if not isinstance(page, list):
                page = list(page or ())
            if not page:
                if expected_count is not None and len(records) < expected_count:
                    truncated = True
                break

            new_page: list[dict[str, Any]] = []
            page_sequences: list[int] = []
            for raw in page:
                if not isinstance(raw, dict):
                    continue
                item = dict(raw)
                raw_sequence = item.get("sequence")
                try:
                    sequence = int(raw_sequence) if raw_sequence is not None else None
                except (TypeError, ValueError):
                    sequence = None
                if sequence is None:
                    new_page.append(item)
                    continue
                if sequence <= cursor or sequence in seen_sequences:
                    continue
                seen_sequences.add(sequence)
                page_sequences.append(sequence)
                new_page.append(item)

            if not new_page:
                # A repository that ignores ``after`` would otherwise loop
                # forever and silently return only the first page.
                truncated = True
                break

            records.extend(new_page)
            next_cursor = max(page_sequences, default=cursor)
            if expected_count is not None and len(records) >= expected_count:
                break
            if len(page) < AGENT_EVENT_PAGE_SIZE:
                if expected_count is None or len(records) >= expected_count:
                    break
                truncated = True
                break
            if next_cursor <= cursor:
                # Sequence-less full pages cannot be paged safely.  Mark the
                # affected tail inferred instead of claiming a full replay.
                truncated = True
                break
            cursor = next_cursor
            if legacy_reader:
                truncated = True
                break

        complete = not truncated and (
            expected_count is None or len(records) >= expected_count
        )
        if expected_count is not None and len(records) < expected_count:
            truncated = True
            complete = False
        boundary = None
        if records:
            boundary = records[-1].get("ts") or records[-1].get("created_at")
        status = {
            "truncated": bool(truncated),
            "complete": bool(complete),
            "loaded": len(records),
            "expected": expected_count,
            "pages": pages,
            "pageSize": AGENT_EVENT_PAGE_SIZE,
            "truncatedAfter": boundary if truncated else None,
        }
        return records, status

    async def agent_execution_snapshot(self, execution_id: str, learner_id: str) -> dict[str, Any]:
        row = await self._runtime.get_agent_execution(execution_id, learner_id)
        if row is None:
            raise KeyError(f"unknown execution: {execution_id}")
        started = _utc_datetime(row.started_at)
        ended = _utc_datetime(row.ended_at)
        duration = int((ended - started).total_seconds() * 1000) if ended and started else None
        records, event_read = await self._agent_events_for_execution_snapshot(
            execution_id, learner_id
        )
        trace = replay_execution_timeline(
            records,
            execution_id=row.id,
            task_id=row.task_id,
            graph_version=row.graph_version,
            status=row.status,
            started_at=started,
            ended_at=ended,
        )
        trajectory = build_trajectory_projection(
            row,
            records,
            trace,
        )
        _annotate_truncated_trajectory(trajectory, event_read)
        total_tokens = execution_timeline_total_tokens(trace) or None
        return {
            "executionId": row.id,
            "status": row.status,
            "taskId": row.task_id,
            "graphVersion": row.graph_version,
            "schemaVersion": "lingxilearn.execution.v1",
            "snapshot": require_execution_snapshot(
                row.execution_snapshot,
                execution_id=row.id,
                task_id=row.task_id,
                graph_version=row.graph_version,
                status=row.status,
            ),
            "timeline": {
                "schemaVersion": "lingxilearn.timeline.v1",
                "executionId": row.id,
                "spans": trace,
                "totalTokens": total_tokens or 0,
                "waitingForUserMs": int((trace[0] if trace else {}).get("waitingForUserMs") or 0),
            },
            "trajectory": trajectory,
            "eventLog": event_read,
            "executionMetadata": {
                "trigger": row.trigger,
                "startedAt": started.isoformat() if started else None,
                "endedAt": ended.isoformat() if ended else None,
                "totalDurationMs": duration,
                "cost": None,
                "totalTokens": total_tokens,
                "scheduleId": row.schedule_id,
                "scheduledFor": row.scheduled_for.isoformat() if row.scheduled_for else None,
            },
        }

    # -- run / trace reads for observability endpoints ---------------------

    async def get_agent_execution(self, execution_id: str, learner_id: str) -> Any:
        return await self._runtime.get_agent_execution(execution_id, learner_id)

    async def agent_runs_for_task(self, task_id: str) -> list[dict[str, Any]]:
        return await self._runtime.agent_runs_for_task(task_id)

    async def skill_runs_for_task(self, task_id: str) -> list[dict[str, Any]]:
        return await self._runtime.skill_runs_for_task(task_id)

    async def work_dependencies_for_task(self, task_id: str) -> list[dict[str, Any]]:
        return await self._work_ledger.work_dependencies_for_task(task_id)

    async def decisions_for_task(self, task_id: str) -> list[dict[str, Any]]:
        return await self._runtime_state.decisions_for_task(task_id)

    async def evidence_for_task(self, task_id: str) -> list[dict[str, Any]]:
        return await self._runtime_state.evidence_for_task(task_id)

    async def project_learning_record(
        self,
        *,
        learner_id: str,
        record_key: str,
        task_id: str,
        sequence: int,
        kind: str,
        agent: str,
        payload: dict[str, Any],
        runtime: dict[str, Any],
        execution_id: str | None,
    ) -> dict[str, Any]:
        """Project a replayed runtime event into the canonical runtime tables."""

        return await self._runtime.project_runtime_event(
            learner_id=learner_id,
            record_key=record_key,
            task_id=task_id,
            sequence=sequence,
            kind=kind,
            agent=agent,
            payload=payload,
            runtime=runtime,
            execution_id=execution_id,
        )

    # -- interaction outbox (transactional public projection) --------------

    async def publish_interaction_outbox(self, task_id: str) -> int:
        """Publish committed interaction facts into the replay log.

        ``claim_interaction_answer`` commits the answer, the pending→resolved
        transition and this outbox row in one transaction, so the public event
        can never contradict the durable state: either both exist, or the
        pending row is still here to be published.  Publishing is idempotent —
        an event already in the log only marks its row — so a crash between the
        append and the mark cannot duplicate the fact, and any later answer
        retry, drain or restart repairs a publish that never finished
        (issue #18 §10.6).
        """

        published = 0
        # The lock only spares one process from redundant work; correctness
        # comes from the repository claiming the outbox row and writing its
        # events in one transaction, so two replicas cannot both publish.
        async with self._interaction_publish_locks[task_id]:
            rows = [
                row
                for row in await self._work_ledger.pending_outbox(task_id=task_id)
                if row.get("kind") == "interaction.resolved"
            ]
            if not rows:
                return 0
            for row in rows:
                payload = dict(row.get("payload") or {})
                interaction_id = str(payload.get("interaction_id") or "")
                if not interaction_id:
                    await self._work_ledger.mark_outbox_published(str(row["id"]))
                    continue
                execution_id = str(payload.get("execution_id") or "")
                resolved_payload = {
                    "interaction_id": interaction_id,
                    "answers": list(payload.get("answers") or []),
                }
                projector = PublicProjector(
                    chat_id=task_id,
                    execution_id=execution_id,
                    turn_id=str(payload.get("turn_id") or ""),
                    request_id=execution_id,
                )
                v1_rows = _project_public_events(
                    projector,
                    [{"kind": "interaction.resolved", "agent": "", "payload": resolved_payload}],
                    execution_id=execution_id,
                )
                if await self._agent_tasks.publish_outbox_agent_events(
                    outbox_id=str(row["id"]),
                    task_id=task_id,
                    events=[
                        {
                            "kind": "interaction.resolved",
                            "agent": "",
                            "payload": resolved_payload,
                            "execution_id": execution_id or None,
                            "runtime": {},
                        },
                        *v1_rows,
                    ],
                ):
                    published += 1
            if published:
                self.notify(task_id)
        return published
