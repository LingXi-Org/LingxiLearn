"""Engine, session factory and the repository.

One rule worth stating because breaking it is the classic scaling mistake:
**never hold a database session open across a graph run.**  Resolve what you
need, release the connection, then stream.  A pool of 10 gated on model latency
caps you at 10 concurrent learners for no reason.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import delete, event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import Settings
from .models import (
    AgentTask,
    AgentTaskEvent,
    Base,
    Learner,
    Mastery,
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

    async def get_session_for_learner(
        self, session_id: str, learner_id: str
    ) -> Session | None:
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

    async def get_agent_task(self, task_id: str) -> AgentTask | None:
        async with self.db.session() as s:
            return await s.get(AgentTask, task_id)

    async def get_agent_task_for_learner(
        self, task_id: str, learner_id: str
    ) -> AgentTask | None:
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
            elif agent == "visual_explainer":
                row.visual_result = value
            else:
                raise ValueError(f"unknown agent output: {agent}")
            row.updated_at = utcnow()
            await s.commit()

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
                    "ts": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

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
                    "ts": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

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
