"""Current runtime adapter: drives the LingxiGraph loop for agent tasks.

Implements :class:`~lingxilearn.application.runtime_port.RuntimeInputPort`.
This module owns the graph-run lifecycle — claim, execution row, event
translation, turn bookkeeping — while durable event persistence goes through
:class:`~lingxilearn.application.agent_events.AgentEventService` and artifact
projection through
:class:`~lingxilearn.application.artifacts.ArtifactResourceService`.

Two decisions carry most of the weight.

**Interrupts are durable thread state, never a blocking await.**  When the
graph pauses for the learner we return, persist the status, and let the pending
question be read back from the checkpoint.

**SSE serves from the persisted event log, not from the live stream.**  The run
writes projections with a monotonic per-session sequence; the endpoint replays
from ``Last-Event-ID``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from lingxigraph import Command, EventKind, GraphCancelledError
from lingxigraph.errors import (
    BudgetExceededError,
    GraphTimeoutError,
)

from ..agents.model_runtime import EVENT_CHANNEL
from ..config import Settings
from ..runtime.loop import GRAPH_NAME as LOOP_GRAPH_NAME
from ..runtime.loop import GRAPH_VERSION as LOOP_GRAPH_VERSION
from ..runtime.loop import initial_state as initial_loop_state
from ..runtime.public_projection import PublicProjector
from ..runtime.sim_semantics import SimRunProjector
from ..state.session_state import RuntimeStatus, new_budget
from ..store.repositories.agent_tasks import AgentTaskRepository
from ..store.repositories.runtime import RuntimeRepository
from ..store.repositories.work_ledger import WorkLedgerRepository
from ..store.runtime_state import RuntimeStateRepository
from .agent_events import AgentEventService, _project_public_events
from .artifacts import ArtifactResourceService
from .graph_factory import RuntimeGraphFactory
from .shared import BackgroundTasks, _json_safe

logger = logging.getLogger(__name__)

AGENT_FLUSH_EVERY = 4
"""Batch size for persisting projections mid-run — small enough to feel live."""


class _ProviderEventRuntime:
    """Small event bridge used by isolated provider contract tests."""

    context = None
    cancellation = None

    def __init__(self, agent: str) -> None:
        self.agent = agent
        self.events: list[dict[str, Any]] = []

    def emit(self, _channel: str, event: dict[str, Any]) -> None:
        kind = str(event.get("type") or "")
        if not kind:
            return
        payload = _json_safe({key: value for key, value in event.items() if key != "type"})
        agent = str(payload.pop("agent", self.agent))
        self.events.append({"kind": kind, "agent": agent, "payload": payload})


_AGENT_FORCE_FLUSH = frozenset(
    {
        "agent.started",
        "agent.completed",
        "agent.failed",
        "agent.status",
        "agent.output",
        "agent.output.delta",
        "model.started",
        "model.completed",
        "model.failed",
        "tool.call.delta",
        "tool.result",
        "artifact.ready",
        "node.held",
        "node.revising",
        "delivery.queued",
        "delivery.unlocked",
        "task.cancelled",
        "run.paused",
        "run.resumed",
        "run.ended",
        "run.failed",
        "run.timed_out",
        "run.budget_exceeded",
        "node.appeared",
        "plan.created",
        "plan.replanned",
    }
)

_LOOP_NODES = frozenset(
    {
        "interpret_goal",
        "orchestrate",
        "dispatch",
        "observe",
        "update_state",
        "evaluate_goal",
        "await_user",
    }
)
"""The runtime loop's own nodes. Which *agent* ran is not derived from these.

Providers announce themselves on the event channel, so attribution follows the
run rather than a table of agent names that would have to be edited every time a
capability is added.
"""


def _agent_task_status(values: dict[str, Any], *, interrupted: bool) -> str:
    """Project the loop's runtime status onto the public task status."""

    return {
        str(RuntimeStatus.COMPLETED): "completed",
        str(RuntimeStatus.FAILED): "failed",
        str(RuntimeStatus.WAITING_FOR_USER): "awaiting_user",
    }.get(
        str(values.get("runtime_status") or ""),
        "awaiting_user" if interrupted else "partial",
    )


def _trace_agent(metadata: Any, default_agent: str = "coordinator") -> str:
    """Attribute a streamed message to whichever agent is currently running.

    LingxiGraph namespaces child-agent events under the agent's own name, so the
    namespace is the attribution; there is no list of known agents to check
    against.
    """

    if not isinstance(metadata, dict):
        return default_agent
    namespace = metadata.get("namespace") or ()
    if isinstance(namespace, (list, tuple)):
        for value in reversed(namespace):
            name = str(value)
            if name and name not in _LOOP_NODES:
                return name
    for key in ("agent", "name"):
        value = metadata.get(key)
        if value and str(value) not in _LOOP_NODES:
            return str(value)
    return default_agent


def _message_trace_events(value: Any, default_agent: str) -> list[dict[str, Any]]:
    """Convert one native LingxiGraph message envelope into Agent Task events."""
    if not isinstance(value, (tuple, list)) or not value:
        return []
    message = value[0]
    metadata = value[1] if len(value) > 1 else {}
    agent = _trace_agent(metadata, default_agent)
    events: list[dict[str, Any]] = []
    message_type = str(getattr(message, "type", "") or "")
    content = getattr(message, "content", "")
    if message_type == "tool":
        events.append(
            {
                "kind": "tool.result",
                "agent": agent,
                "payload": {
                    "tool_call_id": getattr(message, "tool_call_id", None),
                    "name": getattr(message, "name", None),
                    "content": str(content or ""),
                    "status": getattr(message, "status", None),
                    "additional_kwargs": _json_safe(
                        getattr(message, "additional_kwargs", {}) or {}
                    ),
                    "response_metadata": _json_safe(
                        getattr(message, "response_metadata", {}) or {}
                    ),
                },
            }
        )
        return events
    additional = getattr(message, "additional_kwargs", {}) or {}
    reasoning = ""
    if isinstance(additional, dict):
        for key in ("reasoning_content", "reasoning", "thinking"):
            candidate = additional.get(key)
            if candidate:
                reasoning = str(candidate)
                break
    if reasoning and not additional.get("_reasoning_replay"):
        events.append(
            {
                "kind": "reasoning.delta",
                "agent": agent,
                "payload": {
                    "delta": reasoning,
                    "debug": _json_safe(additional),
                    "response_metadata": _json_safe(
                        getattr(message, "response_metadata", {}) or {}
                    ),
                },
            }
        )
    if content:
        events.append(
            {"kind": "assistant.delta", "agent": agent, "payload": {"delta": str(content)}}
        )
    tool_chunks = getattr(message, "tool_call_chunks", ()) or ()
    if tool_chunks:
        events.append(
            {
                "kind": "tool.call.delta",
                "agent": agent,
                "payload": {
                    "chunks": [
                        {
                            "name": getattr(chunk, "name", None),
                            "args": getattr(chunk, "args", ""),
                            "id": getattr(chunk, "id", None),
                            "index": getattr(chunk, "index", 0),
                        }
                        for chunk in tool_chunks
                    ],
                    "debug": _json_safe(additional),
                    "response_metadata": _json_safe(
                        getattr(message, "response_metadata", {}) or {}
                    ),
                },
            }
        )
    usage = getattr(message, "usage", {}) or {}
    if usage:
        events.append({"kind": "model.usage", "agent": agent, "payload": {"usage": dict(usage)}})
    for event in events:
        event["runtime"] = {
            "run_id": _json_safe(metadata.get("run_id")) if isinstance(metadata, dict) else None,
            "step": _json_safe(metadata.get("step")) if isinstance(metadata, dict) else None,
            "node": _json_safe(metadata.get("node")) if isinstance(metadata, dict) else None,
            "task_id": _json_safe(metadata.get("task_id")) if isinstance(metadata, dict) else None,
            "namespace": _json_safe(metadata.get("namespace"))
            if isinstance(metadata, dict)
            else None,
            "checkpoint_id": _json_safe(metadata.get("checkpoint_id"))
            if isinstance(metadata, dict)
            else None,
            "span_id": _json_safe(metadata.get("span_id")) if isinstance(metadata, dict) else None,
        }
        logger.debug(
            "agent trace task=%s agent=%s kind=%s payload=%s",
            metadata.get("task_id", ""),
            agent,
            event["kind"],
            event["payload"],
        )
    return events


def _safe_agent_error(exc: BaseException, settings: Settings) -> str:
    """Expose actionable workflow errors without leaking credentials."""

    detail = str(exc).strip() or type(exc).__name__
    secret = settings.agent_api_key.get_secret_value()
    if secret:
        detail = detail.replace(secret, "[redacted]")
    return detail[-4000:]


class LingxiGraphRuntimeAdapter:
    """Drive agent-task turns on the LingxiGraph loop.

    A returned coroutine is only the fast path: the command ledger already
    holds every input durably, so a process death is recovered at startup.
    """

    def __init__(
        self,
        *,
        agent_task_repository: AgentTaskRepository,
        work_ledger: WorkLedgerRepository,
        runtime_repository: RuntimeRepository,
        runtime_state: RuntimeStateRepository,
        settings: Settings,
        artifact_service: ArtifactResourceService,
        event_service: AgentEventService,
        graph_factory: RuntimeGraphFactory,
        tasks: BackgroundTasks,
        board_locks: defaultdict[str, asyncio.Lock],
    ) -> None:
        self._agent_tasks = agent_task_repository
        self._work_ledger = work_ledger
        self._runtime = runtime_repository
        self._runtime_state = runtime_state
        self._settings = settings
        self._artifacts = artifact_service
        self._events = event_service
        self._graph_factory = graph_factory
        self._tasks = tasks
        self._board_locks = board_locks
        self._hold_sweep_locks = board_locks
        self._hold_sweep_pending: set[str] = set()
        self._agent_slots = asyncio.Semaphore(max(1, settings.agent_concurrency))
        self._agent_runners: defaultdict[str, set[asyncio.Task[Any]]] = defaultdict(set)
        self._active_steering: dict[str, tuple[Any, str, str, str]] = {}
        self._pending_steering: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        self._conversation_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._conversation_queue: defaultdict[str, asyncio.Queue[dict[str, Any]]] = defaultdict(
            asyncio.Queue
        )

    # -- RuntimeInputPort ---------------------------------------------------

    @property
    def agent_model(self) -> dict[str, Any] | None:
        return self._graph_factory.agent_model

    @agent_model.setter
    def agent_model(self, value: dict[str, Any] | None) -> None:
        self._graph_factory.agent_model = value

    @property
    def model_configured(self) -> bool:
        return self._graph_factory.agent_model is not None

    def start_turn(
        self,
        task_id: str,
        learner_id: str,
        prompt: str,
        *,
        schedule_id: str | None = None,
        scheduled_for: datetime | None = None,
    ) -> None:
        self._tasks.spawn(
            self._drive_agent_task(
                task_id,
                learner_id,
                prompt,
                schedule_id=schedule_id,
                scheduled_for=scheduled_for,
            )
        )

    def resume_turn(self, task_id: str, learner_id: str, resume: dict[str, Any]) -> None:
        self._tasks.spawn(self._drive_agent_task(task_id, learner_id, "", resume=resume))

    def enqueue_conversation_input(
        self, task_id: str, learner_id: str, item: dict[str, Any]
    ) -> None:
        self._conversation_queue[task_id].put_nowait(item)
        self._tasks.spawn(self._serve_conversation(task_id, learner_id))

    async def submit_running_input(
        self, task_id: str, learner_id: str, item: dict[str, Any]
    ) -> None:
        """Steer the live LingxiGraph run without starting a second turn."""

        active = self._active_steering.get(task_id)
        if active is None:
            self._pending_steering[task_id].append(dict(item))
            return
        graph, run_id, execution_id, turn_id = active
        event = graph.steer(
            run_id,
            kind="user_message",
            payload=dict(item),
            metadata={
                "task_id": task_id,
                "thread_id": task_id,
                "turn_id": str(item.get("turn_id") or turn_id),
                "learner_id": learner_id,
                "execution_id": execution_id,
            },
            idempotency_key=str(item.get("idempotency_key") or item.get("command_id") or "")
            or None,
        )
        await self._events.append(
            task_id,
            [
                {
                    "kind": "steer.accepted",
                    "agent": "coordinator",
                    "execution_id": execution_id,
                    "turn_id": str(item.get("turn_id") or turn_id) or None,
                    "payload": {
                        "steering_event_id": event.id,
                        "sequence": event.sequence,
                        "kind": event.kind,
                        "status": "accepted",
                    },
                }
            ],
        )
        self._events.notify(task_id)

    def schedule_interaction_drain(self, task_id: str, learner_id: str) -> None:
        self._tasks.spawn(self._drain_interaction_continuations(task_id, learner_id))

    async def cancel_run(self, task_id: str) -> None:
        runners = [
            runner
            for runner in self._agent_runners.get(task_id, set())
            if runner is not asyncio.current_task() and not runner.done()
        ]
        for runner in runners:
            runner.cancel()
        if runners:
            await asyncio.gather(*runners, return_exceptions=True)

    async def recover_pending(self) -> None:
        """Replay durable queued work after a process restart."""

        # Agent tasks are accepted before their graph starts.  Recover tasks
        # left in that durable queue when the API process is restarted; the
        # atomic claim in _run_agent_task makes this safe across replicas.
        for task in await self._agent_tasks.queued_agent_tasks():
            self._tasks.spawn(
                self._drive_agent_task(task["id"], task["learner_id"], task["prompt"])
            )
        await self.recover_interaction_continuations()

    async def recover_interaction_continuations(self) -> int:
        """Replay answered-but-unresumed interactions after a restart."""

        recovered = 0
        # A publish that never finished is repaired first: the interaction is
        # durably resolved, so the replay log must say so before the recap is
        # rebuilt (issue #18 §10.6).
        for row in await self._work_ledger.pending_outbox():
            if row.get("kind") == "interaction.resolved":
                await self._events.publish_interaction_outbox(str(row["task_id"]))
        for command in await self._runtime.pending_interaction_continuations():
            payload = dict(command.get("payload") or {})
            interaction_id = str(payload.get("interaction_id") or "")
            if not interaction_id:
                continue
            self._tasks.spawn(
                self._drive_agent_task(
                    str(command["task_id"]),
                    str(command.get("learner_id") or ""),
                    "",
                    resume={
                        "kind": "interaction_answer",
                        "interaction_id": interaction_id,
                        "answers": list(payload.get("answers") or []),
                    },
                )
            )
            recovered += 1
        return recovered

    # -- run engine ----------------------------------------------------------

    async def _drive_agent_task(
        self,
        task_id: str,
        learner_id: str,
        prompt: str,
        *,
        resume: dict[str, Any] | None = None,
        schedule_id: str | None = None,
        scheduled_for: datetime | None = None,
    ) -> bool:
        """Run one turn; returns whether *this* call owned the run.

        False means another worker won the durable ``claim_agent_task`` (or the
        thread was gone), so this caller executed nothing and must not act as
        if it had — in particular it must not consume the command ledger entry
        the winner is working from (issue #18 §10.4).
        """

        # Keep the public task launcher cheap: queued tasks wait here instead
        # of all retaining graph state and provider response buffers at once.
        runner = asyncio.current_task()
        if runner is not None:
            self._agent_runners[task_id].add(runner)
        try:
            async with self._agent_slots:
                return await self._run_agent_task(
                    task_id,
                    learner_id,
                    prompt,
                    resume=resume,
                    schedule_id=schedule_id,
                    scheduled_for=scheduled_for,
                )
        finally:
            if runner is not None:
                runners = self._agent_runners.get(task_id)
                if runners is not None:
                    runners.discard(runner)
                    if not runners:
                        self._agent_runners.pop(task_id, None)

    async def _run_agent_task(
        self,
        task_id: str,
        learner_id: str,
        prompt: str,
        *,
        resume: dict[str, Any] | None = None,
        schedule_id: str | None = None,
        scheduled_for: datetime | None = None,
    ) -> bool:
        """Execute one turn; returns whether this call claimed the thread."""

        self._hold_sweep_pending.discard(task_id)
        if not self.model_configured:
            await self._agent_tasks.set_agent_task_status(
                task_id, "failed", "DS_API_KEY is not configured"
            )
            self._events.notify(task_id)
            return False
        record = await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
        if record is None:
            return False
        if resume is not None and resume.get("message"):
            await self._agent_tasks.update_agent_task_output(
                task_id,
                "user_message",
                {
                    "message": str(resume.get("message")),
                    "kind": str(resume.get("kind") or "chat"),
                    "answers": _json_safe(resume.get("answers"))
                    if resume.get("answers") is not None
                    else None,
                    "attachments": _json_safe(resume.get("attachments") or []),
                },
            )
        latest = await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
        if latest is None or latest.status == "cancelled":
            return False
        claimed = await self._agent_tasks.claim_agent_task(task_id, learner_id)
        if claimed is None:
            # Another API process (or the request that originally created the
            # task) already owns this run.  The caller must treat this as "not
            # mine": the winner owns the command ledger entry too.
            return False
        record = claimed
        # Freeze the command set belonging to this turn.  Inputs arriving
        # while the graph is running belong to a later turn and must remain
        # pending for the next coordinator pass.
        pending_commands = await self._work_ledger.pending_commands(task_id)
        turn_command_ids = {str(command["id"]) for command in pending_commands}
        # Messages accepted while a task was still queued survive a process
        # restart in the command ledger. Rehydrate them into the native
        # Steering channel when this execution starts. The first message that
        # exactly matches the new-turn prompt is the turn input, not steering.
        deferred_steering: list[dict[str, Any]] = []
        primary_prompt_seen = False
        for command in pending_commands:
            if command.get("kind") != "message":
                continue
            payload = dict(command.get("payload") or {})
            if not primary_prompt_seen and str(payload.get("message") or "") == str(prompt or ""):
                primary_prompt_seen = True
                continue
            deferred_steering.append(
                {
                    **payload,
                    "command_id": str(command.get("id") or ""),
                    "turn_id": str(command.get("turn_id") or ""),
                    "idempotency_key": str(command.get("idempotency_key") or ""),
                }
            )
        steering_command_ids = {str(item.get("command_id") or "") for item in deferred_steering}
        execution_id = f"exec-{uuid.uuid4().hex}"
        try:
            # Bind this invocation to the canonical turn it executes.  A
            # resume keeps the turn that paused; new messages claim the
            # latest pending turn (issue #18 §4.3).
            current_turn = await self._work_ledger.latest_turn(task_id)
            turn_id = str(current_turn["id"]) if current_turn else ""
            turn_index = int(current_turn["turn_index"]) if current_turn else 0
            # An interaction answer resumes the paused execution inside the
            # same turn; link the new execution back to it (issue #18 §4.3).
            resumes_execution_id: str | None = None
            if resume is not None and resume.get("kind") == "interaction_answer":
                prior = await self._runtime.get_interaction(
                    str(resume.get("interaction_id") or ""), task_id=task_id
                )
                resumes_execution_id = str((prior or {}).get("execution_id") or "") or None
            await self._runtime.create_agent_execution(
                execution_id=execution_id,
                task_id=task_id,
                learner_id=learner_id,
                turn_id=turn_id or None,
                resumes_execution_id=resumes_execution_id,
                graph_version=record.graph_version,
                trigger="resume"
                if resume is not None
                else ("schedule" if schedule_id else "agent-task"),
                schedule_id=schedule_id,
                scheduled_for=scheduled_for,
            )
            projector = SimRunProjector(
                execution_id=execution_id,
                task_id=task_id,
                graph_version=record.graph_version,
            )
            public_projector = PublicProjector(
                chat_id=task_id,
                execution_id=execution_id,
                turn_id=turn_id,
                request_id=execution_id,
            )
            start_runtime = {
                "execution_id": execution_id,
                "task_id": task_id,
                "graph_version": record.graph_version,
            }
            start_events: list[dict[str, Any]] = [
                {
                    "kind": "run.started",
                    "agent": "coordinator",
                    "execution_id": execution_id,
                    "runtime": start_runtime,
                    "payload": {"status": "running", "runtime": start_runtime},
                }
            ]
            if resume is not None:
                start_events.append(
                    {
                        "kind": "run.resumed",
                        "agent": "coordinator",
                        "execution_id": execution_id,
                        "runtime": start_runtime,
                        "payload": {"status": "running", "runtime": start_runtime},
                    }
                )
            turn_started = public_projector.turn_event(
                "resumed" if resume is not None else "started",
                turn_id=turn_id or task_id,
                turn_index=turn_index,
                user_text="" if resume is not None else str(prompt or ""),
            )
            if turn_started is not None:
                start_events.append(
                    {
                        "kind": "v1.turn",
                        "agent": "",
                        "payload": turn_started,
                        "execution_id": execution_id,
                        "runtime": {},
                        "protocol_version": 1,
                        "turn_id": turn_id or None,
                    }
                )
            # The thread is executing again; the legacy per-run status keeps
            # its historical meaning for existing readers (issue #18 §4.1).
            await self._agent_tasks.set_agent_thread_status(task_id, "running")
            await self._events.append(task_id, start_events)
        except Exception as exc:  # noqa: BLE001 - startup failures are user-visible
            logger.exception("agent task failed before graph start: %s", task_id)
            detail = _safe_agent_error(exc, self._settings)
            await self._agent_tasks.set_agent_task_status(
                task_id, "failed", f"启动失败：{type(exc).__name__}: {detail}"
            )
            await self._agent_tasks.set_agent_thread_status(task_id, "open")
            await self._events.append(
                task_id,
                [
                    {
                        "kind": "task.failed",
                        "agent": "coordinator",
                        "payload": {
                            "error_type": type(exc).__name__,
                            "message": f"启动失败：{type(exc).__name__}: {detail}",
                        },
                    }
                ],
            )
            self._events.notify(task_id)
            return True

        response_composed = False

        async def persist_buffer(events: list[dict[str, Any]]) -> None:
            nonlocal response_composed
            if not events:
                return
            # The graph adapter can inspect provider-native messages for local
            # control flow, but this is the sole public persistence boundary.
            # Raw reasoning and raw tool payloads/arguments stay private: they
            # are dropped from the V0 rows and only their sanitized V1 shape
            # (safeParams/safeResult, issue #18 §3.4/§9.3) is persisted.
            private_kinds = {"reasoning.delta", "tool.call.delta", "tool.result"}
            # An artifact that passed validation projects to a read-only
            # WorkspaceFile immediately, so the resource identity exists the
            # moment the learner sees "产物完成" (issue #18 §12.2).
            for item in events:
                if item.get("kind") != "artifact.ready":
                    continue
                artifact = str((item.get("payload") or {}).get("artifact") or "")
                descriptor = await self._artifacts.project_task_artifact_resource(
                    learner_id, task_id, artifact
                )
                if descriptor is not None:
                    payload = dict(item.get("payload") or {})
                    payload["workspace_file_id"] = descriptor["id"]
                    payload["workspace_file_title"] = descriptor["title"]
                    item["payload"] = payload
            v1_rows = _project_public_events(
                public_projector,
                events,
                execution_id=execution_id,
            )
            public_events = [item for item in events if item.get("kind") not in private_kinds]
            composed: list[dict[str, Any]] = []
            for item in public_events:
                if item.get("kind") == "agent.output":
                    stream_id = str((item.get("payload") or {}).get("stream_id") or "")
                    if stream_id.endswith(":opening-companion"):
                        composed.append(item)
                        continue
                    if response_composed:
                        continue
                    response_composed = True
                composed.append(item)
            public_events = composed
            current_workflow_state = projector.snapshot()["workflowState"]
            for item in public_events:
                item.setdefault("execution_id", execution_id)
                item.setdefault("runtime", (item.get("payload") or {}).get("runtime") or {})
                item.setdefault("workflowState", current_workflow_state)
                item["payload"] = {
                    **(item.get("payload") or {}),
                    "workflowState": current_workflow_state,
                }
            # Dual projection: V1 rows carry the canonical identity the next
            # frontend stage consumes; V0 keeps serving today's UI unchanged.
            await self._events.append(task_id, [*public_events, *v1_rows])
            if not public_events and not v1_rows:
                return
            await self._runtime.update_agent_execution(
                execution_id,
                workflow_state=current_workflow_state,
                trace_spans=projector.snapshot()["traceSpans"],
                event_count=await self._agent_tasks.agent_event_count_for_execution(execution_id),
            )
            self._events.notify(task_id)

        async def persist_result(agent: str, value: dict[str, Any]) -> None:
            await self._agent_tasks.update_agent_task_output(task_id, agent, value)
            self._events.notify(task_id)

        async def emit_turn_terminal(status: str) -> None:
            """Close the turn on the V1 stream; the thread itself stays open."""

            envelope = public_projector.turn_event(
                status, turn_id=turn_id or task_id, turn_index=turn_index
            )
            if envelope is None:
                return
            try:
                await self._events.append(
                    task_id,
                    [
                        {
                            "kind": "v1.turn",
                            "agent": "",
                            "payload": envelope,
                            "execution_id": execution_id,
                            "runtime": {},
                            "protocol_version": 1,
                            "turn_id": turn_id or None,
                        }
                    ],
                )
                self._events.notify(task_id)
            except Exception:  # noqa: BLE001 - turn bookkeeping must not fail the run
                logger.exception("failed to emit turn terminal event: %s", task_id)

        # One runtime for every task. There is no second topology to choose
        # between, and no graph_version branch to pick it with.
        config = {
            "configurable": {
                "thread_id": task_id,
                "checkpoint_ns": f"{LOOP_GRAPH_NAME}@{LOOP_GRAPH_VERSION}",
            },
            "recursion_limit": 80,
        }
        buffer: list[dict[str, Any]] = []
        current_agent = "coordinator"
        graph: Any | None = None
        flush_lock = asyncio.Lock()

        async def flush_buffer() -> None:
            """Persist buffered learner events immediately and in sequence.

            Runtime callbacks execute inside graph nodes while native stream
            events are consumed by the outer iterator. Both paths append to
            this buffer, so every flush is serialized through one lock.
            """

            async with flush_lock:
                if not buffer:
                    return
                pending = list(buffer)
                buffer.clear()
                await persist_buffer(pending)

        def emit_runtime_event(kind: str, payload: dict[str, Any]) -> None:
            agent = str(payload.pop("agent", "orchestrator"))
            projected = projector.consume_runtime_event(kind, payload, agent=agent)
            projected["execution_id"] = execution_id
            buffer.append(projected)
            # deps.emit is synchronous and bypasses the native CUSTOM stream.
            # Force-flush learner output and AgentRun identity now instead of
            # waiting for a model/node boundary to make the outer loop wake up.
            if kind in _AGENT_FORCE_FLUSH:
                self._tasks.spawn(flush_buffer())

        try:
            session_state = await self._runtime_state.ensure_session_state(
                learner_id=learner_id,
                task_id=task_id,
                budget=new_budget(),
            )
            prior_results, prior_artifacts = self._artifacts.restore_task_outputs(record)
            graph = self._graph_factory.loop_for(
                learner_id=learner_id,
                task_id=task_id,
                execution_id=execution_id,
                turn_id=turn_id,
                emit=emit_runtime_event,
                confirmed_actions=frozenset(
                    (session_state.get("plan") or {}).get("confirmed_actions") or ()
                ),
                prior_results=prior_results,
                prior_artifacts=prior_artifacts,
            )
            self._active_steering[task_id] = (graph, execution_id, execution_id, turn_id)
            steering_by_identity: dict[str, dict[str, Any]] = {}
            for pending in [*deferred_steering, *self._pending_steering.pop(task_id, [])]:
                identity = str(
                    pending.get("idempotency_key") or pending.get("command_id") or uuid.uuid4().hex
                )
                steering_by_identity.setdefault(identity, pending)
            for pending in steering_by_identity.values():
                await self.submit_running_input(task_id, learner_id, pending)
            graph_input: Any = (
                Command(resume=resume)
                if resume is not None
                else initial_loop_state(
                    learner_id=learner_id,
                    task_id=task_id,
                    utterance=prompt,
                    budget=session_state.get("budget") or new_budget(),
                )
            )
            async for streamed in graph.astream(
                graph_input,
                config,
                stream_mode=("events", "messages"),
                run_id=execution_id,
                context={
                    "learner_id": learner_id,
                    "locale": "zh-CN",
                    "resource_refs": list(record.resources or []),
                },
            ):
                current_record = await self._agent_tasks.get_agent_task_for_learner(
                    task_id, learner_id
                )
                if current_record is None:
                    return True
                if current_record.status == "cancelled":
                    await flush_buffer()
                    snapshot = projector.snapshot()
                    await self._runtime.update_agent_execution(
                        execution_id,
                        status="cancelled",
                        workflow_state=snapshot["workflowState"],
                        trace_spans=snapshot["traceSpans"],
                        ended=True,
                    )
                    self._events.notify(task_id)
                    return True
                mode, event = streamed
                force_flush = False
                if mode == "messages":
                    message_events = _message_trace_events(event, current_agent)
                    buffer.extend(message_events)
                    for item in message_events:
                        item["execution_id"] = execution_id
                    if len(buffer) >= AGENT_FLUSH_EVERY:
                        await flush_buffer()
                    continue
                node = str(event.node or "")
                if node and node not in _LOOP_NODES:
                    # A child agent's node: attribute to it until it completes.
                    if event.kind is EventKind.NODE_STARTED:
                        current_agent = node
                    elif event.kind is EventKind.NODE_COMPLETED:
                        current_agent = "coordinator"
                projected = projector.consume(event, agent=current_agent)
                if event.kind is EventKind.CUSTOM:
                    data = dict(event.data or {})
                    if data.get("channel") == EVENT_CHANNEL:
                        value = data.get("value") or {}
                        if isinstance(value, dict) and value.get("type"):
                            event_type = str(value["type"])
                            buffer.append(
                                {
                                    "kind": event_type,
                                    "agent": str(value.get("agent") or "coordinator"),
                                    "payload": {
                                        str(k): _json_safe(v)
                                        for k, v in value.items()
                                        if k not in {"type", "agent"}
                                    },
                                    "execution_id": execution_id,
                                    "runtime": projected.get("runtime") or {},
                                }
                            )
                            force_flush = event_type in _AGENT_FORCE_FLUSH
                    else:
                        projected["agent"] = current_agent
                        buffer.append(projected)
                elif projected.get("kind"):
                    projected["agent"] = projected.get("agent") or current_agent
                    buffer.append(projected)
                if force_flush or len(buffer) >= AGENT_FLUSH_EVERY:
                    await flush_buffer()
            active = self._active_steering.get(task_id)
            if active is not None and active[1] == execution_id:
                self._active_steering.pop(task_id, None)
        except Exception as exc:  # noqa: BLE001 - task failures are user-visible state
            active = self._active_steering.get(task_id)
            if active is not None and active[1] == execution_id:
                self._active_steering.pop(task_id, None)
            logger.exception("agent task failed: %s", task_id)
            detail = _safe_agent_error(exc, self._settings)
            recovered_intro = await self._artifacts.recover_lesson_intro_draft(task_id)
            if recovered_intro is not None:
                buffer.append(
                    {
                        "kind": "artifact.recovered",
                        "agent": "lecture_hook",
                        "payload": {
                            "artifact": "lesson-intro",
                            "relative_path": recovered_intro["relative_path"],
                            "message": "课程引入生成被中断，已从已写入草稿恢复可用页面。",
                        },
                    }
                )
            recovered_deck = await self._artifacts.recover_deck_draft(task_id)
            if recovered_deck is not None:
                buffer.append(
                    {
                        "kind": "artifact.recovered",
                        "agent": "interactive_lecture_deck",
                        "payload": {
                            "artifact": "lecture-deck",
                            "relative_path": f"{task_id}/lecture-deck/dist/lecture.html",
                            "message": "课件生成被中断或校验失败，已从已写入源文件恢复可用发布物。",
                            "validation": recovered_deck["validation"],
                        },
                    }
                )
            failure_status = (
                "timed_out"
                if isinstance(exc, GraphTimeoutError)
                else "budget_exceeded"
                if isinstance(exc, BudgetExceededError)
                else "cancelled"
                if isinstance(exc, GraphCancelledError)
                else "failed"
            )
            failure_kind = {
                "timed_out": "run.timed_out",
                "budget_exceeded": "run.budget_exceeded",
                "cancelled": "run.cancelled",
                "failed": "run.failed",
            }[failure_status]
            buffer.append(
                {
                    "kind": failure_kind,
                    "agent": "coordinator",
                    "payload": {
                        "status": failure_status,
                        "error_type": type(exc).__name__,
                        "message": f"运行失败：{type(exc).__name__}: {detail}",
                    },
                }
            )
            await flush_buffer()
            # A failed turn closes only the turn; the thread returns to open
            # so the learner can keep talking (issue #18 §4.1).
            await self._agent_tasks.set_agent_task_status(
                task_id, failure_status, f"运行失败：{type(exc).__name__}: {detail}"
            )
            await self._agent_tasks.set_agent_thread_status(
                task_id, "cancelled" if failure_status == "cancelled" else "open"
            )
            await emit_turn_terminal("cancelled" if failure_status == "cancelled" else "failed")
            snapshot = projector.snapshot()
            workflow_state = dict(snapshot["workflowState"])
            metadata = dict(workflow_state.get("metadata") or {})
            metadata.update({"terminal": True, "status": failure_status, "paused": False})
            workflow_state["metadata"] = metadata
            await self._runtime.update_agent_execution(
                execution_id,
                status=failure_status,
                error=f"运行失败：{type(exc).__name__}: {detail}",
                workflow_state=workflow_state,
                trace_spans=snapshot["traceSpans"],
                ended=True,
            )
            self._events.notify(task_id)
            # A failed turn still releases the thread; an answer accepted while
            # it was running must not wait for a restart (issue #18 §10.4).
            self._tasks.spawn(self._drain_interaction_continuations(task_id, learner_id))
            return True

        # Join any in-flight forced flush before terminal state is read.
        await flush_buffer()
        if graph is None:  # pragma: no cover - the try/except above returns on failure
            return True
        state = await graph.aget_state(config)
        values = dict(getattr(state, "values", None) or {})
        status = _agent_task_status(values, interrupted=bool(getattr(state, "interrupts", None)))
        errors = [str(item) for item in values.get("errors") or []]
        if status == "failed" and values.get("finished_reason"):
            errors.append(str(values["finished_reason"]))
        thread_status = {"awaiting_user": "awaiting_user", "cancelled": "cancelled"}.get(
            status, "open"
        )
        await self._agent_tasks.set_agent_task_status(
            task_id,
            "handed_off" if status == "handed_off" else status,
            "; ".join(errors),
            thread_status=thread_status,
        )
        turn = await self._work_ledger.latest_turn(task_id)
        if turn is not None:
            turn_status = {
                "awaiting_user": "awaiting_user",
                "completed": "delivered",
                "handed_off": "delivered",
                "failed": "failed",
                "cancelled": "cancelled",
            }.get(status, "active")
            await self._work_ledger.update_turn(
                turn_id=str(turn["id"]),
                status=turn_status,
                phase="evaluating" if turn_status == "active" else "delivered",
                goal_status="satisfied" if status in {"completed", "handed_off"} else "open",
            )
        await emit_turn_terminal(
            {"awaiting_user": "awaiting_user", "cancelled": "cancelled"}.get(
                status, "failed" if status == "failed" else "delivered"
            )
        )
        # A command remains pending while the turn is executing. It becomes
        # consumed only after the graph has produced a durable outcome, so a
        # crash cannot silently drop an input.
        if status not in {"failed", "partial"}:
            remaining_commands = await self._work_ledger.pending_commands(task_id)
            transferred = [
                command
                for command in remaining_commands
                if command.get("kind") == "message"
                and (
                    str(command["id"]) in steering_command_ids
                    or str(command["id"]) not in turn_command_ids
                )
            ]
            if transferred:
                await self._events.append(
                    task_id,
                    [
                        {
                            "kind": "steer.superseded",
                            "agent": "coordinator",
                            "execution_id": execution_id,
                            "turn_id": str(command.get("turn_id") or "") or None,
                            "payload": {
                                "command_id": str(command["id"]),
                                "status": "superseded",
                                "disposition": "transfer_pending",
                            },
                        }
                        for command in transferred
                    ],
                )
            for command in remaining_commands:
                if str(command["id"]) not in turn_command_ids:
                    continue
                if str(command["id"]) in steering_command_ids:
                    continue
                await self._work_ledger.consume_command(str(command["id"]))
        await self._runtime.update_agent_execution(
            execution_id,
            status="awaiting_user"
            if status == "awaiting_user"
            else ("completed" if status in {"completed", "handed_off"} else status),
            workflow_state=projector.snapshot()["workflowState"],
            trace_spans=projector.snapshot()["traceSpans"],
            error="; ".join(errors),
            ended=status not in {"awaiting_user", "partial"},
        )
        # Publish generated HTML artifacts as native read-only workspace files
        # while retaining the original task-audit files and URLs.
        try:
            await self._artifacts.project_agent_artifacts(learner_id, task_id)
        except Exception:  # noqa: BLE001 - projection must not fail the task
            logger.exception("failed to project task artifacts: %s", task_id)
        self._events.notify(task_id)
        # The thread is claimable again: pick up any interaction answer that
        # was accepted while this execution still held it (issue #18 §10.4).
        self._tasks.spawn(self._drain_interaction_continuations(task_id, learner_id))
        return True

    async def _sweep_holds(self, task_id: str, learner_id: str) -> None:
        async with self._hold_sweep_locks[task_id]:
            if task_id in self._hold_sweep_pending:
                return
            record = await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
            if record is None or record.status != "awaiting_user":
                return
            board = await self._runtime_state.get_board(task_id)
            if not (board.get("holds") or {}):
                return
            self._hold_sweep_pending.add(task_id)
        self._tasks.spawn(
            self._drive_agent_task(task_id, learner_id, "", resume={"kind": "holds_ready"})
        )

    async def _serve_conversation(self, task_id: str, learner_id: str) -> None:
        """Drain queued learner inputs through the normal turn coordinator.

        A queued message waits while a graph turn is executing, then either
        resumes the paused checkpoint (``awaiting_user``) or starts a new turn
        on the same long-lived thread.  A finished turn never ends the thread
        (issue #18 §4.1) — only a cancelled thread stops draining the queue.
        """

        async with self._conversation_locks[task_id]:
            queue = self._conversation_queue[task_id]
            while not queue.empty():
                item = await queue.get()
                while True:
                    record = await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
                    if record is None:
                        return
                    if str(getattr(record, "thread_status", "") or "open") == "cancelled":
                        return
                    if record.status in {"queued", "running"}:
                        await asyncio.sleep(0.2)
                        continue
                    break
                if record.status == "awaiting_user":
                    await self._drive_agent_task(
                        task_id,
                        learner_id,
                        "",
                        resume={
                            "message": str(item.get("message") or ""),
                            "kind": "chat",
                            "attachments": item.get("attachments") or [],
                        },
                    )
                else:
                    # New turn on the same thread: fresh graph invocation with
                    # the message as the utterance, reusing the checkpoint
                    # history under the same thread_id.
                    await self._drive_agent_task(
                        task_id,
                        learner_id,
                        str(item.get("message") or ""),
                        resume=None,
                    )

    async def _drain_interaction_continuations(self, task_id: str, learner_id: str) -> int:
        """Resume answered interactions whose fast-path resume could not claim.

        An answer can be accepted while the previous execution is still
        running: the continuation command is durable at that point, but
        ``claim_agent_task`` refuses a running thread, so that first resume
        attempt returns without doing anything.  The finishing execution calls
        this the moment it becomes claimable again, so a learner who answers
        quickly is not left waiting for a process restart (issue #18 §10.4).

        The command ledger is the coordination point: each pass re-reads the
        pending commands, and a resume that runs to a durable outcome consumes
        its own command, so a concurrent drain cannot replay it.
        """

        drained = 0
        async with self._conversation_locks[task_id]:
            while True:
                pending = [
                    command
                    for command in await self._work_ledger.pending_commands(task_id)
                    if command.get("kind") == "interaction_answer"
                ]
                if not pending:
                    return drained
                record = await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
                if record is None:
                    return drained
                if str(getattr(record, "thread_status", "") or "open") == "cancelled":
                    return drained
                if record.status in {"queued", "running"}:
                    # A live turn owns the thread; whoever finishes it drains.
                    return drained
                payload = dict(pending[0].get("payload") or {})
                interaction_id = str(payload.get("interaction_id") or "")
                if not interaction_id:
                    await self._work_ledger.consume_command(str(pending[0]["id"]))
                    continue
                owned = await self._drive_agent_task(
                    task_id,
                    learner_id,
                    "",
                    resume={
                        "kind": "interaction_answer",
                        "interaction_id": interaction_id,
                        "answers": list(payload.get("answers") or []),
                    },
                )
                if not owned:
                    # Another worker (the answer's own fast path, or a drain in
                    # another replica) won the durable claim and is executing
                    # this continuation.  Consuming its command here would let
                    # a crash on the winning side lose the answer entirely, so
                    # ownership — not arrival — decides who may consume.
                    return drained
                drained += 1
                # This call owned the run, so it may close the ledger entry:
                # a resume that reached a durable outcome already consumed it,
                # and consuming here covers the failed turn so one continuation
                # is never replayed in a loop.
                await self._work_ledger.consume_command(str(pending[0]["id"]))
