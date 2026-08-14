"""Engine, session factory and the repository.

One rule worth stating because breaking it is the classic scaling mistake:
**never hold a database session open across a graph run.**  Resolve what you
need, release the connection, then stream.  A pool of 10 gated on model latency
caps you at 10 concurrent learners for no reason.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import Settings
from .knowledge_graph import GraphRevisionConflict, graph_snapshot_dict, validate_result

__all__ = ["Database", "Repository", "GraphRevisionConflict"]
from .models import (
    AgentExecution,
    AgentSchedule,
    AgentScheduleRun,
    AgentTask,
    AgentTaskEvent,
    AgentTaskSidecar,
    Base,
    KnowledgeGraph,
    KnowledgeGraphEdge,
    KnowledgeGraphEvent,
    KnowledgeGraphLearnerOverlay,
    KnowledgeGraphNode,
    Learner,
    Mastery,
    QuizSubmission,
    ReportRecord,
    RunEvent,
    Session,
    utcnow,
)


class Database:
    def __init__(self, settings: Settings) -> None:
        url = settings.resolved_database_url
        kwargs: dict[str, Any] = {"pool_pre_ping": True}
        if url.startswith("postgresql"):
            kwargs.update(pool_size=10, max_overflow=20)
        else:
            kwargs["connect_args"] = {"timeout": 30}
        self.engine = create_async_engine(url, **kwargs)

        if url.startswith("sqlite"):
            # A run streams events from a background task while the API reads
            # status and SSE replays the log. Rollback-journal SQLite serialises
            # those against each other and throws "database is locked"; WAL lets
            # readers proceed during a write, which is exactly our access shape.
            @event.listens_for(self.engine.sync_engine, "connect")
            def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=10000")
                cursor.close()

        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.factory() as session:
            yield session

    async def create_all(self) -> None:
        """Only for tests and the SQLite quick-start; production runs Alembic."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def ping(self) -> bool:
        async with self.engine.connect() as conn:
            await conn.execute(select(1))
        return True

    async def dispose(self) -> None:
        await self.engine.dispose()


class Repository:
    """Data access. Each method opens and closes its own short transaction."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -- learners --------------------------------------------------------

    async def ensure_learner(self, learner_id: str, display_name: str = "") -> None:
        async with self.db.session() as s:
            existing = await s.get(Learner, learner_id)
            if existing is None:
                s.add(Learner(id=learner_id, display_name=display_name or learner_id))
                await s.commit()

    async def mastery_for(self, learner_id: str) -> dict[str, float]:
        async with self.db.session() as s:
            rows = (
                await s.execute(select(Mastery).where(Mastery.learner_id == learner_id))
            ).scalars()
            return {row.concept: row.score for row in rows}

    async def mastery_detail(self, learner_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(Mastery)
                    .where(Mastery.learner_id == learner_id)
                    .order_by(Mastery.concept)
                )
            ).scalars()
            return [
                {
                    "concept": r.concept,
                    "score": round(r.score, 4),
                    "evidence_count": r.evidence_count,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in rows
            ]

    async def save_mastery(self, learner_id: str, scores: dict[str, float]) -> None:
        if not scores:
            return
        async with self.db.session() as s:
            existing = {
                row.concept: row
                for row in (
                    await s.execute(select(Mastery).where(Mastery.learner_id == learner_id))
                ).scalars()
            }
            for concept, score in scores.items():
                row = existing.get(concept)
                if row is None:
                    s.add(
                        Mastery(
                            learner_id=learner_id,
                            concept=concept,
                            score=float(score),
                            evidence_count=1,
                        )
                    )
                else:
                    row.score = float(score)
                    row.evidence_count += 1
                    row.updated_at = utcnow()
            await s.commit()

    # -- sessions --------------------------------------------------------

    async def create_session(self, **fields: Any) -> None:
        async with self.db.session() as s:
            s.add(Session(**fields))
            await s.commit()

    async def get_session(self, session_id: str) -> Session | None:
        async with self.db.session() as s:
            return await s.get(Session, session_id)

    async def get_session_for_learner(self, session_id: str, learner_id: str) -> Session | None:
        async with self.db.session() as s:
            return await s.scalar(
                select(Session).where(
                    Session.id == session_id,
                    Session.learner_id == learner_id,
                )
            )

    async def set_status(self, session_id: str, status: str, error: str = "") -> None:
        async with self.db.session() as s:
            row = await s.get(Session, session_id)
            if row is None:
                return
            row.status = status
            row.error = error
            row.updated_at = utcnow()
            await s.commit()

    async def list_sessions(self, learner_id: str, limit: int = 20) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(Session)
                    .where(Session.learner_id == learner_id)
                    .order_by(Session.created_at.desc())
                    .limit(limit)
                )
            ).scalars()
            return [
                {
                    "id": r.id,
                    "mission_id": r.mission_id,
                    "pack_id": r.pack_id,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    # -- Agent Tasks ------------------------------------------------------

    async def create_agent_task(self, **fields: Any) -> None:
        async with self.db.session() as s:
            s.add(AgentTask(**fields))
            await s.commit()

    async def create_agent_execution(
        self,
        *,
        execution_id: str,
        task_id: str,
        learner_id: str,
        graph_version: str,
        trigger: str = "agent-task",
        schedule_id: str | None = None,
        scheduled_for: Any | None = None,
    ) -> None:
        async with self.db.session() as s:
            s.add(
                AgentExecution(
                    id=execution_id,
                    task_id=task_id,
                    learner_id=learner_id,
                    graph_version=graph_version,
                    trigger=trigger,
                    schedule_id=schedule_id,
                    scheduled_for=scheduled_for,
                    status="running",
                    workflow_state={},
                    trace_spans=[],
                )
            )
            task = await s.get(AgentTask, task_id)
            if task is not None:
                task.current_execution_id = execution_id
                task.latest_execution_id = execution_id
                task.updated_at = utcnow()
            await s.commit()

    async def update_agent_execution(
        self,
        execution_id: str,
        *,
        status: str | None = None,
        workflow_state: dict[str, Any] | None = None,
        trace_spans: list[dict[str, Any]] | None = None,
        event_count: int | None = None,
        error: str | None = None,
        ended: bool = False,
    ) -> None:
        async with self.db.session() as s:
            row = await s.get(AgentExecution, execution_id)
            if row is None:
                return
            if status is not None:
                row.status = status
            if workflow_state is not None:
                row.workflow_state = workflow_state
            if trace_spans is not None:
                row.trace_spans = trace_spans
            if event_count is not None:
                row.event_count = event_count
            if error is not None:
                row.error = error
            if ended:
                row.ended_at = utcnow()
            row.updated_at = utcnow()
            await s.commit()

    async def get_agent_execution(
        self, execution_id: str, learner_id: str | None = None
    ) -> AgentExecution | None:
        async with self.db.session() as s:
            stmt = select(AgentExecution).where(AgentExecution.id == execution_id)
            if learner_id is not None:
                stmt = stmt.where(AgentExecution.learner_id == learner_id)
            return await s.scalar(stmt)

    async def list_agent_executions(
        self, task_id: str, learner_id: str, limit: int = 20
    ) -> list[AgentExecution]:
        async with self.db.session() as s:
            return list(
                (
                    await s.execute(
                        select(AgentExecution)
                        .where(
                            AgentExecution.task_id == task_id,
                            AgentExecution.learner_id == learner_id,
                        )
                        .order_by(AgentExecution.created_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
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
                    # A SQLite development worker has no SKIP LOCKED. If two
                    # pollers race the same unique slot, the loser simply
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

    async def set_agent_task_status(self, task_id: str, status: str, error: str = "") -> None:
        async with self.db.session() as s:
            row = await s.get(AgentTask, task_id)
            if row is None:
                return
            row.status = status
            row.error = error
            row.updated_at = utcnow()
            await s.commit()

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
        async with self.db.session() as s:
            highest = (
                await s.execute(
                    select(func.max(AgentTaskEvent.sequence)).where(
                        AgentTaskEvent.task_id == task_id
                    )
                )
            ).scalar() or 0
            for offset, event in enumerate(events, start=1):
                s.add(
                    AgentTaskEvent(
                        task_id=task_id,
                        sequence=highest + offset,
                        kind=str(event.get("kind", "")),
                        agent=str(event.get("agent", "")),
                        payload=event.get("payload") or {},
                        execution_id=event.get("execution_id"),
                        runtime=event.get("runtime")
                        or (event.get("payload") or {}).get("runtime")
                        or {},
                    )
                )
            await s.commit()
            return highest + len(events)

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
            return [
                {
                    "sequence": r.sequence,
                    "kind": r.kind,
                    "agent": r.agent,
                    "payload": r.payload,
                    "execution_id": r.execution_id or (r.runtime or {}).get("execution_id"),
                    "run_id": (r.runtime or {}).get("run_id"),
                    "step": (r.runtime or {}).get("step"),
                    "node": (r.runtime or {}).get("node"),
                    "task_id": (r.runtime or {}).get("task_id"),
                    "namespace": (r.runtime or {}).get("namespace"),
                    "checkpoint_id": (r.runtime or {}).get("checkpoint_id"),
                    "span_id": (r.runtime or {}).get("span_id"),
                    "runtime": r.runtime or {},
                    "ts": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    async def agent_event_count_for_execution(self, execution_id: str) -> int:
        async with self.db.session() as s:
            count = await s.scalar(
                select(func.count())
                .select_from(AgentTaskEvent)
                .where(AgentTaskEvent.execution_id == execution_id)
            )
            return int(count or 0)

    async def agent_events_after_for_learner(
        self, task_id: str, learner_id: str, after: int = 0, limit: int = 500
    ) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(AgentTaskEvent)
                    .join(AgentTask, AgentTask.id == AgentTaskEvent.task_id)
                    .where(
                        AgentTaskEvent.task_id == task_id,
                        AgentTask.learner_id == learner_id,
                        AgentTaskEvent.sequence > after,
                    )
                    .order_by(AgentTaskEvent.sequence)
                    .limit(limit)
                )
            ).scalars()
            return [
                {
                    "sequence": r.sequence,
                    "kind": r.kind,
                    "agent": r.agent,
                    "payload": r.payload,
                    "execution_id": r.execution_id or (r.runtime or {}).get("execution_id"),
                    "run_id": (r.runtime or {}).get("run_id"),
                    "step": (r.runtime or {}).get("step"),
                    "node": (r.runtime or {}).get("node"),
                    "task_id": (r.runtime or {}).get("task_id"),
                    "namespace": (r.runtime or {}).get("namespace"),
                    "checkpoint_id": (r.runtime or {}).get("checkpoint_id"),
                    "span_id": (r.runtime or {}).get("span_id"),
                    "runtime": r.runtime or {},
                    "ts": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    # -- sidecars --------------------------------------------------------

    async def upsert_agent_sidecar(
        self,
        *,
        sidecar_id: str,
        task_id: str,
        learner_id: str,
        kind: str,
        input: dict[str, Any],
    ) -> dict[str, Any]:
        async with self.db.session() as s:
            row = await s.scalar(
                select(AgentTaskSidecar).where(
                    AgentTaskSidecar.task_id == task_id,
                    AgentTaskSidecar.kind == kind,
                )
            )
            if row is None:
                row = AgentTaskSidecar(
                    id=sidecar_id,
                    task_id=task_id,
                    learner_id=learner_id,
                    kind=kind,
                    status="queued",
                    input=input,
                    output={},
                    error="",
                    attempts=0,
                )
                s.add(row)
            elif row.input == input and row.status in {"queued", "running", "succeeded"}:
                await s.commit()
                return _sidecar_dict(row)
            elif row.status in {"failed", "queued", "succeeded"}:
                row.input = input
                row.status = "queued"
                row.error = ""
                row.output = {}
            await s.commit()
            return _sidecar_dict(row)

    async def claim_agent_sidecar(self, sidecar_id: str) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.get(AgentTaskSidecar, sidecar_id)
            if row is None or row.status in {"running", "succeeded"}:
                return None
            row.status = "running"
            row.attempts = int(row.attempts or 0) + 1
            row.updated_at = utcnow()
            await s.commit()
            return _sidecar_dict(row)

    async def finish_agent_sidecar(
        self, sidecar_id: str, *, status: str, output: dict[str, Any] | None = None, error: str = ""
    ) -> None:
        async with self.db.session() as s:
            row = await s.get(AgentTaskSidecar, sidecar_id)
            if row is None:
                return
            row.status = status
            row.output = output or {}
            row.error = error
            row.updated_at = utcnow()
            await s.commit()

    async def list_agent_sidecars(self, task_id: str, learner_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(AgentTaskSidecar)
                    .where(
                        AgentTaskSidecar.task_id == task_id,
                        AgentTaskSidecar.learner_id == learner_id,
                    )
                    .order_by(AgentTaskSidecar.created_at)
                )
            ).scalars()
            return [_sidecar_dict(row) for row in rows]

    async def queued_agent_sidecars(self) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(AgentTaskSidecar).where(
                        AgentTaskSidecar.status.in_(("queued", "running"))
                    )
                )
            ).scalars()
            return [_sidecar_dict(row) for row in rows]

    # -- knowledge graphs -----------------------------------------------

    async def get_knowledge_graph(self, graph_id: str, learner_id: str) -> dict[str, Any] | None:
        async with self.db.session() as s:
            graph = await s.scalar(
                select(KnowledgeGraph).where(
                    KnowledgeGraph.graph_id == graph_id,
                    KnowledgeGraph.learner_id == learner_id,
                )
            )
            if graph is None:
                return None
            nodes = (
                (
                    await s.execute(
                        select(KnowledgeGraphNode)
                        .where(KnowledgeGraphNode.graph_id == graph_id)
                        .order_by(KnowledgeGraphNode.level, KnowledgeGraphNode.node_id)
                    )
                )
                .scalars()
                .all()
            )
            edges = (
                (
                    await s.execute(
                        select(KnowledgeGraphEdge)
                        .where(KnowledgeGraphEdge.graph_id == graph_id)
                        .order_by(KnowledgeGraphEdge.edge_id)
                    )
                )
                .scalars()
                .all()
            )
            overlays = (
                (
                    await s.execute(
                        select(KnowledgeGraphLearnerOverlay).where(
                            KnowledgeGraphLearnerOverlay.graph_id == graph_id,
                            KnowledgeGraphLearnerOverlay.learner_id == learner_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            return graph_snapshot_dict(graph, nodes, edges, overlays)

    async def list_knowledge_graph_candidates(
        self, learner_id: str, query: str, limit: int = 3
    ) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            graphs = (
                (
                    await s.execute(
                        select(KnowledgeGraph)
                        .where(KnowledgeGraph.learner_id == learner_id)
                        .order_by(KnowledgeGraph.updated_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            normalized_query = "".join(query.split()).casefold()
            terms = {term.casefold() for term in query.split() if term.strip()}
            if normalized_query:
                terms.add(normalized_query)
                terms.update(
                    normalized_query[index : index + 2]
                    for index in range(max(0, len(normalized_query) - 1))
                )
            scored: list[tuple[int, KnowledgeGraph]] = []
            for graph in graphs:
                nodes = (
                    (
                        await s.execute(
                            select(KnowledgeGraphNode).where(
                                KnowledgeGraphNode.graph_id == graph.graph_id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                haystack = " ".join(
                    [
                        graph.title,
                        graph.domain,
                        *[node.label for node in nodes],
                        *sum((node.aliases or [] for node in nodes), []),
                    ]
                ).casefold()
                score = sum(1 for term in terms if term in haystack)
                if score:
                    scored.append((score, graph))
            scored.sort(
                key=lambda item: (
                    -item[0],
                    -(item[1].updated_at.timestamp() if item[1].updated_at else 0),
                )
            )
            snapshots: list[dict[str, Any]] = []
            for _, graph in scored[:limit]:
                snapshot = await self.get_knowledge_graph(graph.graph_id, learner_id)
                if snapshot is not None:
                    snapshots.append(snapshot)
            return snapshots

    async def apply_knowledge_graph_result(
        self,
        *,
        learner_id: str,
        task_id: str,
        result: dict[str, Any],
        graph_id: str | None = None,
    ) -> dict[str, Any] | None:
        if result.get("status") != "ok":
            target = result["decision"].get("target_graph_id")
            return await self.get_knowledge_graph(target, learner_id) if target else None
        action = result["decision"]["action"]
        target = result["decision"].get("target_graph_id")
        existing_for_validation = (
            await self.get_knowledge_graph(target, learner_id) if target else None
        )
        if action in {"extend_graph", "update_graph"} and existing_for_validation is not None:
            expected_revision = result["decision"].get("base_revision")
            if int(existing_for_validation["revision"]) != int(expected_revision):
                raise GraphRevisionConflict("knowledge graph revision conflict")
        validate_result(result, existing_for_validation)
        if action == "no_change":
            return await self.get_knowledge_graph(target, learner_id) if target else None
        patch = result["graph_patch"]
        async with self.db.session() as s:
            selected_id = graph_id or target
            graph = (
                await s.scalar(
                    select(KnowledgeGraph).where(
                        KnowledgeGraph.graph_id == selected_id,
                        KnowledgeGraph.learner_id == learner_id,
                    )
                )
                if selected_id
                else None
            )
            if action == "create_graph":
                if graph is not None:
                    prior_event = await s.scalar(
                        select(KnowledgeGraphEvent).where(
                            KnowledgeGraphEvent.graph_id == selected_id,
                            KnowledgeGraphEvent.learner_id == learner_id,
                            KnowledgeGraphEvent.task_id == task_id,
                        )
                    )
                    if prior_event is not None:
                        await s.rollback()
                        return await self.get_knowledge_graph(selected_id, learner_id)
                    raise GraphRevisionConflict("graph id already exists")
                if not selected_id:
                    raise ValueError("host must allocate graph_id for create_graph")
                graph = KnowledgeGraph(
                    graph_id=selected_id,
                    learner_id=learner_id,
                    title=result["decision"].get("proposed_title") or "我的知识图谱",
                    domain=result["decision"].get("proposed_domain") or "",
                    revision=0,
                )
                s.add(graph)
                await s.flush()
            else:
                if graph is None:
                    raise KeyError("knowledge graph not found")
                expected = result["decision"].get("base_revision")
                if int(graph.revision) != int(expected):
                    raise GraphRevisionConflict("knowledge graph revision conflict")

            existing_nodes = {
                row.node_id: row
                for row in (
                    await s.execute(
                        select(KnowledgeGraphNode).where(
                            KnowledgeGraphNode.graph_id == graph.graph_id
                        )
                    )
                ).scalars()
            }
            existing_edges = {
                row.edge_id: row
                for row in (
                    await s.execute(
                        select(KnowledgeGraphEdge).where(
                            KnowledgeGraphEdge.graph_id == graph.graph_id
                        )
                    )
                ).scalars()
            }
            existing_overlay = {
                row.node_id: row
                for row in (
                    await s.execute(
                        select(KnowledgeGraphLearnerOverlay).where(
                            KnowledgeGraphLearnerOverlay.graph_id == graph.graph_id,
                            KnowledgeGraphLearnerOverlay.learner_id == learner_id,
                        )
                    )
                ).scalars()
            }
            for node in patch["add_nodes"]:
                values = dict(node)
                is_current = bool(values.pop("is_current", False))
                learning_state = values.pop("learning_state", "unknown")
                values["graph_id"] = graph.graph_id
                values["node_id"] = values.pop("id")
                s.add(KnowledgeGraphNode(**values))
                overlay = KnowledgeGraphLearnerOverlay(
                    graph_id=graph.graph_id,
                    learner_id=learner_id,
                    node_id=values["node_id"],
                    is_current=is_current,
                    learning_state=learning_state,
                    evidence_ids=[],
                )
                s.add(overlay)
                existing_overlay[values["node_id"]] = overlay
            for update in patch["update_nodes"]:
                row = existing_nodes[update["id"]]
                for key, value in update["set"].items():
                    setattr(row, key, value)
            for edge in patch["add_edges"]:
                values = dict(edge)
                if values["relation"] in {"contrasts_with", "commonly_confused_with", "related_to"}:
                    values["source"], values["target"] = sorted(
                        (values["source"], values["target"])
                    )
                values["graph_id"] = graph.graph_id
                values["edge_id"] = values.pop("id")
                values["source_node_id"] = values.pop("source")
                values["target_node_id"] = values.pop("target")
                s.add(KnowledgeGraphEdge(**values))
            for update in patch["update_edges"]:
                row = existing_edges[update["id"]]
                for key, value in update["set"].items():
                    setattr(row, key, value)
            for update in patch["learner_overlay_updates"]:
                row = existing_overlay.get(update["node_id"])
                if row is None:
                    row = KnowledgeGraphLearnerOverlay(
                        graph_id=graph.graph_id,
                        learner_id=learner_id,
                        node_id=update["node_id"],
                        is_current=False,
                        learning_state="unknown",
                        evidence_ids=[],
                    )
                    s.add(row)
                if "is_current" in update:
                    row.is_current = bool(update["is_current"])
                if "learning_state" in update:
                    row.learning_state = update["learning_state"]
                if "evidence_ids" in update:
                    row.evidence_ids = list(update["evidence_ids"])
            if result["decision"].get("proposed_title"):
                graph.title = result["decision"]["proposed_title"]
            if result["decision"].get("proposed_domain"):
                graph.domain = result["decision"]["proposed_domain"]
            base_revision = int(graph.revision)
            graph.revision = base_revision + 1
            graph.updated_at = utcnow()
            s.add(
                KnowledgeGraphEvent(
                    event_id=f"{task_id}:{graph.graph_id}:{graph.revision}",
                    learner_id=learner_id,
                    graph_id=graph.graph_id,
                    task_id=task_id,
                    base_revision=None if action == "create_graph" else base_revision,
                    new_revision=graph.revision,
                    patch=patch,
                )
            )
            await s.commit()
        return await self.get_knowledge_graph(graph.graph_id, learner_id)

    # -- events ----------------------------------------------------------

    async def next_sequence(self, session_id: str) -> int:
        async with self.db.session() as s:
            highest = (
                await s.execute(
                    select(func.max(RunEvent.sequence)).where(RunEvent.session_id == session_id)
                )
            ).scalar()
            return int(highest or 0)

    async def append_events(self, session_id: str, events: list[dict[str, Any]]) -> int:
        """Append projections with a monotonic per-session sequence."""
        if not events:
            return await self.next_sequence(session_id)
        async with self.db.session() as s:
            highest = (
                await s.execute(
                    select(func.max(RunEvent.sequence)).where(RunEvent.session_id == session_id)
                )
            ).scalar() or 0
            for offset, event in enumerate(events, start=1):
                s.add(
                    RunEvent(
                        session_id=session_id,
                        sequence=highest + offset,
                        kind=str(event.get("kind", "")),
                        node=str(event.get("node") or ""),
                        payload=event.get("payload") or {},
                    )
                )
            await s.commit()
            return highest + len(events)

    async def events_after(
        self, session_id: str, after: int = 0, limit: int = 500
    ) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(RunEvent)
                    .where(RunEvent.session_id == session_id, RunEvent.sequence > after)
                    .order_by(RunEvent.sequence)
                    .limit(limit)
                )
            ).scalars()
            return [
                {
                    "sequence": r.sequence,
                    "kind": r.kind,
                    "node": r.node,
                    "payload": r.payload,
                    "ts": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    async def events_after_for_learner(
        self, session_id: str, learner_id: str, after: int = 0, limit: int = 500
    ) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(RunEvent)
                    .join(Session, Session.id == RunEvent.session_id)
                    .where(
                        RunEvent.session_id == session_id,
                        Session.learner_id == learner_id,
                        RunEvent.sequence > after,
                    )
                    .order_by(RunEvent.sequence)
                    .limit(limit)
                )
            ).scalars()
            return [
                {
                    "sequence": r.sequence,
                    "kind": r.kind,
                    "node": r.node,
                    "payload": r.payload,
                    "ts": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    # -- reports ---------------------------------------------------------

    async def save_report(
        self, *, session_id: str, learner_id: str, mission_id: str, report: dict[str, Any]
    ) -> None:
        async with self.db.session() as s:
            await s.execute(delete(ReportRecord).where(ReportRecord.session_id == session_id))
            s.add(
                ReportRecord(
                    session_id=session_id,
                    learner_id=learner_id,
                    mission_id=mission_id,
                    probe_score=float(report.get("probe_score", 0.0)),
                    verify_score=float(report.get("verify_score", 0.0)),
                    payload=report,
                )
            )
            await s.commit()

    async def get_report(self, session_id: str) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.get(ReportRecord, session_id)
            return dict(row.payload) if row else None

    async def get_report_for_learner(
        self, session_id: str, learner_id: str
    ) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.scalar(
                select(ReportRecord).where(
                    ReportRecord.session_id == session_id,
                    ReportRecord.learner_id == learner_id,
                )
            )
            return dict(row.payload) if row else None


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


def _sidecar_dict(row: AgentTaskSidecar) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "learner_id": row.learner_id,
        "kind": row.kind,
        "status": row.status,
        "input": row.input or {},
        "output": row.output or {},
        "error": row.error,
        "attempts": row.attempts,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
