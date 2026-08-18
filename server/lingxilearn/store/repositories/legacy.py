"""Legacy Repository class - moved from db.py for issue #56.

This is a temporary facade during migration to domain-specific repositories.
Use from lingxilearn.store.repositories import Repository for backward compatibility.
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
from .database import Database
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


class Repository:
    """Legacy data access class - moved from db.py during issue #56 refactoring.
    
    This provides backward compatibility while we migrate to domain-specific
    repositories. Each method opens and closes its own short transaction.
    """

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
        async with self.db.session() as s:
            row = await s.scalar(
                select(AgentTask).where(
                    AgentTask.id == task_id,
                    AgentTask.learner_id == learner_id,
                )
            )
            if row is None:
                return None
            if row.status != "queued":
                return None
            row.status = "running"
            row.updated_at = utcnow()
            await s.commit()
            await s.refresh(row)
            return row

    async def update_agent_task_output(
        self, task_id: str, agent: str, value: Any
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
                    "thread_status": row.thread_status,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in rows
            ]

    # -- Events -----------------------------------------------------------

    async def append_agent_events(self, task_id: str, events: Sequence[dict[str, Any]]) -> None:
        async with self.db.agent_event_lock(task_id):
            async with self.db.session() as s:
                task = await s.get(AgentTask, task_id)
                if task is None:
                    return
                await self._write_agent_event_rows(s, task, events)
                await s.commit()

    async def _write_agent_event_rows(
        self, s: AsyncSession, task: AgentTask, events: Sequence[dict[str, Any]]
    ) -> None:
        last_seq = (
            await s.scalar(
                select(func.max(AgentTaskEvent.sequence)).where(
                    AgentTaskEvent.task_id == task.id
                )
            )
            or 0
        )
        for ev in events:
            last_seq += 1
            s.add(
                AgentTaskEvent(
                    task_id=task.id,
                    sequence=last_seq,
                    kind=ev.get("kind", "unknown"),
                    agent=ev.get("agent", ""),
                    runtime=ev.get("payload", {}),
                    execution_id=ev.get("execution_id"),
                    protocol_version=ev.get("protocol_version", 0),
                    turn_id=ev.get("turn_id"),
                    agent_run_id=ev.get("agent_run_id"),
                    skill_run_id=ev.get("skill_run_id"),
                )
            )

    async def agent_events_after(self, task_id: str, after_sequence: int = 0) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(AgentTaskEvent)
                    .where(AgentTaskEvent.task_id == task_id)
                    .where(AgentTaskEvent.sequence > after_sequence)
                    .order_by(AgentTaskEvent.sequence)
                )
            ).scalars()
            return [
                {
                    "sequence": r.sequence,
                    "kind": r.kind,
                    "agent": r.agent,
                    "runtime": r.runtime,
                    "execution_id": r.execution_id,
                    "protocol_version": r.protocol_version,
                    "turn_id": r.turn_id,
                    "agent_run_id": r.agent_run_id,
                    "skill_run_id": r.skill_run_id,
                }
                for r in rows
            ]

    async def append_events(self, session_id: str, events: Sequence[dict[str, Any]]) -> None:
        async with self.db.session() as s:
            last_seq = (
                await s.scalar(
                    select(func.max(RunEvent.sequence)).where(RunEvent.session_id == session_id)
                )
                or 0
            )
            for ev in events:
                last_seq += 1
                s.add(
                    RunEvent(
                        session_id=session_id,
                        sequence=last_seq,
                        kind=ev.get("kind", "unknown"),
                        node=ev.get("node", ""),
                        payload=ev.get("payload", {}),
                    )
                )
            await s.commit()

    async def events_after(self, session_id: str, after_sequence: int = 0) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(RunEvent)
                    .where(RunEvent.session_id == session_id)
                    .where(RunEvent.sequence > after_sequence)
                    .order_by(RunEvent.sequence)
                )
            ).scalars()
            return [
                {
                    "sequence": r.sequence,
                    "kind": r.kind,
                    "node": r.node,
                    "payload": r.payload,
                }
                for r in rows
            ]


def _quiz_submission_dict(row: QuizSubmission) -> dict[str, Any]:
    return {
        "task_id": row.task_id,
        "submission_id": row.submission_id,
        "answers": row.answers,
        "per_question": row.per_question,
        "total_score": row.total_score,
        "total_points": row.total_points,
        "handoff_reason": row.handoff_reason,
    }