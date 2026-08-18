"""Learning session persistence: sessions, run events, reports."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select

from ..database import Database
from ..models.base import utcnow
from ..models.learning import ReportRecord, RunEvent, Session
from ..models.workspace import Workspace
from ..runtime_tables import project_runtime_events


class SessionRepository:
    """Learning-session persistence. Each method owns a short transaction."""

    def __init__(self, db: Database) -> None:
        self.db = db

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
