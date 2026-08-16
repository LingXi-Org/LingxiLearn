"""Engine, session factory and the repository.

One rule worth stating because breaking it is the classic scaling mistake:
**never hold a database session open across a graph run.**  Resolve what you
need, release the connection, then stream.  A pool of 10 gated on model latency
caps you at 10 concurrent learners for no reason.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, event, func, inspect, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import Settings
from .runtime_tables import project_runtime_events

__all__ = ["Database", "Repository"]
from .models import (
    AgentExecution,
    AgentInteraction,
    AgentInteractionAnswer,
    AgentRun,
    AgentSchedule,
    AgentScheduleRun,
    AgentTask,
    AgentTaskEvent,
    AgentTurn,
    Base,
    BudgetLedger,
    CandidateSnapshot,
    CommandInbox,
    FactSnapshot,
    Learner,
    Mastery,
    QuizSubmission,
    ReportRecord,
    RunEvent,
    Session,
    SkillRun,
    TransactionalOutbox,
    WorkDependency,
    WorkItem,
    WorkResult,
    Workspace,
    utcnow,
)


def _utc_datetime(value: datetime) -> datetime:
    """Normalize SQLite's naive DateTime round-trip to UTC for comparisons."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


logger = logging.getLogger(__name__)


# SQLite is the supported zero-setup development database.  Older local
# checkouts were created with ``Base.metadata.create_all`` before the latest
# migrations were added, so ``create_all`` alone cannot repair them.  Keep the
# compatibility DDL explicit and small: production PostgreSQL still uses the
# normal Alembic chain, while a local SQLite restart upgrades the existing
# file in place without discarding learner data.
_SQLITE_SCHEMA_HEAD = "0018_mothership_protocol_v1"
_SQLITE_COMPAT_COLUMNS: dict[str, dict[str, str]] = {
    "agent_tasks": {
        "create_idempotency_key": "VARCHAR(192)",
        "create_payload_digest": "VARCHAR(64)",
        "title": "TEXT NOT NULL DEFAULT ''",
        "is_pinned": "BOOLEAN NOT NULL DEFAULT 0",
        "is_unread": "BOOLEAN NOT NULL DEFAULT 0",
        "deleted_at": "DATETIME",
        "resources": "JSON NOT NULL DEFAULT '[]'",
        "graph_version": "VARCHAR(32) NOT NULL DEFAULT 'difficult_knowledge.v2'",
        "deck_result": "JSON NOT NULL DEFAULT '{}'",
        "quiz_result": "JSON NOT NULL DEFAULT '{}'",
        "adaptive_result": "JSON NOT NULL DEFAULT '{}'",
        "handoff_result": "JSON NOT NULL DEFAULT '{}'",
        "user_messages": "JSON NOT NULL DEFAULT '[]'",
        "current_execution_id": "VARCHAR(128)",
        "latest_execution_id": "VARCHAR(128)",
        # 0018: the long-lived thread status alongside the legacy one-shot one.
        "thread_status": "VARCHAR(24) NOT NULL DEFAULT 'open'",
    },
    "agent_task_events": {
        "execution_id": "VARCHAR(128)",
        "runtime": "JSON NOT NULL DEFAULT '{}'",
        # 0018: protocol version + canonical identity on the event log.
        "protocol_version": "INTEGER NOT NULL DEFAULT 0",
        "turn_id": "VARCHAR(128)",
        "agent_run_id": "VARCHAR(128)",
        "skill_run_id": "VARCHAR(160)",
    },
    "agent_executions": {
        # 0018: link an execution to its turn and to the execution it resumes.
        "turn_id": "VARCHAR(128)",
        "parent_execution_id": "VARCHAR(128)",
        "resumes_execution_id": "VARCHAR(128)",
    },
    "workspace_knowledge_tags": {
        "tag_slot": "VARCHAR(32) NOT NULL DEFAULT ''",
    },
    "workspace_table_views": {
        "is_default": "BOOLEAN NOT NULL DEFAULT 0",
        "created_by": "VARCHAR(64)",
    },
    "learning_evidence": {
        "task_id": "VARCHAR(96)",
        "knowledge_point": "VARCHAR(160) NOT NULL DEFAULT ''",
        "signal": "VARCHAR(48) NOT NULL DEFAULT ''",
        "source_agent": "VARCHAR(96) NOT NULL DEFAULT ''",
        "payload": "JSON NOT NULL DEFAULT '{}'",
        "seq": "INTEGER NOT NULL DEFAULT 0",
        "observed_at": "DATETIME",
    },
    "session_state": {
        "board": "JSON NOT NULL DEFAULT '{}'",
    },
    "work_items": {
        "reserved_tokens": "INTEGER NOT NULL DEFAULT 0",
        "reserved_heavy": "INTEGER NOT NULL DEFAULT 0",
        "reserved_wall_ms": "INTEGER NOT NULL DEFAULT 0",
    },
}


def _repair_sqlite_schema(connection: Any) -> None:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    repaired: list[str] = []

    for table_name, columns in _SQLITE_COMPAT_COLUMNS.items():
        if table_name not in existing_tables:
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, ddl in columns.items():
            if column_name in existing_columns:
                continue
            connection.exec_driver_sql(
                f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {ddl}'
            )
            repaired.append(f"{table_name}.{column_name}")

    # ``create_all`` does not create indexes for columns added above.  Let
    # SQLAlchemy create every declared index after the column repair; existing
    # indexes are left untouched.
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            index.create(connection, checkfirst=True)

    # A create_all-created SQLite file has no migration marker.  Once the
    # current model schema has been materialised, mark it at the same head as
    # Alembic so a later explicit ``alembic upgrade head`` is a no-op rather
    # than replaying migrations over already-existing tables.
    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"
    )
    connection.exec_driver_sql("DELETE FROM alembic_version")
    connection.exec_driver_sql(
        "INSERT INTO alembic_version (version_num) VALUES (?)",
        (_SQLITE_SCHEMA_HEAD,),
    )
    if repaired:
        logger.info("Repaired SQLite schema columns: %s", ", ".join(repaired))


class Database:
    def __init__(self, settings: Settings) -> None:
        url = settings.resolved_database_url
        kwargs: dict[str, Any] = {"pool_pre_ping": True}
        if url.startswith("postgresql"):
            kwargs.update(
                pool_size=max(1, settings.db_pool_size),
                max_overflow=max(0, settings.db_max_overflow),
            )
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
        # Event producers include the graph stream and lifecycle
        # handlers. They may append to one task concurrently. Serialise the
        # sequence allocation in-process; PostgreSQL row locking below covers
        # separate workers as well.
        self._agent_event_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def agent_event_lock(self, task_id: str) -> asyncio.Lock:
        return self._agent_event_locks[task_id]

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.factory() as session:
            yield session

    async def create_all(self) -> None:
        """Only for tests and the SQLite quick-start; production runs Alembic."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def ensure_sqlite_schema(self) -> None:
        """Create or repair the local SQLite schema without dropping data."""
        if not self.engine.url.drivername.startswith("sqlite"):
            return
        await self.create_all()
        async with self.engine.begin() as conn:
            await conn.run_sync(_repair_sqlite_schema)

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

    async def ensure_workspace(self, learner_id: str) -> None:
        """Create the learner workspace once, tolerating concurrent first runs."""

        async with self.db.session() as s:
            existing = await s.scalar(select(Workspace).where(Workspace.learner_id == learner_id))
            if existing is not None:
                return
            s.add(
                Workspace(
                    id=f"ws_{uuid4().hex}",
                    learner_id=learner_id,
                    name="灵犀智学",
                    appearance={},
                )
            )
            try:
                await s.commit()
            except IntegrityError:
                await s.rollback()
                winner = await s.scalar(select(Workspace).where(Workspace.learner_id == learner_id))
                if winner is None:
                    raise

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
        turn_id: str | None = None,
        parent_execution_id: str | None = None,
        resumes_execution_id: str | None = None,
    ) -> None:
        async with self.db.session() as s:
            s.add(
                AgentExecution(
                    id=execution_id,
                    task_id=task_id,
                    learner_id=learner_id,
                    turn_id=turn_id,
                    parent_execution_id=parent_execution_id,
                    resumes_execution_id=resumes_execution_id,
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

    async def claim_agent_task(self, task_id: str, learner_id: str) -> AgentTask | None:
        """Atomically claim a runnable task for one process.

        Task execution is launched from an asyncio background task, so the
        database is the only coordination point shared by API replicas and a
        restarted process.  A conditional update prevents startup recovery,
        retries, and the original request from running the same task twice.

        A task is claimable when it is queued, waiting on the learner, or —
        under the long-lived thread model (issue #18 §4.1) — when the thread is
        still open even though an earlier turn ended in a terminal legacy
        status.  A running task is never claimable.
        """

        async with self.db.session() as s:
            result = await s.execute(
                update(AgentTask)
                .where(
                    AgentTask.id == task_id,
                    AgentTask.learner_id == learner_id,
                    AgentTask.thread_status.in_(("open", "awaiting_user", "running")),
                    AgentTask.status.notin_(("running", "cancelled")),
                )
                .values(status="running", updated_at=utcnow())
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
            task = await s.get(AgentTask, task_id)
            learner_id = task.learner_id if task is not None else ""
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
            snapshot = _quiz_submission_dict(row)
        if learner_id:
            await self.project_runtime_event(
                learner_id=learner_id,
                record_key=f"assessment:{task_id}:{submission_id}",
                task_id=task_id,
                kind="assessment.submitted",
                payload=snapshot,
            )
        return snapshot

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

        Shared by the ordinary append and the outbox publisher so both produce
        identical rows and identical V1 envelope sequencing.
        """

        highest = (
            await s.execute(
                select(func.max(AgentTaskEvent.sequence)).where(AgentTaskEvent.task_id == task_id)
            )
        ).scalar() or 0
        runtime_records: list[dict[str, Any]] = []
        for offset, event in enumerate(events, start=1):
            sequence = highest + offset
            runtime = event.get("runtime") or (event.get("payload") or {}).get("runtime") or {}
            payload = event.get("payload") or {}
            if int(event.get("protocol_version") or 0) == 1:
                # Keep the V1 envelope seq equal to the durable row
                # sequence so Last-Event-ID reconnect works uniformly
                # across protocols (issue #18 §15.2).
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
                    protocol_version=int(event.get("protocol_version") or 0),
                    turn_id=event.get("turn_id"),
                    agent_run_id=event.get("agent_run_id"),
                    skill_run_id=event.get("skill_run_id"),
                )
            )
            runtime_records.append(
                {
                    "record_key": f"task:{task_id}:{sequence}",
                    "task_id": task_id,
                    "sequence": sequence,
                    "kind": str(event.get("kind", "")),
                    "agent": str(event.get("agent", "")),
                    "payload": payload,
                    "execution_id": event.get("execution_id"),
                    "runtime": runtime,
                }
            )
        await project_runtime_events(
            s,
            learner_id=task.learner_id,
            records=runtime_records,
            workspace=await s.scalar(
                select(Workspace).where(Workspace.learner_id == task.learner_id)
            ),
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
        await self.ensure_workspace(task_record.learner_id)
        async with self.db.agent_event_lock(task_id):
            async with self.db.session() as s:
                # FOR UPDATE makes the max(sequence) allocation atomic across
                # API/worker processes on PostgreSQL. SQLite ignores it, but
                # the per-task asyncio lock still serialises local writers.
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
        await self.ensure_workspace(task_record.learner_id)
        async with self.db.agent_event_lock(task_id):
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
            ).scalars().all()
            return [_agent_event_dict(row) for row in rows]

    async def agent_events_after_for_learner(
        self,
        task_id: str,
        learner_id: str,
        after: int = 0,
        limit: int = 500,
        *,
        protocol_version: int | None = None,
    ) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            stmt = (
                select(AgentTaskEvent)
                .join(AgentTask, AgentTask.id == AgentTaskEvent.task_id)
                .where(
                    AgentTaskEvent.task_id == task_id,
                    AgentTask.learner_id == learner_id,
                    AgentTaskEvent.sequence > after,
                )
            )
            if protocol_version is not None:
                stmt = stmt.where(AgentTaskEvent.protocol_version == protocol_version)
            rows = (
                await s.execute(stmt.order_by(AgentTaskEvent.sequence).limit(limit))
            ).scalars()
            return [_agent_event_dict(r) for r in rows]

    # -- Mothership V1: AgentRun / SkillRun / Interaction ------------------

    async def create_agent_run(
        self,
        *,
        agent_run_id: str,
        task_id: str,
        execution_id: str,
        provider_id: str,
        turn_id: str | None = None,
        work_item_id: str | None = None,
        parent_agent_run_id: str | None = None,
        agent_display_name: str = "",
        execution_kind: str = "model",
        capability: str = "",
        presentation_role: str = "supporting",
        status: str = "queued",
        started: bool = False,
        start_sequence: int | None = None,
        safe_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self.db.session() as s:
            row = AgentRun(
                id=agent_run_id,
                task_id=task_id,
                turn_id=turn_id,
                execution_id=execution_id,
                work_item_id=work_item_id,
                parent_agent_run_id=parent_agent_run_id,
                provider_id=provider_id,
                agent_display_name=agent_display_name,
                execution_kind=execution_kind,
                capability=capability,
                presentation_role=presentation_role,
                status="running" if started else status,
                started_at=utcnow() if started else None,
                start_sequence=start_sequence,
                safe_metadata=dict(safe_metadata or {}),
            )
            s.add(row)
            await s.commit()
            return _agent_run_dict(row)

    async def update_agent_run(
        self,
        agent_run_id: str,
        *,
        status: str | None = None,
        ended: bool = False,
        end_sequence: int | None = None,
    ) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.get(AgentRun, agent_run_id)
            if row is None:
                return None
            if status is not None:
                row.status = status
            if end_sequence is not None:
                row.end_sequence = end_sequence
            if ended:
                row.ended_at = utcnow()
            row.updated_at = utcnow()
            await s.commit()
            return _agent_run_dict(row)

    async def agent_run(self, agent_run_id: str) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.get(AgentRun, agent_run_id)
            return _agent_run_dict(row) if row is not None else None

    async def agent_runs_for_execution(self, execution_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(AgentRun)
                    .where(AgentRun.execution_id == execution_id)
                    .order_by(AgentRun.start_sequence, AgentRun.created_at)
                )
            ).all()
            return [_agent_run_dict(row) for row in rows]

    async def agent_runs_for_task(self, task_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(AgentRun)
                    .where(AgentRun.task_id == task_id)
                    .order_by(AgentRun.created_at)
                )
            ).all()
            return [_agent_run_dict(row) for row in rows]

    async def work_dependencies_for_task(self, task_id: str) -> list[dict[str, Any]]:
        """Work Ledger dependency edges for one task, for the execution graph."""

        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(WorkDependency.work_id, WorkDependency.depends_on_id)
                    .join(WorkItem, WorkItem.id == WorkDependency.work_id)
                    .where(WorkItem.task_id == task_id)
                )
            ).all()
            return [{"work_id": work_id, "depends_on_id": depends_on} for work_id, depends_on in rows]

    async def create_skill_run(
        self,
        *,
        skill_run_id: str,
        agent_run_id: str,
        task_id: str,
        execution_id: str,
        skill_id: str,
        turn_id: str | None = None,
        display_name: str = "",
        version: str = "",
        checksum: str = "",
    ) -> dict[str, Any]:
        async with self.db.session() as s:
            row = SkillRun(
                id=skill_run_id,
                agent_run_id=agent_run_id,
                task_id=task_id,
                turn_id=turn_id,
                execution_id=execution_id,
                skill_id=skill_id,
                display_name=display_name,
                version=version,
                checksum=checksum,
                status="running",
                started_at=utcnow(),
            )
            s.add(row)
            await s.commit()
            return _skill_run_dict(row)

    async def update_skill_run(
        self, skill_run_id: str, *, status: str, ended: bool = True
    ) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.get(SkillRun, skill_run_id)
            if row is None:
                return None
            row.status = status
            if ended:
                row.ended_at = utcnow()
            row.updated_at = utcnow()
            await s.commit()
            return _skill_run_dict(row)

    async def skill_runs_for_task(self, task_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(SkillRun).where(SkillRun.task_id == task_id).order_by(SkillRun.created_at)
                )
            ).all()
            return [_skill_run_dict(row) for row in rows]

    async def create_interaction(
        self,
        *,
        interaction_id: str,
        task_id: str,
        request_payload: dict[str, Any],
        turn_id: str | None = None,
        execution_id: str | None = None,
        agent_run_id: str | None = None,
        purpose: str = "clarification",
        presentation: str = "question",
        blocking: bool = True,
        reason_code: str = "",
    ) -> dict[str, Any]:
        async with self.db.session() as s:
            row = AgentInteraction(
                id=interaction_id,
                task_id=task_id,
                turn_id=turn_id,
                execution_id=execution_id,
                agent_run_id=agent_run_id,
                purpose=purpose,
                presentation=presentation,
                blocking=blocking,
                request_payload=dict(request_payload),
                status="pending",
                reason_code=reason_code,
            )
            s.add(row)
            await s.commit()
            return _interaction_dict(row)

    async def get_interaction(
        self, interaction_id: str, *, task_id: str | None = None
    ) -> dict[str, Any] | None:
        async with self.db.session() as s:
            stmt = select(AgentInteraction).where(AgentInteraction.id == interaction_id)
            if task_id is not None:
                stmt = stmt.where(AgentInteraction.task_id == task_id)
            row = await s.scalar(stmt)
            return _interaction_dict(row) if row is not None else None

    async def resolve_interaction(self, interaction_id: str) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.get(AgentInteraction, interaction_id)
            if row is None:
                return None
            row.status = "resolved"
            row.resolved_at = utcnow()
            await s.commit()
            return _interaction_dict(row)

    async def save_interaction_answer(
        self,
        *,
        interaction_id: str,
        answers: list[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Persist one idempotent structured answer; a retried key returns the original."""

        async with self.db.session() as s:
            existing = await s.scalar(
                select(AgentInteractionAnswer).where(
                    AgentInteractionAnswer.interaction_id == interaction_id,
                    AgentInteractionAnswer.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return {
                    "answers": list(existing.answers or []),
                    "created": False,
                }
            row = AgentInteractionAnswer(
                interaction_id=interaction_id,
                answers=list(answers),
                idempotency_key=idempotency_key,
            )
            s.add(row)
            try:
                await s.commit()
            except IntegrityError:
                await s.rollback()
                existing = await s.scalar(
                    select(AgentInteractionAnswer).where(
                        AgentInteractionAnswer.interaction_id == interaction_id,
                        AgentInteractionAnswer.idempotency_key == idempotency_key,
                    )
                )
                if existing is not None:
                    return {"answers": list(existing.answers or []), "created": False}
                raise
            return {"answers": list(answers), "created": True}

    async def claim_interaction_answer(
        self,
        *,
        interaction_id: str,
        task_id: str,
        answers: list[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Resolve one blocking interaction and enqueue its continuation atomically.

        The answer, the pending→resolved transition and the durable
        continuation command commit together, so a crash between them is
        impossible: either the thread is still waiting for an answer, or a
        replayable command exists to resume the original checkpoint.  The
        continuation belongs to the interaction's own turn — answering never
        opens a new one (issue #18 §10.4).

        Outcomes: ``accepted`` (this call resolved it), ``duplicate`` (same
        idempotency key and payload — returns the original), ``conflict``
        (same key, different payload), ``already_resolved`` (another answer
        won), ``not_found``, ``invalid``.
        """

        async with self.db.session() as s:
            # Serialise concurrent answers for this thread; two different keys
            # must not both observe a pending interaction.
            task = await s.scalar(
                select(AgentTask).where(AgentTask.id == task_id).with_for_update()
            )
            if task is None:
                return {"outcome": "not_found"}
            interaction = await s.scalar(
                select(AgentInteraction)
                .where(
                    AgentInteraction.id == interaction_id,
                    AgentInteraction.task_id == task_id,
                )
                .with_for_update()
            )
            if interaction is None:
                return {"outcome": "not_found"}
            existing_answer = await s.scalar(
                select(AgentInteractionAnswer).where(
                    AgentInteractionAnswer.interaction_id == interaction_id,
                    AgentInteractionAnswer.idempotency_key == idempotency_key,
                )
            )
            if existing_answer is not None:
                if list(existing_answer.answers or []) != list(answers):
                    return {"outcome": "conflict"}
                command = await s.scalar(
                    select(CommandInbox).where(
                        CommandInbox.task_id == task_id,
                        CommandInbox.idempotency_key
                        == _interaction_command_key(interaction_id, idempotency_key),
                    )
                )
                return {
                    "outcome": "duplicate",
                    "answers": list(existing_answer.answers or []),
                    "command": _command_dict(command) if command is not None else None,
                    "interaction": _interaction_dict(interaction),
                }
            if interaction.status == "resolved":
                return {"outcome": "already_resolved", "interaction": _interaction_dict(interaction)}
            if interaction.status != "pending":
                return {"outcome": "invalid", "status": interaction.status}
            if not interaction.blocking:
                return {"outcome": "invalid", "status": "non_blocking"}

            sequence = (
                int(
                    await s.scalar(
                        select(func.coalesce(func.max(CommandInbox.sequence), 0)).where(
                            CommandInbox.task_id == task_id
                        )
                    )
                    or 0
                )
                + 1
            )
            # The continuation belongs to the turn that paused.  Older
            # interactions predating turn linkage fall back to the newest turn
            # so the command ledger's foreign key stays valid.
            turn_id = str(interaction.turn_id or "")
            if not turn_id:
                turn_id = str(
                    await s.scalar(
                        select(AgentTurn.id)
                        .where(AgentTurn.task_id == task_id)
                        .order_by(AgentTurn.turn_index.desc())
                        .limit(1)
                    )
                    or ""
                )
            if not turn_id:
                return {"outcome": "invalid", "status": "no_turn"}
            # The pending→resolved transition is the election: a conditional
            # UPDATE is atomic on both PostgreSQL and SQLite, so two concurrent
            # answers cannot both observe a pending interaction and both
            # resume the same checkpoint.
            elected = await s.execute(
                update(AgentInteraction)
                .where(
                    AgentInteraction.id == interaction_id,
                    AgentInteraction.status == "pending",
                )
                .values(status="resolved", resolved_at=utcnow())
            )
            if not int(getattr(elected, "rowcount", 0) or 0):
                await s.rollback()
                return {"outcome": "already_resolved"}
            answer_row = AgentInteractionAnswer(
                interaction_id=interaction_id,
                answers=list(answers),
                idempotency_key=idempotency_key,
            )
            # The public ``interaction.resolved`` fact commits with the
            # transition that produced it.  Appending it afterwards would let a
            # crash leave an interaction durably resolved while the replay log
            # still says the card is pending — the recap would disappear on
            # refresh (issue #18 §10.6).  The outbox row is the durable intent;
            # the service publishes it into the event log and marks it, and any
            # later replay repairs a missed publish.
            outbox = TransactionalOutbox(
                id=f"outbox_{uuid4().hex}",
                event_key=interaction_resolved_event_key(interaction_id),
                task_id=task_id,
                turn_id=turn_id,
                kind="interaction.resolved",
                safe_payload={
                    "interaction_id": interaction_id,
                    "execution_id": str(interaction.execution_id or ""),
                    "turn_id": turn_id,
                    "answers": list(answers),
                },
            )
            command = CommandInbox(
                id=f"cmd_{uuid4().hex}",
                task_id=task_id,
                turn_id=turn_id,
                sequence=sequence,
                kind="interaction_answer",
                idempotency_key=_interaction_command_key(interaction_id, idempotency_key),
                payload={
                    "interaction_id": interaction_id,
                    "answers": list(answers),
                },
            )
            s.add_all([answer_row, command, outbox])
            try:
                await s.commit()
            except IntegrityError:
                await s.rollback()
                return {"outcome": "already_resolved"}
            return {
                "outcome": "accepted",
                "answers": list(answers),
                "command": _command_dict(command),
            }

    async def pending_outbox(self, *, task_id: str | None = None) -> list[dict[str, Any]]:
        """Durable facts committed with their transaction but not yet published."""

        async with self.db.session() as s:
            stmt = select(TransactionalOutbox).where(TransactionalOutbox.published_at.is_(None))
            if task_id is not None:
                stmt = stmt.where(TransactionalOutbox.task_id == task_id)
            rows = (await s.scalars(stmt.order_by(TransactionalOutbox.created_at))).all()
            return [
                {
                    "id": row.id,
                    "event_key": row.event_key,
                    "task_id": row.task_id,
                    "turn_id": row.turn_id,
                    "kind": row.kind,
                    "payload": dict(row.safe_payload or {}),
                }
                for row in rows
            ]

    async def mark_outbox_published(self, outbox_id: str) -> bool:
        """Mark one outbox row published; only the first caller gets True."""

        async with self.db.session() as s:
            result = await s.execute(
                update(TransactionalOutbox)
                .where(
                    TransactionalOutbox.id == outbox_id,
                    TransactionalOutbox.published_at.is_(None),
                )
                .values(published_at=utcnow())
            )
            await s.commit()
            return bool(getattr(result, "rowcount", 0))

    async def pending_interaction_continuations(self) -> list[dict[str, Any]]:
        """Continuation commands whose resume never ran (crash recovery).

        A durable command that is still unconsumed means the answer committed
        but its checkpoint resume did not complete; startup replays it instead
        of leaving the thread waiting forever.
        """

        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(CommandInbox, AgentTask.learner_id)
                    .join(AgentTask, AgentTask.id == CommandInbox.task_id)
                    .where(
                        CommandInbox.kind == "interaction_answer",
                        CommandInbox.consumed_at.is_(None),
                        AgentTask.deleted_at.is_(None),
                    )
                    .order_by(CommandInbox.created_at)
                )
            ).all()
            return [
                {**_command_dict(command), "learner_id": learner_id}
                for command, learner_id in rows
            ]

    async def pending_interactions(self, task_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(AgentInteraction)
                    .where(
                        AgentInteraction.task_id == task_id,
                        AgentInteraction.status == "pending",
                    )
                    .order_by(AgentInteraction.created_at)
                )
            ).all()
            return [_interaction_dict(row) for row in rows]

    # -- V2 coordinator / work ledger -----------------------------------

    async def append_command(
        self,
        *,
        task_id: str,
        kind: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Append one command and create its immutable turn atomically.

        A retried idempotency key returns the original command; it never
        creates a second turn or advances the command sequence.
        """

        async with self.db.session() as s:
            # Turn indexes and command sequences are task-local monotonic
            # counters.  Lock the task row so separate API processes cannot
            # both observe the same high-water mark.
            task = await s.scalar(
                select(AgentTask).where(AgentTask.id == task_id).with_for_update()
            )
            if task is None:
                raise KeyError(f"unknown agent task: {task_id}")
            existing = await s.scalar(
                select(CommandInbox).where(
                    CommandInbox.task_id == task_id,
                    CommandInbox.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                result = _command_dict(existing)
                result["created"] = False
                return result
            turn_index = (
                int(
                    await s.scalar(
                        select(func.coalesce(func.max(AgentTurn.turn_index), -1)).where(
                            AgentTurn.task_id == task_id
                        )
                    )
                )
                + 1
            )
            turn = AgentTurn(
                id=f"turn_{uuid4().hex}",
                task_id=task_id,
                turn_index=turn_index,
                status="active",
                input_payload=dict(payload),
            )
            sequence = (
                int(
                    await s.scalar(
                        select(func.coalesce(func.max(CommandInbox.sequence), 0)).where(
                            CommandInbox.task_id == task_id
                        )
                    )
                    or 0
                )
                + 1
            )
            command = CommandInbox(
                id=f"cmd_{uuid4().hex}",
                task_id=task_id,
                turn_id=turn.id,
                sequence=sequence,
                kind=kind,
                idempotency_key=idempotency_key,
                payload=dict(payload),
            )
            s.add_all([turn, command])
            try:
                await s.commit()
            except IntegrityError:
                await s.rollback()
                existing = await s.scalar(
                    select(CommandInbox).where(
                        CommandInbox.task_id == task_id,
                        CommandInbox.idempotency_key == idempotency_key,
                    )
                )
                if existing is None:
                    # A concurrent database may have committed the task's
                    # counters between the initial read and flush.  Re-read
                    # the high-water marks once after rollback and retry the
                    # insert with fresh immutable IDs.
                    retry_turn_index = (
                        int(
                            await s.scalar(
                                select(func.coalesce(func.max(AgentTurn.turn_index), -1)).where(
                                    AgentTurn.task_id == task_id
                                )
                            )
                        )
                        + 1
                    )
                    retry_turn = AgentTurn(
                        id=f"turn_{uuid4().hex}",
                        task_id=task_id,
                        turn_index=retry_turn_index,
                        status="active",
                        input_payload=dict(payload),
                    )
                    retry_sequence = (
                        int(
                            await s.scalar(
                                select(func.coalesce(func.max(CommandInbox.sequence), 0)).where(
                                    CommandInbox.task_id == task_id
                                )
                            )
                            or 0
                        )
                        + 1
                    )
                    retry_command = CommandInbox(
                        id=f"cmd_{uuid4().hex}",
                        task_id=task_id,
                        turn_id=retry_turn.id,
                        sequence=retry_sequence,
                        kind=kind,
                        idempotency_key=idempotency_key,
                        payload=dict(payload),
                    )
                    s.add_all([retry_turn, retry_command])
                    await s.commit()
                    result = _command_dict(retry_command)
                    result["created"] = True
                    return result
                result = _command_dict(existing)
                result["created"] = False
                return result
            result = _command_dict(command)
            result["created"] = True
            return result

    async def pending_commands(self, task_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(CommandInbox)
                    .where(CommandInbox.task_id == task_id, CommandInbox.consumed_at.is_(None))
                    .order_by(CommandInbox.sequence)
                )
            ).all()
            return [_command_dict(row) for row in rows]

    async def latest_turn(self, task_id: str) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.scalar(
                select(AgentTurn)
                .where(AgentTurn.task_id == task_id)
                .order_by(AgentTurn.turn_index.desc())
            )
            if row is None:
                return None
            return {
                "id": row.id,
                "turn_index": row.turn_index,
                "status": row.status,
                "phase": row.phase,
                "goal_status": row.goal_status,
                "execution_mode": row.execution_mode,
                "revision": int(row.revision or 0),
            }

    async def update_turn(
        self,
        *,
        turn_id: str,
        status: str,
        phase: str,
        goal_status: str = "open",
        execution_mode: str | None = None,
    ) -> bool:
        async with self.db.session() as s:
            row = await s.get(AgentTurn, turn_id)
            if row is None:
                return False
            row.status = status
            row.phase = phase
            row.goal_status = goal_status
            if execution_mode is not None:
                row.execution_mode = execution_mode
            await s.commit()
            return True

    async def consume_command(self, command_id: str) -> bool:
        async with self.db.session() as s:
            result = await s.execute(
                update(CommandInbox)
                .where(CommandInbox.id == command_id, CommandInbox.consumed_at.is_(None))
                .values(consumed_at=utcnow())
            )
            await s.commit()
            return bool(getattr(result, "rowcount", 0))

    async def create_work_plan(
        self,
        *,
        task_id: str,
        turn_id: str,
        expected_revision: int,
        items: list[dict[str, Any]],
        dependencies: Sequence[tuple[str, str]] = (),
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """CAS-submit work and dependencies as one short transaction."""

        async with self.db.session() as s:
            # Serialize reservations for a task at the database level.  The
            # in-memory Budget object is only a projection; outstanding
            # reservations and settled usage across all revisions are the
            # authoritative ledger.
            task = await s.scalar(
                select(AgentTask).where(AgentTask.id == task_id).with_for_update()
            )
            if task is None:
                return None
            turn = await s.scalar(
                select(AgentTurn)
                .where(AgentTurn.id == turn_id, AgentTurn.task_id == task_id)
                .with_for_update()
            )
            if turn is None or int(turn.revision or 0) != int(expected_revision):
                return None
            revision = int(expected_revision) + 1
            reservation = {
                "tokens": sum(int(item.get("reserved_tokens") or 0) for item in items),
                "heavy": sum(int(item.get("reserved_heavy") or 0) for item in items),
                "wall_ms": sum(int(item.get("reserved_wall_ms") or 0) for item in items),
            }
            if budget is not None and any(reservation.values()):
                ledger = await s.scalar(
                    select(BudgetLedger)
                    .where(
                        BudgetLedger.task_id == task_id,
                        BudgetLedger.turn_id == turn_id,
                        BudgetLedger.plan_revision == revision,
                    )
                    .with_for_update()
                )
                if ledger is None:
                    ledger = BudgetLedger(
                        id=f"budget_{uuid4().hex}",
                        task_id=task_id,
                        turn_id=turn_id,
                        plan_revision=revision,
                    )
                    s.add(ledger)
                totals = (
                    await s.execute(
                        select(
                            func.coalesce(func.sum(BudgetLedger.reserved_tokens), 0),
                            func.coalesce(func.sum(BudgetLedger.used_tokens), 0),
                            func.coalesce(func.sum(BudgetLedger.reserved_heavy), 0),
                            func.coalesce(func.sum(BudgetLedger.used_heavy), 0),
                            func.coalesce(func.sum(BudgetLedger.reserved_wall_ms), 0),
                            func.coalesce(func.sum(BudgetLedger.used_wall_ms), 0),
                        ).where(BudgetLedger.task_id == task_id)
                    )
                ).one()
                consumed = {
                    "tokens": int(totals[0] or 0) + int(totals[1] or 0),
                    "heavy": int(totals[2] or 0) + int(totals[3] or 0),
                    "wall_ms": int(totals[4] or 0) + int(totals[5] or 0),
                }
                limits = {
                    "tokens": max(0, int(budget.get("token_budget") or 0)),
                    "heavy": max(0, int(budget.get("max_heavy_artifacts") or 0)),
                    "wall_ms": max(0, int(budget.get("wall_ms_budget") or 0)),
                }
                if any(consumed[key] + reservation[key] > limits[key] for key in reservation):
                    await s.rollback()
                    return {"budget_exceeded": True, "reservation": reservation}
                ledger.reserved_tokens = reservation["tokens"]
                ledger.reserved_heavy = reservation["heavy"]
                ledger.reserved_wall_ms = reservation["wall_ms"]
            created: list[WorkItem] = []
            snapshotted_candidates: set[str] = set()
            for raw in items:
                item = WorkItem(
                    id=str(raw.get("id") or f"work_{uuid4().hex}"),
                    task_id=task_id,
                    turn_id=turn_id,
                    work_key=str(raw.get("work_key") or raw.get("id") or uuid4().hex),
                    plan_revision=revision,
                    candidate_id=str(raw.get("candidate_id") or ""),
                    capability=str(raw.get("capability") or ""),
                    skill_id=str(raw.get("skill_id") or ""),
                    skill_version=str(raw.get("skill_version") or ""),
                    skill_checksum=str(raw.get("skill_checksum") or ""),
                    provider=str(raw.get("provider") or ""),
                    knowledge_point_id=str(raw.get("knowledge_point_id") or ""),
                    input_payload=dict(raw.get("input_payload") or {}),
                    idempotency_key=str(
                        raw.get("idempotency_key") or f"{turn_id}:{raw.get('id') or uuid4().hex}"
                    ),
                    status=str(raw.get("status") or "queued"),
                    reserved_tokens=int(raw.get("reserved_tokens") or 0),
                    reserved_heavy=int(raw.get("reserved_heavy") or 0),
                    reserved_wall_ms=int(raw.get("reserved_wall_ms") or 0),
                    confirmation_digest=str(raw.get("confirmation_digest") or "") or None,
                )
                created.append(item)
                s.add(item)
                if item.candidate_id and item.candidate_id not in snapshotted_candidates:
                    snapshotted_candidates.add(item.candidate_id)
                    s.add(
                        CandidateSnapshot(
                            id=f"candidate_snapshot_{uuid4().hex}",
                            task_id=task_id,
                            turn_id=turn_id,
                            plan_revision=revision,
                            candidate_id=item.candidate_id,
                            capability=item.capability,
                            knowledge_point_id=item.knowledge_point_id,
                            skill_id=item.skill_id,
                            skill_version=item.skill_version,
                            skill_checksum=item.skill_checksum,
                            provider=item.provider,
                            registry_snapshot={
                                "candidate_id": item.candidate_id,
                                "skill_id": item.skill_id,
                                "skill_version": item.skill_version,
                                "skill_checksum": item.skill_checksum,
                                "provider": item.provider,
                            },
                        )
                    )
            # Flush the newly-created work items before inserting dependency
            # rows. PostgreSQL enforces both dependency foreign keys at the
            # statement boundary, and these independent ORM objects do not
            # otherwise guarantee insert ordering.
            await s.flush()
            turn.revision = revision
            for work_id, dependency_id in dependencies:
                s.add(WorkDependency(work_id=work_id, depends_on_id=dependency_id))
            await s.commit()
            return {"revision": revision, "work_items": [_work_dict(item) for item in created]}

    async def reserve_budget(
        self,
        *,
        task_id: str,
        turn_id: str,
        plan_revision: int,
        tokens: int,
        heavy: int,
        wall_ms: int,
        limits: dict[str, int],
    ) -> bool:
        """Atomically reserve remaining budget for work outside plan creation."""
        async with self.db.session() as s:
            row = await s.scalar(
                select(BudgetLedger)
                .where(
                    BudgetLedger.task_id == task_id,
                    BudgetLedger.turn_id == turn_id,
                    BudgetLedger.plan_revision == plan_revision,
                )
                .with_for_update()
            )
            if row is None:
                row = BudgetLedger(
                    id=f"budget_{uuid4().hex}",
                    task_id=task_id,
                    turn_id=turn_id,
                    plan_revision=plan_revision,
                )
                s.add(row)
            if (
                int(row.reserved_tokens or 0) + tokens + int(row.used_tokens or 0)
                > limits.get("tokens", 0)
                or int(row.reserved_heavy or 0) + heavy + int(row.used_heavy or 0)
                > limits.get("heavy", 0)
                or int(row.reserved_wall_ms or 0) + wall_ms + int(row.used_wall_ms or 0)
                > limits.get("wall_ms", 0)
            ):
                await s.rollback()
                return False
            row.reserved_tokens = int(row.reserved_tokens or 0) + max(0, tokens)
            row.reserved_heavy = int(row.reserved_heavy or 0) + max(0, heavy)
            row.reserved_wall_ms = int(row.reserved_wall_ms or 0) + max(0, wall_ms)
            await s.commit()
            return True

    async def settle_budget(
        self,
        *,
        task_id: str,
        turn_id: str,
        plan_revision: int,
        reserved_tokens: int,
        reserved_heavy: int,
        reserved_wall_ms: int,
        used_tokens: int,
        used_heavy: int,
        used_wall_ms: int,
    ) -> bool:
        async with self.db.session() as s:
            row = await s.scalar(
                select(BudgetLedger)
                .where(
                    BudgetLedger.task_id == task_id,
                    BudgetLedger.turn_id == turn_id,
                    BudgetLedger.plan_revision == plan_revision,
                )
                .with_for_update()
            )
            if row is None:
                return False
            row.reserved_tokens = max(0, int(row.reserved_tokens or 0) - max(0, reserved_tokens))
            row.reserved_heavy = max(0, int(row.reserved_heavy or 0) - max(0, reserved_heavy))
            row.reserved_wall_ms = max(0, int(row.reserved_wall_ms or 0) - max(0, reserved_wall_ms))
            row.used_tokens = int(row.used_tokens or 0) + max(0, used_tokens)
            row.used_heavy = int(row.used_heavy or 0) + max(0, used_heavy)
            row.used_wall_ms = int(row.used_wall_ms or 0) + max(0, used_wall_ms)
            await s.commit()
            return True

    async def claim_work(self, *, owner: str, lease_seconds: int = 60) -> dict[str, Any] | None:
        """Claim only queued work whose dependencies all succeeded."""

        moment = utcnow()
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(WorkItem)
                    .where(
                        (WorkItem.status == "queued")
                        | ((WorkItem.status == "leased") & (WorkItem.lease_until < moment))
                    )
                    .order_by(WorkItem.created_at)
                    .limit(32)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for row in rows:
                dependency_ids = list(
                    await s.scalars(
                        select(WorkDependency.depends_on_id).where(WorkDependency.work_id == row.id)
                    )
                )
                if dependency_ids:
                    states = list(
                        await s.scalars(
                            select(WorkItem.status).where(WorkItem.id.in_(dependency_ids))
                        )
                    )
                    if any(state != "succeeded" for state in states):
                        if any(
                            state in {"failed", "incomplete", "blocked", "cancelled"}
                            for state in states
                        ):
                            row.status = "blocked"
                        continue
                result = await s.execute(
                    update(WorkItem)
                    .where(
                        WorkItem.id == row.id,
                        (
                            (WorkItem.status == "queued")
                            | (
                                (WorkItem.status == "leased")
                                & (WorkItem.lease_until < moment)
                            )
                        ),
                    )
                    .values(
                        status="leased",
                        lease_owner=owner,
                        lease_until=moment + timedelta(seconds=max(1, lease_seconds)),
                        attempts=WorkItem.attempts + 1,
                    )
                )
                if int(getattr(result, "rowcount", 0) or 0) != 1:
                    continue
                await s.commit()
                await s.refresh(row)
                return _work_dict(row)
            await s.commit()
            return None

    async def claim_work_item(
        self, *, work_id: str, owner: str, lease_seconds: int = 60
    ) -> dict[str, Any] | None:
        """Claim a specific ledger row after rechecking its dependencies."""

        moment = utcnow()
        async with self.db.session() as s:
            row = await s.scalar(select(WorkItem).where(WorkItem.id == work_id).with_for_update())
            if row is None or row.status not in {"queued", "leased"}:
                return None
            if (
                row.status == "leased"
                and row.lease_until
                and _utc_datetime(row.lease_until) >= moment
            ):
                return None
            dependency_ids = list(
                await s.scalars(
                    select(WorkDependency.depends_on_id).where(WorkDependency.work_id == row.id)
                )
            )
            if dependency_ids:
                states = list(
                    await s.scalars(select(WorkItem.status).where(WorkItem.id.in_(dependency_ids)))
                )
                if any(state != "succeeded" for state in states):
                    if any(
                        state in {"failed", "incomplete", "blocked", "cancelled"}
                        for state in states
                    ):
                        row.status = "blocked"
                        await s.commit()
                    return None
            result = await s.execute(
                update(WorkItem)
                .where(
                    WorkItem.id == row.id,
                    (
                        (WorkItem.status == "queued")
                        | ((WorkItem.status == "leased") & (WorkItem.lease_until < moment))
                    ),
                )
                .values(
                    status="leased",
                    lease_owner=owner,
                    lease_until=moment + timedelta(seconds=max(1, lease_seconds)),
                    attempts=WorkItem.attempts + 1,
                )
            )
            if int(getattr(result, "rowcount", 0) or 0) != 1:
                await s.rollback()
                return None
            await s.commit()
            async with self.db.session() as refreshed_session:
                refreshed = await refreshed_session.get(WorkItem, work_id)
                return _work_dict(refreshed) if refreshed is not None else None

    async def heartbeat_work(self, *, work_id: str, owner: str, lease_seconds: int = 60) -> bool:
        """Extend a live lease without changing work status or ownership."""
        moment = utcnow()
        async with self.db.session() as s:
            row = await s.scalar(select(WorkItem).where(WorkItem.id == work_id))
            if row is None or row.status != "leased" or row.lease_owner != owner:
                return False
            if row.lease_until is not None and _utc_datetime(row.lease_until) < moment:
                return False
            row.lease_until = moment + timedelta(seconds=max(1, lease_seconds))
            await s.commit()
            return True

    async def recover_expired_work(self, *, limit: int = 100) -> int:
        """Requeue expired leases; dependency failures are blocked eagerly."""
        moment = utcnow()
        recovered = 0
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(WorkItem)
                    .where(WorkItem.status == "leased", WorkItem.lease_until < moment)
                    .limit(limit)
                )
            ).all()
            for row in rows:
                dependencies = list(
                    await s.scalars(
                        select(WorkDependency.depends_on_id).where(WorkDependency.work_id == row.id)
                    )
                )
                states = (
                    list(
                        await s.scalars(
                            select(WorkItem.status).where(WorkItem.id.in_(dependencies))
                        )
                    )
                    if dependencies
                    else []
                )
                row.status = (
                    "blocked"
                    if any(
                        state in {"failed", "incomplete", "blocked", "cancelled"}
                        for state in states
                    )
                    else "queued"
                )
                row.lease_owner = None
                row.lease_until = None
                recovered += 1
            await s.commit()
        return recovered

    async def cancel_work(self, *, task_id: str, work_id: str) -> bool:
        async with self.db.session() as s:
            row = await s.scalar(
                select(WorkItem).where(WorkItem.id == work_id, WorkItem.task_id == task_id)
            )
            if row is None or row.status in {"succeeded", "failed", "cancelled"}:
                return False
            row.status = "cancelled"
            row.lease_owner = None
            row.lease_until = None
            ledger = await s.scalar(
                select(BudgetLedger).where(
                    BudgetLedger.task_id == row.task_id,
                    BudgetLedger.turn_id == row.turn_id,
                    BudgetLedger.plan_revision == row.plan_revision,
                )
            )
            if ledger is not None:
                ledger.reserved_tokens = max(
                    0, int(ledger.reserved_tokens or 0) - int(row.reserved_tokens or 0)
                )
                ledger.reserved_heavy = max(
                    0, int(ledger.reserved_heavy or 0) - int(row.reserved_heavy or 0)
                )
                ledger.reserved_wall_ms = max(
                    0, int(ledger.reserved_wall_ms or 0) - int(row.reserved_wall_ms or 0)
                )
            await s.commit()
            return True

    async def finish_work(
        self,
        *,
        work_id: str,
        owner: str,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> bool:
        async with self.db.session() as s:
            item = await s.scalar(select(WorkItem).where(WorkItem.id == work_id))
            if item is None or item.lease_owner != owner or item.status != "leased":
                return False
            item.status = status
            item.lease_owner = None
            item.lease_until = None
            if result is not None:
                result_id = f"result_{uuid4().hex}"
                s.add(
                    WorkResult(
                        id=result_id,
                        work_id=item.id,
                        schema_id=str(result.get("schema_id") or ""),
                        safe_summary=str(result.get("safe_summary") or ""),
                        artifact_refs=list(result.get("artifact_refs") or []),
                        evidence_refs=list(result.get("evidence_refs") or []),
                        usage=dict(result.get("usage") or {}),
                        output_payload=dict(result.get("output_payload") or {}),
                        error_code=str(result.get("error_code") or ""),
                    )
                )
                item.result_id = result_id
                usage = dict(result.get("usage") or {})
                ledger = await s.scalar(
                    select(BudgetLedger).where(
                        BudgetLedger.task_id == item.task_id,
                        BudgetLedger.turn_id == item.turn_id,
                        BudgetLedger.plan_revision == item.plan_revision,
                    )
                )
                if ledger is not None:
                    ledger.reserved_tokens = max(
                        0, int(ledger.reserved_tokens or 0) - int(item.reserved_tokens or 0)
                    )
                    ledger.reserved_heavy = max(
                        0, int(ledger.reserved_heavy or 0) - int(item.reserved_heavy or 0)
                    )
                    ledger.reserved_wall_ms = max(
                        0, int(ledger.reserved_wall_ms or 0) - int(item.reserved_wall_ms or 0)
                    )
                    ledger.used_tokens = int(ledger.used_tokens or 0) + int(
                        usage.get("tokens") or 0
                    )
                    ledger.used_heavy = int(ledger.used_heavy or 0) + int(usage.get("heavy") or 0)
                    ledger.used_wall_ms = int(ledger.used_wall_ms or 0) + int(
                        usage.get("wall_ms") or 0
                    )
            await s.commit()
            return True

    async def get_work(self, *, task_id: str, work_id: str) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.scalar(
                select(WorkItem).where(WorkItem.id == work_id, WorkItem.task_id == task_id)
            )
            return _work_dict(row) if row is not None else None

    async def list_work(self, task_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(WorkItem)
                    .where(WorkItem.task_id == task_id)
                    .order_by(WorkItem.created_at)
                )
            ).all()
            return [_work_dict(row) for row in rows]

    async def confirm_work(self, *, work_id: str, payload_digest: str, approve: bool) -> bool:
        async with self.db.session() as s:
            item = await s.scalar(select(WorkItem).where(WorkItem.id == work_id))
            if (
                item is None
                or item.status != "waiting_confirmation"
                or item.confirmation_digest != payload_digest
            ):
                return False
            item.status = "queued" if approve else "cancelled"
            item.confirmed_at = utcnow() if approve else None
            if not approve:
                ledger = await s.scalar(
                    select(BudgetLedger).where(
                        BudgetLedger.task_id == item.task_id,
                        BudgetLedger.turn_id == item.turn_id,
                        BudgetLedger.plan_revision == item.plan_revision,
                    )
                )
                if ledger is not None:
                    ledger.reserved_tokens = max(
                        0, int(ledger.reserved_tokens or 0) - int(item.reserved_tokens or 0)
                    )
                    ledger.reserved_heavy = max(
                        0, int(ledger.reserved_heavy or 0) - int(item.reserved_heavy or 0)
                    )
                    ledger.reserved_wall_ms = max(
                        0, int(ledger.reserved_wall_ms or 0) - int(item.reserved_wall_ms or 0)
                    )
            await s.commit()
            return approve

    async def append_outbox(
        self,
        *,
        event_key: str,
        task_id: str,
        turn_id: str,
        plan_revision: int,
        kind: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        async with self.db.session() as s:
            row = await s.scalar(
                select(TransactionalOutbox).where(TransactionalOutbox.event_key == event_key)
            )
            if row is None:
                row = TransactionalOutbox(
                    id=f"outbox_{uuid4().hex}",
                    event_key=event_key,
                    task_id=task_id,
                    turn_id=turn_id,
                    plan_revision=plan_revision,
                    kind=kind,
                    safe_payload=dict(payload),
                )
                s.add(row)
                await s.commit()
            return {
                "id": row.id,
                "event_key": row.event_key,
                "kind": row.kind,
                "payload": dict(row.safe_payload),
                "published_at": row.published_at,
            }

    async def save_fact_snapshot(
        self,
        *,
        task_id: str,
        turn_id: str,
        plan_revision: int,
        facts: dict[str, Any],
        evidence_refs: list[str] | None = None,
        artifact_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        async with self.db.session() as s:
            row = await s.scalar(
                select(FactSnapshot).where(
                    FactSnapshot.task_id == task_id,
                    FactSnapshot.turn_id == turn_id,
                    FactSnapshot.plan_revision == plan_revision,
                )
            )
            if row is None:
                row = FactSnapshot(
                    id=f"facts_{uuid4().hex}",
                    task_id=task_id,
                    turn_id=turn_id,
                    plan_revision=plan_revision,
                    facts=dict(facts),
                    evidence_refs=list(evidence_refs or []),
                    artifact_refs=list(artifact_refs or []),
                )
                s.add(row)
                await s.commit()
            return {
                "id": row.id,
                "facts": dict(row.facts),
                "evidence_refs": list(row.evidence_refs),
                "artifact_refs": list(row.artifact_refs),
            }

    # -- knowledge graphs -----------------------------------------------

    # Knowledge Graph persistence was removed; runtime graphs live on AgentExecution.
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
        session_record = await self.get_session(session_id)
        if session_record is None:
            raise KeyError(f"unknown session: {session_id}")
        await self.ensure_workspace(session_record.learner_id)
        async with self.db.session() as s:
            session = await s.get(Session, session_id)
            if session is None:
                raise KeyError(f"unknown session: {session_id}")
            session_learner_id = session.learner_id
            highest = (
                await s.execute(
                    select(func.max(RunEvent.sequence)).where(RunEvent.session_id == session_id)
                )
            ).scalar() or 0
            runtime_records: list[dict[str, Any]] = []
            for offset, event in enumerate(events, start=1):
                sequence = highest + offset
                s.add(
                    RunEvent(
                        session_id=session_id,
                        sequence=sequence,
                        kind=str(event.get("kind", "")),
                        node=str(event.get("node") or ""),
                        payload=event.get("payload") or {},
                    )
                )
                runtime_records.append(
                    {
                        "record_key": f"session:{session_id}:{sequence}",
                        "session_id": session_id,
                        "sequence": sequence,
                        "kind": str(event.get("kind", "")),
                        "agent": str(event.get("node") or event.get("agent") or ""),
                        "payload": event.get("payload") or {},
                        "runtime": (event.get("payload") or {}).get("runtime") or {},
                    }
                )
            await project_runtime_events(
                s,
                learner_id=session_learner_id,
                records=runtime_records,
                workspace=await s.scalar(
                    select(Workspace).where(Workspace.learner_id == session_learner_id)
                ),
            )
            await s.commit()
            return highest + len(events)

    async def project_runtime_event(
        self,
        *,
        learner_id: str,
        record_key: str,
        kind: str,
        task_id: str = "",
        session_id: str = "",
        sequence: int = 0,
        agent: str = "",
        payload: dict[str, Any] | None = None,
        runtime: dict[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> dict[str, Any]:
        """Project an externally replayed event using the same runtime path."""

        await self.ensure_workspace(learner_id)
        async with self.db.session() as s:
            workspace = await s.scalar(select(Workspace).where(Workspace.learner_id == learner_id))
            result = await project_runtime_events(
                s,
                learner_id=learner_id,
                records=[
                    {
                        "record_key": record_key,
                        "task_id": task_id,
                        "session_id": session_id,
                        "sequence": sequence,
                        "kind": kind,
                        "agent": agent,
                        "payload": payload or {},
                        "runtime": runtime or {},
                        "execution_id": execution_id,
                    }
                ],
                workspace=workspace,
            )
            await s.commit()
            return result[0]

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


def interaction_resolved_event_key(interaction_id: str) -> str:
    """Outbox key for one interaction's public ``resolved`` fact.

    Unique per interaction, so a retried answer can only ever repair the same
    row — never publish a second resolved event.
    """

    return f"interaction:{interaction_id}:resolved"


def _interaction_command_key(interaction_id: str, idempotency_key: str) -> str:
    """Command-ledger key for one interaction answer.

    Namespaced by interaction so a learner's own idempotency key cannot
    collide with a message command's key on the same task.
    """

    return f"interaction:{interaction_id}:{idempotency_key}"


def _command_dict(row: CommandInbox) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "turn_id": row.turn_id,
        "sequence": int(row.sequence or 0),
        "kind": row.kind,
        "idempotency_key": row.idempotency_key,
        "payload": dict(row.payload or {}),
        "consumed_at": row.consumed_at.isoformat() if row.consumed_at else None,
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
        "protocol_version": int(row.protocol_version or 0),
        "turn_id": row.turn_id,
        "agent_run_id": row.agent_run_id,
        "skill_run_id": row.skill_run_id,
        "ts": row.created_at.isoformat() if row.created_at else None,
    }


def _agent_run_dict(row: AgentRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "turn_id": row.turn_id,
        "execution_id": row.execution_id,
        "work_item_id": row.work_item_id,
        "parent_agent_run_id": row.parent_agent_run_id,
        "provider_id": row.provider_id,
        "agent_display_name": row.agent_display_name,
        "execution_kind": row.execution_kind,
        "capability": row.capability,
        "presentation_role": row.presentation_role,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "start_sequence": row.start_sequence,
        "end_sequence": row.end_sequence,
        "metadata": dict(row.safe_metadata or {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _skill_run_dict(row: SkillRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "agent_run_id": row.agent_run_id,
        "task_id": row.task_id,
        "turn_id": row.turn_id,
        "execution_id": row.execution_id,
        "skill_id": row.skill_id,
        "display_name": row.display_name,
        "version": row.version,
        "checksum": row.checksum,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _interaction_dict(row: AgentInteraction) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "turn_id": row.turn_id,
        "execution_id": row.execution_id,
        "agent_run_id": row.agent_run_id,
        "purpose": row.purpose,
        "presentation": row.presentation,
        "blocking": bool(row.blocking),
        "request_payload": dict(row.request_payload or {}),
        "status": row.status,
        "reason_code": row.reason_code,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }


def _work_dict(row: WorkItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "turn_id": row.turn_id,
        "work_key": row.work_key,
        "plan_revision": int(row.plan_revision or 0),
        "candidate_id": row.candidate_id,
        "capability": row.capability,
        "skill_id": row.skill_id,
        "skill_version": row.skill_version,
        "skill_checksum": row.skill_checksum,
        "provider": row.provider,
        "knowledge_point_id": row.knowledge_point_id,
        "input_payload": dict(row.input_payload or {}),
        "status": row.status,
        "idempotency_key": row.idempotency_key,
        "attempts": int(row.attempts or 0),
        "lease_owner": row.lease_owner,
        "lease_until": row.lease_until.isoformat() if row.lease_until else None,
        "reserved_tokens": int(row.reserved_tokens or 0),
        "reserved_heavy": int(row.reserved_heavy or 0),
        "reserved_wall_ms": int(row.reserved_wall_ms or 0),
        "confirmation_digest": row.confirmation_digest,
        "result_id": row.result_id,
    }
