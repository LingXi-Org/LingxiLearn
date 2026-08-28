"""AgentTask aggregate persistence: tasks, quiz, schedules and the event log."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.errors import AgentTaskCreateConflict
from ..database import Database
from ..models.agent import (
    AgentSchedule,
    AgentScheduleRun,
    AgentTask,
    AgentTaskEvent,
    QuizSubmission,
    TransactionalOutbox,
)
from ..models.base import utcnow


class AgentTaskRepository:
    """AgentTask persistence. Each method opens and closes its own short transaction."""

    def __init__(self, db: Database) -> None:
        self.db = db
        # Event producers include the graph stream and lifecycle handlers. They
        # may append to one task concurrently. Serialise the sequence
        # allocation in-process; PostgreSQL row locking covers separate
        # workers as well.
        self._event_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _event_lock(self, task_id: str) -> asyncio.Lock:
        return self._event_locks[task_id]

    async def create_agent_task(self, **fields: Any) -> None:
        async with self.db.session() as s:
            s.add(AgentTask(**fields))
            try:
                await s.commit()
            except IntegrityError as exc:
                await s.rollback()
                if fields.get("create_idempotency_key"):
                    raise AgentTaskCreateConflict from exc
                raise

    async def get_agent_task_by_create_idempotency_key(
        self, learner_id: str, idempotency_key: str
    ) -> AgentTask | None:
        """Find the durable task created by one learner request key.

        The lookup intentionally includes archived tasks. Reusing a create key
        must never create a new task merely because the original task was later
        deleted from the active list.
        """

        async with self.db.session() as s:
            return await s.scalar(
                select(AgentTask).where(
                    AgentTask.learner_id == learner_id,
                    AgentTask.create_idempotency_key == idempotency_key,
                )
            )

    async def create_schedule_proposal(self, **fields: Any) -> AgentSchedule:
        async with self.db.session() as s:
            learner_id = fields.get("learner_id")
            source_task_id = fields.get("source_task_id")
            prior_scopes = (
                await s.execute(
                    select(AgentSchedule.approval_scope, AgentSchedule.source_task_id).where(
                        AgentSchedule.learner_id == learner_id,
                        AgentSchedule.status == "active",
                        AgentSchedule.approval_scope.in_(("always_allow", "allow_chat")),
                    )
                )
            ).all()
            inherited_scope = next(
                (
                    scope
                    for scope, task_id in prior_scopes
                    if scope == "always_allow"
                    or (scope == "allow_chat" and task_id == source_task_id)
                ),
                None,
            )
            if inherited_scope and not (fields.get("inputs_snapshot") or {}).get(
                "revokesScheduleId"
            ):
                fields["status"] = "active"
                fields["approval_scope"] = inherited_scope
                fields["approved_at"] = utcnow()
            row = AgentSchedule(**fields)
            s.add(row)
            await s.commit()
            await s.refresh(row)
            return row

    async def decide_schedule_permission(
        self, *, proposal_id: str, learner_id: str, decision: str
    ) -> dict[str, Any] | None:
        """Apply the first tool-permission decision exactly once."""

        if decision not in {"allow", "allow_chat", "always_allow", "skip"}:
            raise ValueError("invalid_schedule_permission_decision")

        async with self.db.session() as s:
            stmt = select(AgentSchedule).where(
                AgentSchedule.proposal_id == proposal_id,
                AgentSchedule.learner_id == learner_id,
            )
            if self.db.engine.url.get_backend_name() == "postgresql":
                stmt = stmt.with_for_update()
            row = await s.scalar(stmt)
            if row is None:
                return None
            if row.status not in {"proposed", "pending"}:
                return {
                    "proposal_id": proposal_id,
                    "status": row.status,
                    "applied": False,
                    "scope": row.approval_scope,
                    "source_task_id": row.source_task_id,
                }
            row.approval_scope = decision
            row.approved_at = utcnow()
            if decision == "skip":
                row.status = "rejected"
            else:
                row.status = "active"
                revoked_id = (row.inputs_snapshot or {}).get("revokesScheduleId")
                if revoked_id:
                    row.status = "revoked"
                    target = await s.get(AgentSchedule, revoked_id)
                    if target is not None and target.learner_id == learner_id:
                        target.status = "revoked"
                        target.revoked_at = utcnow()
                        target.updated_at = utcnow()
            row.updated_at = utcnow()
            await s.commit()
            return {
                "proposal_id": proposal_id,
                "status": row.status,
                "applied": True,
                "scope": decision,
                "source_task_id": row.source_task_id,
            }

    async def get_schedule(self, *, schedule_id: str, learner_id: str) -> AgentSchedule | None:
        async with self.db.session() as s:
            return await s.scalar(
                select(AgentSchedule).where(
                    AgentSchedule.id == schedule_id, AgentSchedule.learner_id == learner_id
                )
            )

    async def revoke_schedule_proposal(self, *, proposal_id: str, learner_id: str) -> bool:
        async with self.db.session() as s:
            row = await s.scalar(
                select(AgentSchedule).where(
                    AgentSchedule.proposal_id == proposal_id, AgentSchedule.learner_id == learner_id
                )
            )
            if row is None:
                return False
            row.status = "revoked"
            row.revoked_at = utcnow()
            row.updated_at = utcnow()
            await s.commit()
            return True

    async def claim_due_schedule(
        self, *, owner: str, now: datetime | None = None, lease_seconds: int = 60
    ) -> dict[str, Any] | None:
        """Claim one due schedule; PostgreSQL uses SKIP LOCKED."""

        moment = now or datetime.now(UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        async with self.db.session() as s:
            stmt = (
                select(AgentSchedule)
                .where(
                    AgentSchedule.status == "active",
                    AgentSchedule.next_run_at.is_not(None),
                    AgentSchedule.next_run_at <= moment,
                    (AgentSchedule.lease_until.is_(None) | (AgentSchedule.lease_until < moment)),
                )
                .order_by(AgentSchedule.next_run_at)
                .limit(1)
            )
            if self.db.engine.url.get_backend_name() == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)
            row = await s.scalar(stmt)
            if row is None:
                return None
            scheduled_for = row.next_run_at
            row.lease_owner = owner
            row.lease_until = moment + timedelta(seconds=lease_seconds)
            run = await s.scalar(
                select(AgentScheduleRun).where(
                    AgentScheduleRun.schedule_id == row.id,
                    AgentScheduleRun.scheduled_for == scheduled_for,
                )
            )
            if run is not None:
                # A process can die after claiming a slot. Reuse that one
                # durable claim once its lease expires instead of creating a
                # duplicate trigger. A started slot is already handed off;
                # never launch it a second time.
                if run.status == "started":
                    row.lease_owner = None
                    row.lease_until = None
                    await s.commit()
                    return None
                run.status = "claimed"
                run.updated_at = utcnow()
            else:
                run = AgentScheduleRun(
                    id=f"schedule-run-{uuid4().hex}",
                    schedule_id=row.id,
                    scheduled_for=scheduled_for,
                    status="claimed",
                )
                s.add(run)
                try:
                    await s.flush()
                except IntegrityError:
                    # If two pollers race the same unique slot, the loser simply
                    # yields this tick and the winner owns the lease.
                    await s.rollback()
                    return None
            await s.commit()
            return {
                "schedule_id": row.id,
                "run_id": run.id,
                "scheduled_for": scheduled_for,
                "prompt": row.prompt,
                "learner_id": row.learner_id,
                "resources": row.resources_snapshot or [],
                "graph_version": row.graph_version,
                "timezone": row.timezone,
                "cron": row.cron,
            }

    async def finish_schedule_claim(
        self,
        *,
        run_id: str,
        schedule_id: str,
        scheduled_for: datetime,
        execution_id: str,
        next_run_at: datetime | None,
    ) -> None:
        async with self.db.session() as s:
            run = await s.get(AgentScheduleRun, run_id)
            schedule = await s.get(AgentSchedule, schedule_id)
            if run is not None:
                run.execution_id = execution_id
                run.status = "started"
                run.updated_at = utcnow()
            if schedule is not None:
                schedule.last_run_at = scheduled_for
                schedule.next_run_at = next_run_at
                schedule.lease_owner = None
                schedule.lease_until = None
                schedule.updated_at = utcnow()
            await s.commit()

    async def get_agent_task(self, task_id: str) -> AgentTask | None:
        async with self.db.session() as s:
            return await s.get(AgentTask, task_id)

    async def get_agent_task_for_learner(self, task_id: str, learner_id: str) -> AgentTask | None:
        async with self.db.session() as s:
            return await s.scalar(
                select(AgentTask).where(
                    AgentTask.id == task_id,
                    AgentTask.learner_id == learner_id,
                )
            )

    async def set_agent_task_status(
        self, task_id: str, status: str, error: str = "", *, thread_status: str | None = None
    ) -> None:
        async with self.db.session() as s:
            row = await s.get(AgentTask, task_id)
            if row is None:
                return
            row.status = status
            row.error = error
            if thread_status is not None:
                row.thread_status = thread_status
            row.updated_at = utcnow()
            await s.commit()

    async def set_agent_thread_status(self, task_id: str, thread_status: str) -> None:
        async with self.db.session() as s:
            row = await s.get(AgentTask, task_id)
            if row is None:
                return
            row.thread_status = thread_status
            row.updated_at = utcnow()
            await s.commit()

    async def claim_agent_task(
        self,
        task_id: str,
        learner_id: str,
        *,
        execution_id: str | None = None,
        reclaim_running: bool = False,
    ) -> AgentTask | None:
        """Atomically claim a runnable task for one process.

        Task execution is launched from an asyncio background task, so the
        database is the only coordination point shared by API replicas and a
        restarted process.  A conditional update prevents startup recovery,
        retries, and the original request from running the same task twice.

        A task is claimable when its thread is open and it is not currently
        running or cancelled. A running task is never claimable.
        """

        async with self.db.session() as s:
            claimable_status = AgentTask.status != "cancelled"
            if not reclaim_running:
                claimable_status = AgentTask.status.notin_(("running", "cancelled"))
            values: dict[str, Any] = {"status": "running", "updated_at": utcnow()}
            if execution_id is not None:
                values["current_execution_id"] = execution_id
            result = await s.execute(
                update(AgentTask)
                .where(
                    AgentTask.id == task_id,
                    AgentTask.learner_id == learner_id,
                    AgentTask.thread_status.in_(("open", "awaiting_user", "running")),
                    claimable_status,
                )
                .values(**values)
            )
            if int(getattr(result, "rowcount", 0) or 0) != 1:
                return None
            row = await s.get(AgentTask, task_id)
            await s.commit()
            return row

    async def queued_agent_tasks(self) -> list[dict[str, str]]:
        """Return tasks left queued by a process restart for startup recovery."""

        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(AgentTask.id, AgentTask.learner_id, AgentTask.prompt)
                    .where(AgentTask.status == "queued", AgentTask.deleted_at.is_(None))
                    .order_by(AgentTask.created_at)
                )
            ).all()
            return [
                {"id": str(task_id), "learner_id": str(learner_id), "prompt": str(prompt)}
                for task_id, learner_id, prompt in rows
            ]

    async def update_agent_task_output(
        self, task_id: str, agent: str, value: dict[str, Any]
    ) -> None:
        async with self.db.session() as s:
            row = await s.get(AgentTask, task_id)
            if row is None:
                return
            if agent == "intent":
                row.intent = value
            elif agent == "lecture_hook":
                row.lecture_result = value
            elif agent == "interactive_lecture_deck":
                row.deck_result = value
            elif agent == "quiz_generator":
                row.quiz_result = value
            elif agent == "adaptive_pedagogy":
                row.adaptive_result = value
            elif agent == "handoff":
                row.handoff_result = value
            elif agent == "user_message":
                row.user_messages = [*(row.user_messages or []), value][-100:]
            elif agent in {"learning_companion", "learner_interview", "answer_user", "probe_user"}:
                row.user_messages = [
                    *(row.user_messages or []),
                    {"agent": agent, **value},
                ][-100:]
            elif agent == "visual_explainer":
                row.visual_result = value
            else:
                raise ValueError(f"unknown agent output: {agent}")
            row.updated_at = utcnow()
            await s.commit()

    async def get_quiz_submission(self, task_id: str) -> QuizSubmission | None:
        async with self.db.session() as s:
            return await s.scalar(select(QuizSubmission).where(QuizSubmission.task_id == task_id))

    async def create_quiz_submission(
        self,
        *,
        task_id: str,
        submission_id: str,
        answers: dict[str, Any],
        per_question: list[dict[str, Any]],
        total_score: float,
        total_points: int,
        handoff_reason: str = "quiz_completed",
    ) -> dict[str, Any]:
        """Create the only submission for a task, with retry-safe semantics."""

        async with self.db.session() as s:
            existing = await s.scalar(
                select(QuizSubmission).where(QuizSubmission.task_id == task_id)
            )
            if existing is not None:
                if existing.submission_id == submission_id:
                    return _quiz_submission_dict(existing)
                raise ValueError("already_submitted")
            row = QuizSubmission(
                task_id=task_id,
                submission_id=submission_id,
                answers=answers,
                per_question=per_question,
                total_score=float(total_score),
                total_points=int(total_points),
                handoff_reason=handoff_reason,
            )

            s.add(row)
            try:
                await s.commit()
            except Exception:
                await s.rollback()
                existing = await s.scalar(
                    select(QuizSubmission).where(QuizSubmission.task_id == task_id)
                )
                if existing is not None:
                    if existing.submission_id == submission_id:
                        return _quiz_submission_dict(existing)
                    raise ValueError("already_submitted") from None
                raise
            await s.refresh(row)
            return _quiz_submission_dict(row)

    async def update_agent_task_metadata(
        self,
        task_id: str,
        learner_id: str,
        *,
        title: str | None = None,
        is_pinned: bool | None = None,
        is_unread: bool | None = None,
        resources: list[dict[str, Any]] | None = None,
    ) -> AgentTask | None:
        async with self.db.session() as s:
            row = await s.scalar(
                select(AgentTask).where(AgentTask.id == task_id, AgentTask.learner_id == learner_id)
            )
            if row is None:
                return None
            if title is not None:
                row.title = title
            if is_pinned is not None:
                row.is_pinned = is_pinned
            if is_unread is not None:
                row.is_unread = is_unread
            if resources is not None:
                row.resources = resources
            row.updated_at = utcnow()
            await s.commit()
            await s.refresh(row)
            return row

    async def set_agent_task_deleted(
        self, task_id: str, learner_id: str, deleted: bool
    ) -> AgentTask | None:
        async with self.db.session() as s:
            row = await s.scalar(
                select(AgentTask).where(AgentTask.id == task_id, AgentTask.learner_id == learner_id)
            )
            if row is None:
                return None
            row.deleted_at = utcnow() if deleted else None
            row.updated_at = utcnow()
            await s.commit()
            await s.refresh(row)
            return row

    async def list_agent_tasks(
        self, learner_id: str, scope: str = "active"
    ) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            deleted_filter = (
                AgentTask.deleted_at.is_not(None)
                if scope == "archived"
                else AgentTask.deleted_at.is_(None)
            )
            rows = (
                await s.execute(
                    select(AgentTask)
                    .where(AgentTask.learner_id == learner_id, deleted_filter)
                    .order_by(
                        AgentTask.is_pinned.desc(),
                        AgentTask.updated_at.desc(),
                        AgentTask.created_at.desc(),
                    )
                )
            ).scalars()
            return [
                {
                    "id": row.id,
                    "prompt": row.prompt,
                    "title": row.title or "",
                    "status": row.status,
                    "intent": row.intent or {},
                    "is_pinned": bool(row.is_pinned),
                    "is_unread": bool(row.is_unread),
                    "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
                    "resources": row.resources or [],
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in rows
            ]

    @staticmethod
    async def _write_agent_event_rows(
        s: AsyncSession, task: AgentTask, task_id: str, events: list[dict[str, Any]]
    ) -> int:
        """Allocate sequences and write event rows inside an open transaction.

        Shared by the ordinary append and the outbox publisher.
        """

        highest = (
            await s.execute(
                select(func.max(AgentTaskEvent.sequence)).where(AgentTaskEvent.task_id == task_id)
            )
        ).scalar() or 0
        for offset, event in enumerate(events, start=1):
            sequence = highest + offset
            runtime = event.get("runtime") or (event.get("payload") or {}).get("runtime") or {}
            payload = event.get("payload") or {}
            if str(event.get("kind") or "").startswith("v1."):
                # Keep the public envelope sequence equal to its durable row.
                if isinstance(payload, dict):
                    payload = dict(payload)
                    payload["seq"] = sequence
                    stream = payload.get("stream")
                    if isinstance(stream, dict) and not stream.get("executionId"):
                        stream["executionId"] = event.get("execution_id")
                        payload["stream"] = stream
            s.add(
                AgentTaskEvent(
                    task_id=task_id,
                    sequence=sequence,
                    kind=str(event.get("kind", "")),
                    agent=str(event.get("agent", "")),
                    payload=payload,
                    execution_id=event.get("execution_id"),
                    runtime=runtime,
                    turn_id=event.get("turn_id"),
                    agent_run_id=event.get("agent_run_id"),
                    skill_run_id=event.get("skill_run_id"),
                )
            )
        return highest + len(events)

    async def append_agent_events(self, task_id: str, events: list[dict[str, Any]]) -> int:
        if not events:
            async with self.db.session() as s:
                highest = (
                    await s.execute(
                        select(func.max(AgentTaskEvent.sequence)).where(
                            AgentTaskEvent.task_id == task_id
                        )
                    )
                ).scalar()
                return int(highest or 0)
        task_record = await self.get_agent_task(task_id)
        if task_record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        async with self._event_lock(task_id):
            async with self.db.session() as s:
                # FOR UPDATE makes the max(sequence) allocation atomic across
                # API/worker processes on PostgreSQL; the per-task asyncio lock
                # also serialises local writers.
                task = await s.get(AgentTask, task_id, with_for_update=True)
                if task is None:
                    raise KeyError(f"unknown agent task: {task_id}")
                total = await self._write_agent_event_rows(s, task, task_id, events)
                await s.commit()
                return total

    async def publish_outbox_agent_events(
        self, *, outbox_id: str, task_id: str, events: list[dict[str, Any]]
    ) -> bool:
        """Claim one outbox row and write its events in a single transaction.

        Publishing is exactly-once across processes because the claim and the
        append commit together: a second publisher's conditional update matches
        no row and it writes nothing, and a publisher that dies mid-transaction
        leaves the row unclaimed for the next one.  No "does this event already
        exist?" read is involved — that check-then-act is precisely what two
        replicas can both pass (issue #18 §10.6).
        """

        task_record = await self.get_agent_task(task_id)
        if task_record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        async with self._event_lock(task_id):
            async with self.db.session() as s:
                claimed = await s.execute(
                    update(TransactionalOutbox)
                    .where(
                        TransactionalOutbox.id == outbox_id,
                        TransactionalOutbox.published_at.is_(None),
                    )
                    .values(published_at=utcnow())
                )
                if not int(getattr(claimed, "rowcount", 0) or 0):
                    await s.rollback()
                    return False
                task = await s.get(AgentTask, task_id, with_for_update=True)
                if task is None:
                    await s.rollback()
                    raise KeyError(f"unknown agent task: {task_id}")
                await self._write_agent_event_rows(s, task, task_id, events)
                await s.commit()
                return True

    async def agent_events_after(
        self, task_id: str, after: int = 0, limit: int = 500
    ) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(AgentTaskEvent)
                    .where(
                        AgentTaskEvent.task_id == task_id,
                        AgentTaskEvent.sequence > after,
                    )
                    .order_by(AgentTaskEvent.sequence)
                    .limit(limit)
                )
            ).scalars()
            return [_agent_event_dict(r) for r in rows]

    async def agent_event_count_for_execution(self, execution_id: str) -> int:
        async with self.db.session() as s:
            count = await s.scalar(
                select(func.count())
                .select_from(AgentTaskEvent)
                .where(AgentTaskEvent.execution_id == execution_id)
            )
            return int(count or 0)

    async def agent_events_for_execution(
        self,
        execution_id: str,
        learner_id: str,
        limit: int = 5000,
        after: int = 0,
    ) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                (
                    await s.execute(
                        select(AgentTaskEvent)
                        .join(AgentTask, AgentTask.id == AgentTaskEvent.task_id)
                        .where(
                            AgentTaskEvent.execution_id == execution_id,
                            AgentTask.learner_id == learner_id,
                            AgentTaskEvent.sequence > max(0, int(after or 0)),
                        )
                        .order_by(AgentTaskEvent.sequence)
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            return [_agent_event_dict(row) for row in rows]

    async def agent_events_after_for_learner(
        self,
        task_id: str,
        learner_id: str,
        after: int = 0,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            stmt = (
                select(AgentTaskEvent)
                .join(AgentTask, AgentTask.id == AgentTaskEvent.task_id)
                .where(
                    AgentTaskEvent.task_id == task_id,
                    AgentTask.learner_id == learner_id,
                    AgentTaskEvent.sequence > after,
                    AgentTaskEvent.kind.like("v1.%"),
                )
            )
            rows = (await s.execute(stmt.order_by(AgentTaskEvent.sequence).limit(limit))).scalars()
            return [_agent_event_dict(r) for r in rows]


def _quiz_submission_dict(row: QuizSubmission) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "submission_id": row.submission_id,
        "answers": row.answers or {},
        "per_question": row.per_question or [],
        "total_score": row.total_score,
        "total_points": row.total_points,
        "handoff_reason": row.handoff_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _agent_event_dict(row: AgentTaskEvent) -> dict[str, Any]:
    runtime = row.runtime or {}
    return {
        "sequence": row.sequence,
        "kind": row.kind,
        "agent": row.agent,
        "payload": row.payload,
        "execution_id": row.execution_id or runtime.get("execution_id"),
        "run_id": runtime.get("run_id"),
        "step": runtime.get("step"),
        "node": runtime.get("node"),
        "task_id": runtime.get("task_id"),
        "namespace": runtime.get("namespace"),
        "checkpoint_id": runtime.get("checkpoint_id"),
        "span_id": runtime.get("span_id"),
        "runtime": runtime,
        "turn_id": row.turn_id,
        "agent_run_id": row.agent_run_id,
        "skill_run_id": row.skill_run_id,
        "ts": row.created_at.isoformat() if row.created_at else None,
    }
