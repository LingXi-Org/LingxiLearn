"""Data access for the four state tables.

Kept out of the domain repositories deliberately: the state layer has one rule
the rest of the package does not — evidence is append-only and the profile has
exactly one writer.  Holding those two invariants in one small module makes
them auditable.

Same transaction discipline as the domain repositories: every
method opens and closes its own short session, and none is held across a graph
run.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..state.evidence import EvidenceRecord
from ..state.profile_writer import ProfileChange, ProfileDelta, ProfileWriter, profile_id
from ..state.session_state import (
    GoalStack,
    RuntimeStatus,
    StackOperation,
    new_budget,
    transition,
)
from ..state.skill_catalog import SkillManifest
from .database import Database
from .models.agent import ProjectionCursor
from .models.learning import (
    DecisionTrace,
    LearningEvidence,
    LearningProfile,
    SessionState,
    SessionStateEvent,
)
from .models.runtime import SkillRegistryEntry

logger = logging.getLogger(__name__)

_EVIDENCE_SEQ_RETRIES = 4


def evidence_dict(row: LearningEvidence) -> dict[str, Any]:
    return {
        "id": row.id,
        "learner_id": row.learner_id,
        "session_id": row.session_id,
        "task_id": row.task_id,
        "evidence_id": row.evidence_id,
        "kind": row.kind,
        "source": row.source,
        "summary": row.summary,
        "locator": row.locator or {},
        "value": row.value,
        "digest": row.digest,
        "knowledge_point": row.knowledge_point,
        "signal": row.signal,
        "source_agent": row.source_agent,
        "payload": row.payload or {},
        "seq": row.seq,
        "observed_at": row.observed_at.isoformat() if row.observed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def profile_dict(row: LearningProfile) -> dict[str, Any]:
    """The learner-facing shape: user columns first, system columns under ``system``."""

    return {
        "knowledge_point_id": row.knowledge_point_id,
        "knowledge_point": row.knowledge_point,
        "mastery": round(float(row.mastery or 0.0), 4),
        "learning_state": row.learning_state,
        "progress": round(float(row.progress or 0.0), 4),
        "my_questions": list(row.my_questions or []),
        "recent_performance": dict(row.recent_performance or {}),
        "last_studied_at": row.last_studied_at.isoformat() if row.last_studied_at else None,
        "review_due_at": row.review_due_at.isoformat() if row.review_due_at else None,
        "next_step": dict(row.next_step or {}),
        "system": {
            "confidence": round(float(row.confidence or 0.0), 4),
            "evidence_count": int(row.evidence_count or 0),
            "misconceptions": list(row.misconceptions or []),
            "prerequisites": list(row.prerequisites or []),
            "difficulty": round(float(row.difficulty or 0.0), 4),
            "review_priority": round(float(row.review_priority or 0.0), 4),
            "stability": round(float(row.stability or 0.0), 4),
            "source_agent": row.source_agent,
            "revision": int(row.revision or 0),
            "override_flag": bool(row.override_flag),
            "last_evidence_seq": int(row.last_evidence_seq or 0),
        },
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def session_state_dict(row: SessionState) -> dict[str, Any]:
    return {
        "id": row.id,
        "learner_id": row.learner_id,
        "task_id": row.task_id,
        "session_id": row.session_id,
        "runtime_status": row.runtime_status,
        "goal_stack": list(row.goal_stack or []),
        "plan": dict(row.plan or {}),
        "budget": dict(row.budget or {}),
        "board": dict(row.board or {}),
        "revision": int(row.revision or 0),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def skill_dict(row: SkillRegistryEntry) -> dict[str, Any]:
    return {
        "skill_id": row.skill_id,
        "source": row.source,
        "learner_id": row.learner_id,
        "display_name": row.display_name,
        "description": row.description,
        "capabilities": list(row.capabilities or []),
        "input_schema": dict(row.input_schema or {}),
        "output_schema": dict(row.output_schema or {}),
        "preconditions": dict(row.preconditions or {}),
        "cost": dict(row.cost or {}),
        "ownership": row.ownership,
        "provider": row.provider,
        "version": row.version,
        "enabled": bool(row.enabled),
        "checksum": row.checksum,
        "metadata": dict(row.metadata_payload or {}),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def decision_dict(row: DecisionTrace) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "execution_id": row.execution_id,
        "step": int(row.step or 0),
        "goal": dict(row.goal or {}),
        "candidates": list(row.candidates or []),
        "selected": dict(row.selected or {}),
        "rationale": row.rationale,
        "evidence_ids": list(row.evidence_ids or []),
        "profile_before": dict(row.profile_before or {}),
        "profile_after": dict(row.profile_after or {}),
        "guardrail_state": dict(row.guardrail_state or {}),
        "outcome": dict(row.outcome or {}),
        "replan_of": row.replan_of,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


class RuntimeStateRepository:
    """Reads and writes for ``learning_profile`` / ``learning_evidence`` /
    ``session_state`` / ``skill_registry`` / ``decision_trace``."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._projection_locks: dict[tuple[str, str], asyncio.Lock] = {}

    def projection_lock(
        self, learner_id: str, projection: str = "learning_profile"
    ) -> asyncio.Lock:
        """Return the per-projection process lock used during a fold.

        The cursor is durable (and therefore survives a restart); this lock is
        only a fast path that prevents two local workers from folding the same
        batch concurrently.
        """
        key = (learner_id, projection)
        lock = self._projection_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._projection_locks[key] = lock
        return lock

    async def projection_cursor(self, learner_id: str, projection: str = "learning_profile") -> int:
        async with self.db.session() as s:
            row = await s.scalar(
                select(ProjectionCursor).where(
                    ProjectionCursor.learner_id == learner_id,
                    ProjectionCursor.projection == projection,
                )
            )
            return int(row.last_event_id or 0) if row else 0

    async def advance_projection_cursor(
        self, learner_id: str, seq: int, projection: str = "learning_profile"
    ) -> None:
        if seq <= 0:
            return
        async with self.db.session() as s:
            row = await s.scalar(
                select(ProjectionCursor).where(
                    ProjectionCursor.learner_id == learner_id,
                    ProjectionCursor.projection == projection,
                )
            )
            if row is None:
                row = ProjectionCursor(
                    id=f"cursor_{uuid4().hex}",
                    learner_id=learner_id,
                    projection=projection,
                    last_event_id=str(seq),
                )
                s.add(row)
            elif int(row.last_event_id or 0) < seq:
                row.last_event_id = str(seq)
            await s.commit()

    # -- learning_evidence (append-only) ------------------------------------

    async def append_evidence(self, records: Sequence[EvidenceRecord]) -> list[dict[str, Any]]:
        """Append structured evidence. There is no update or delete counterpart.

        ``seq`` is assigned per learner as ``max(seq) + 1`` inside the same
        transaction.  A concurrent writer that lands the same number trips the
        ``(learner_id, seq)`` unique constraint; we re-read the high-water mark
        and retry rather than silently reusing a sequence number.
        """

        if not records:
            return []
        for attempt in range(_EVIDENCE_SEQ_RETRIES):
            try:
                return await self._append_evidence_once(records)
            except IntegrityError:
                if attempt == _EVIDENCE_SEQ_RETRIES - 1:
                    raise
                logger.debug("evidence seq collision; retrying", exc_info=True)
        return []

    async def _append_evidence_once(
        self, records: Sequence[EvidenceRecord]
    ) -> list[dict[str, Any]]:
        appended: list[dict[str, Any]] = []
        async with self.db.session() as s:
            next_seq: dict[str, int] = {}
            for record in records:
                learner_id = record.learner_id
                if learner_id not in next_seq:
                    current = await s.scalar(
                        select(func.max(LearningEvidence.seq)).where(
                            LearningEvidence.learner_id == learner_id
                        )
                    )
                    next_seq[learner_id] = int(current or 0)

                row_values = record.to_row()
                scope = row_values["session_id"] or row_values["task_id"] or "global"
                row_id = f"{scope}:{row_values['evidence_id']}"
                existing = await s.get(LearningEvidence, row_id)
                if existing is not None:
                    # Same observation, same content: the ledger already has it.
                    appended.append(evidence_dict(existing))
                    continue

                next_seq[learner_id] += 1
                row = LearningEvidence(id=row_id, seq=next_seq[learner_id], **row_values)
                s.add(row)
                await s.flush()
                appended.append(evidence_dict(row))
            await s.commit()
        return appended

    async def evidence_after(
        self, learner_id: str, seq: int, *, limit: int = 500
    ) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(LearningEvidence)
                    .where(
                        LearningEvidence.learner_id == learner_id,
                        LearningEvidence.seq > int(seq),
                    )
                    .order_by(LearningEvidence.seq)
                    .limit(limit)
                )
            ).scalars()
            return [evidence_dict(row) for row in rows]

    async def evidence_for_task(self, task_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(LearningEvidence)
                    .where(LearningEvidence.task_id == task_id)
                    .order_by(LearningEvidence.seq)
                    .limit(limit)
                )
            ).scalars()
            return [evidence_dict(row) for row in rows]

    # -- learning_profile ----------------------------------------------------

    async def profile_for(self, learner_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(LearningProfile)
                    .where(LearningProfile.learner_id == learner_id)
                    .order_by(
                        LearningProfile.review_priority.desc(),
                        LearningProfile.knowledge_point_id,
                    )
                )
            ).scalars()
            return [profile_dict(row) for row in rows]

    async def profile_rows(
        self, learner_id: str, knowledge_point_ids: Iterable[str]
    ) -> dict[str, LearningProfile]:
        """Detached ORM rows keyed by knowledge point, for the gain scorer."""

        wanted = [str(item) for item in knowledge_point_ids if str(item).strip()]
        if not wanted:
            return {}
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(LearningProfile).where(
                        LearningProfile.learner_id == learner_id,
                        LearningProfile.knowledge_point_id.in_(wanted),
                    )
                )
            ).scalars()
            found = {row.knowledge_point_id: row for row in rows}
            for row in found.values():
                s.expunge(row)
            return found

    async def profile_point(
        self, learner_id: str, knowledge_point_id: str
    ) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.get(LearningProfile, profile_id(learner_id, knowledge_point_id))
            return profile_dict(row) if row else None

    async def apply_profile_deltas(self, deltas: Sequence[ProfileDelta]) -> list[ProfileChange]:
        """The only profile write path exposed to the rest of the service."""

        if not deltas:
            return []
        async with self.db.session() as s:
            changes = await ProfileWriter(s).apply(deltas)
            await s.commit()
        return changes

    async def override_profile(
        self,
        *,
        learner_id: str,
        knowledge_point_id: str,
        enabled: bool,
        fields: dict[str, Any] | None = None,
    ) -> ProfileChange | None:
        async with self.db.session() as s:
            change = await ProfileWriter(s).set_override(
                learner_id=learner_id,
                knowledge_point_id=knowledge_point_id,
                enabled=enabled,
                fields=fields,
            )
            await s.commit()
        return change

    # -- session_state -------------------------------------------------------

    async def ensure_session_state(
        self,
        *,
        learner_id: str,
        task_id: str | None = None,
        session_id: str | None = None,
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self.db.session() as s:
            row = None
            if task_id:
                row = await s.scalar(select(SessionState).where(SessionState.task_id == task_id))
            if row is None:
                row = SessionState(
                    id=f"ss_{uuid4().hex}",
                    learner_id=learner_id,
                    task_id=task_id,
                    session_id=session_id,
                    runtime_status=str(RuntimeStatus.PLANNING),
                    goal_stack=[],
                    plan={},
                    budget=new_budget(budget),
                )
                s.add(row)
                await s.flush()
            snapshot = session_state_dict(row)
            await s.commit()
        return snapshot

    async def get_session_state(self, task_id: str) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.scalar(select(SessionState).where(SessionState.task_id == task_id))
            return session_state_dict(row) if row else None

    async def apply_stack_operation(
        self, task_id: str, operation: StackOperation
    ) -> dict[str, Any] | None:
        """Persist a goal-stack change together with its undo record."""

        if not operation.changed:
            return await self.get_session_state(task_id)
        async with self.db.session() as s:
            row = await s.scalar(select(SessionState).where(SessionState.task_id == task_id))
            if row is None:
                return None
            sequence = int(
                await s.scalar(
                    select(func.count(SessionStateEvent.id)).where(
                        SessionStateEvent.session_state_id == row.id
                    )
                )
                or 0
            )
            s.add(
                SessionStateEvent(
                    id=f"sse_{uuid4().hex}",
                    session_state_id=row.id,
                    sequence=sequence + 1,
                    op=operation.op,
                    before={"goal_stack": operation.before},
                    after={"goal_stack": operation.after},
                    reason=operation.reason,
                )
            )
            row.goal_stack = list(operation.after)
            row.revision = int(row.revision or 0) + 1
            row.updated_at = datetime.now(UTC)
            snapshot = session_state_dict(row)
            await s.commit()
        return snapshot

    async def set_runtime_status(
        self, task_id: str, status: RuntimeStatus | str
    ) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.scalar(select(SessionState).where(SessionState.task_id == task_id))
            if row is None:
                return None
            row.runtime_status = str(transition(row.runtime_status, status))
            row.updated_at = datetime.now(UTC)
            snapshot = session_state_dict(row)
            await s.commit()
        return snapshot

    async def save_plan(
        self, task_id: str, plan: dict[str, Any], *, budget: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.scalar(select(SessionState).where(SessionState.task_id == task_id))
            if row is None:
                return None
            row.plan = dict(plan)
            if budget is not None:
                row.budget = dict(budget)
            row.revision = int(row.revision or 0) + 1
            row.updated_at = datetime.now(UTC)
            snapshot = session_state_dict(row)
            await s.commit()
        return snapshot

    async def get_board(self, task_id: str) -> dict[str, Any]:
        async with self.db.session() as s:
            row = await s.scalar(select(SessionState).where(SessionState.task_id == task_id))
            return dict(row.board or {}) if row is not None else {}

    async def save_board(self, task_id: str, board: dict[str, Any]) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.scalar(select(SessionState).where(SessionState.task_id == task_id))
            if row is None:
                return None
            row.board = dict(board)
            row.revision = int(row.revision or 0) + 1
            row.updated_at = datetime.now(UTC)
            snapshot = session_state_dict(row)
            await s.commit()
            return snapshot

    async def save_budget(self, task_id: str, budget: dict[str, Any]) -> None:
        async with self.db.session() as s:
            row = await s.scalar(select(SessionState).where(SessionState.task_id == task_id))
            if row is None:
                return
            row.budget = dict(budget)
            row.updated_at = datetime.now(UTC)
            await s.commit()

    async def goal_stack(self, task_id: str) -> GoalStack:
        snapshot = await self.get_session_state(task_id)
        return GoalStack(list((snapshot or {}).get("goal_stack") or []))

    async def stack_history(self, task_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            row = await s.scalar(select(SessionState).where(SessionState.task_id == task_id))
            if row is None:
                return []
            events = (
                await s.execute(
                    select(SessionStateEvent)
                    .where(SessionStateEvent.session_state_id == row.id)
                    .order_by(SessionStateEvent.sequence)
                )
            ).scalars()
            return [
                {
                    "sequence": item.sequence,
                    "op": item.op,
                    "before": item.before or {},
                    "after": item.after or {},
                    "reason": item.reason,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in events
            ]

    # -- skill_registry ------------------------------------------------------

    async def sync_skill_manifests(self, manifests: Sequence[SkillManifest]) -> int:
        """Upsert system skills, leaving personal and forged entries alone."""

        if not manifests:
            return 0
        async with self.db.session() as s:
            for manifest in manifests:
                values = manifest.to_row()
                row = await s.get(SkillRegistryEntry, manifest.skill_id)
                if row is None:
                    s.add(SkillRegistryEntry(**values))
                    continue
                if row.source != "system":
                    continue
                for key, value in values.items():
                    setattr(row, key, value)
                row.updated_at = datetime.now(UTC)
            await s.commit()
        return len(manifests)

    async def register_skill(self, manifest: SkillManifest, *, learner_id: str) -> dict[str, Any]:
        """Register a personal or forged skill for one learner."""

        async with self.db.session() as s:
            values = manifest.to_row() | {"learner_id": learner_id}
            row = await s.get(SkillRegistryEntry, manifest.skill_id)
            if row is None:
                row = SkillRegistryEntry(**values)
                s.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
                row.updated_at = datetime.now(UTC)
            await s.flush()
            snapshot = skill_dict(row)
            await s.commit()
        return snapshot

    async def set_skill_enabled(self, skill_id: str, enabled: bool) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.get(SkillRegistryEntry, skill_id)
            if row is None:
                return None
            row.enabled = bool(enabled)
            row.updated_at = datetime.now(UTC)
            snapshot = skill_dict(row)
            await s.commit()
        return snapshot

    async def list_skills(
        self, *, learner_id: str | None = None, enabled_only: bool = False
    ) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            statement = select(SkillRegistryEntry)
            if enabled_only:
                statement = statement.where(SkillRegistryEntry.enabled.is_(True))
            rows = (await s.execute(statement.order_by(SkillRegistryEntry.skill_id))).scalars()
            return [
                skill_dict(row)
                for row in rows
                if row.learner_id in (None, "", learner_id) or learner_id is None
            ]

    # -- decision_trace ------------------------------------------------------

    async def record_decision(self, **fields: Any) -> dict[str, Any]:
        async with self.db.session() as s:
            row = DecisionTrace(id=fields.pop("id", None) or f"dec_{uuid4().hex}", **fields)
            s.add(row)
            await s.flush()
            snapshot = decision_dict(row)
            await s.commit()
        return snapshot

    async def update_decision_outcome(self, decision_id: str, outcome: dict[str, Any]) -> None:
        async with self.db.session() as s:
            row = await s.get(DecisionTrace, decision_id)
            if row is None:
                return
            row.outcome = dict(outcome)
            await s.commit()

    async def decisions_for_task(self, task_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(DecisionTrace)
                    .where(DecisionTrace.task_id == task_id)
                    .order_by(DecisionTrace.step)
                )
            ).scalars()
            return [decision_dict(row) for row in rows]

    async def next_decision_step(self, task_id: str) -> int:
        async with self.db.session() as s:
            current = await s.scalar(
                select(func.max(DecisionTrace.step)).where(DecisionTrace.task_id == task_id)
            )
            return int(current or 0) + 1


__all__ = [
    "RuntimeStateRepository",
    "decision_dict",
    "evidence_dict",
    "profile_dict",
    "session_state_dict",
    "skill_dict",
]
