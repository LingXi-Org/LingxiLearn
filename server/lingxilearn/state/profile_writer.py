"""The single writer of ``learning_profile``.

Every agent in the system may *read* the profile.  None of them may write it.
This module is the only place in the codebase that mutates
:class:`~lingxilearn.store.models.LearningProfile`, and
``tests/test_profile_write_guard.py`` walks the AST of the whole package to keep
it that way.

The rule that makes the ledger trustworthy: a change must cite the
``learning_evidence`` rows it came from.  :meth:`ProfileWriter.apply` refuses an
update with no evidence, so nothing can move a mastery number on a hunch.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

LEARNING_STATES = {
    "unknown",
    "not_observed",
    "emerging",
    "demonstrated",
    "misconception_evidence",
    "needs_recheck",
}
from ..store.models import LearningProfile
from .scheduling import confidence as compute_confidence

DEFAULT_MASTERY = 0.35


class UnsourcedProfileWrite(ValueError):
    """A profile change arrived without the evidence that justifies it."""


class InvalidProfileField(ValueError):
    """A profile change carried a value outside its declared domain."""


@dataclass(frozen=True, slots=True)
class ProfileDelta:
    """One knowledge point's worth of change, with the evidence behind it."""

    learner_id: str
    knowledge_point_id: str
    evidence_ids: Sequence[str]
    source_agent: str
    knowledge_point: str | None = None
    mastery: float | None = None
    learning_state: str | None = None
    progress: float | None = None
    my_questions: Sequence[str] | None = None
    recent_performance: dict[str, Any] | None = None
    last_studied_at: datetime | None = None
    review_due_at: datetime | None = None
    next_step: dict[str, Any] | None = None
    misconceptions: Sequence[str] | None = None
    prerequisites: Sequence[str] | None = None
    difficulty: float | None = None
    review_priority: float | None = None
    stability: float | None = None
    evidence_count: int | None = None
    last_evidence_seq: int | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.learner_id).strip():
            raise UnsourcedProfileWrite("profile delta requires a learner_id")
        if not str(self.knowledge_point_id).strip():
            raise UnsourcedProfileWrite("profile delta requires a knowledge_point_id")
        if not list(self.evidence_ids):
            raise UnsourcedProfileWrite(
                f"refusing to write {self.knowledge_point_id!r} without citing evidence"
            )
        if not str(self.source_agent).strip():
            raise UnsourcedProfileWrite("profile delta requires a source_agent")
        if self.learning_state is not None and self.learning_state not in LEARNING_STATES:
            raise InvalidProfileField(f"unknown learning_state: {self.learning_state!r}")
        for name in ("mastery", "progress", "difficulty", "review_priority"):
            value = getattr(self, name)
            if value is not None and not 0.0 <= float(value) <= 1.0:
                raise InvalidProfileField(f"{name} must be within 0..1, got {value!r}")


@dataclass(frozen=True, slots=True)
class ProfileChange:
    """Before/after for one row — what the decision trace and SSE event carry."""

    learner_id: str
    knowledge_point_id: str
    before: dict[str, Any]
    after: dict[str, Any]
    evidence_ids: list[str]
    source_agent: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "learner_id": self.learner_id,
            "knowledge_point_id": self.knowledge_point_id,
            "before": dict(self.before),
            "after": dict(self.after),
            "evidence_ids": list(self.evidence_ids),
            "source_agent": self.source_agent,
            "reason": self.reason,
        }

    @property
    def mastery_delta(self) -> float:
        before = float(self.before.get("mastery") or 0.0)
        after = float(self.after.get("mastery") or 0.0)
        return round(after - before, 4)


_TRACKED_FIELDS = (
    "knowledge_point",
    "mastery",
    "learning_state",
    "progress",
    "my_questions",
    "recent_performance",
    "last_studied_at",
    "review_due_at",
    "next_step",
    "confidence",
    "evidence_count",
    "misconceptions",
    "prerequisites",
    "difficulty",
    "review_priority",
    "stability",
    "source_agent",
    "revision",
    "override_flag",
    "last_evidence_seq",
)

_LEARNER_OWNED_FIELDS = frozenset(
    {"mastery", "learning_state", "progress", "difficulty", "next_step"}
)
"""Fields a learner override freezes; the updater may still add evidence counts."""


def snapshot(row: LearningProfile) -> dict[str, Any]:
    """A JSON-safe view of one row, used for trace before/after values."""

    out: dict[str, Any] = {}
    for name in _TRACKED_FIELDS:
        value = getattr(row, name, None)
        out[name] = value.isoformat() if isinstance(value, datetime) else value
    return out


def profile_id(learner_id: str, knowledge_point_id: str) -> str:
    return f"{learner_id}:{knowledge_point_id}"


class ProfileWriter:
    """The one component allowed to change a learner's profile."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def read(self, learner_id: str, knowledge_point_id: str) -> LearningProfile | None:
        return await self._session.scalar(
            select(LearningProfile).where(
                LearningProfile.id == profile_id(learner_id, knowledge_point_id)
            )
        )

    async def apply(self, deltas: Sequence[ProfileDelta]) -> list[ProfileChange]:
        """Apply evidence-backed changes, returning before/after for each row.

        Rows are created on first sight.  ``override_flag`` rows keep the
        learner's own values for the fields they own — the updater may still
        record that new evidence arrived, it just may not overrule the learner.
        """

        changes: list[ProfileChange] = []
        for delta in deltas:
            row = await self.read(delta.learner_id, delta.knowledge_point_id)
            created = row is None
            if row is None:
                row = LearningProfile(
                    id=profile_id(delta.learner_id, delta.knowledge_point_id),
                    learner_id=delta.learner_id,
                    knowledge_point_id=delta.knowledge_point_id,
                    knowledge_point=delta.knowledge_point or delta.knowledge_point_id,
                    mastery=DEFAULT_MASTERY,
                    learning_state="unknown",
                    my_questions=[],
                    recent_performance={},
                    next_step={},
                    misconceptions=[],
                    prerequisites=[],
                )
                self._session.add(row)
                await self._session.flush()

            before = snapshot(row)
            frozen = bool(row.override_flag)
            self._assign(row, delta, frozen=frozen)
            row.source_agent = delta.source_agent
            row.revision = int(row.revision or 0) + 1
            row.updated_at = datetime.now(UTC)
            after = snapshot(row)

            if not created and before == {**after, "revision": before.get("revision")}:
                # Nothing but the revision counter moved; do not manufacture a
                # profile change event for a no-op update.
                row.revision = int(before.get("revision") or 0)
                continue

            changes.append(
                ProfileChange(
                    learner_id=delta.learner_id,
                    knowledge_point_id=delta.knowledge_point_id,
                    before=before,
                    after=snapshot(row),
                    evidence_ids=[str(item) for item in delta.evidence_ids],
                    source_agent=delta.source_agent,
                    reason=delta.reason,
                )
            )
        await self._session.flush()
        return changes

    async def set_override(
        self,
        *,
        learner_id: str,
        knowledge_point_id: str,
        enabled: bool,
        fields: dict[str, Any] | None = None,
    ) -> ProfileChange | None:
        """Record a learner's own correction to their profile.

        This is not an agent write: it is the learner speaking about their own
        record, so it does not need evidence and it sets ``override_flag`` to
        stop the updater from quietly reverting it.
        """

        row = await self.read(learner_id, knowledge_point_id)
        if row is None:
            return None
        before = snapshot(row)
        row.override_flag = bool(enabled)
        for name, value in (fields or {}).items():
            if name not in _LEARNER_OWNED_FIELDS:
                raise InvalidProfileField(f"{name} is not learner-editable")
            if name == "learning_state" and value not in LEARNING_STATES:
                raise InvalidProfileField(f"unknown learning_state: {value!r}")
            setattr(row, name, value)
        row.source_agent = "learner"
        row.revision = int(row.revision or 0) + 1
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return ProfileChange(
            learner_id=learner_id,
            knowledge_point_id=knowledge_point_id,
            before=before,
            after=snapshot(row),
            evidence_ids=[],
            source_agent="learner",
            reason="learner override",
        )

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _assign(row: LearningProfile, delta: ProfileDelta, *, frozen: bool) -> None:
        def put(name: str, value: Any) -> None:
            if value is None:
                return
            if frozen and name in _LEARNER_OWNED_FIELDS:
                return
            setattr(row, name, value)

        put("knowledge_point", delta.knowledge_point)
        put("mastery", None if delta.mastery is None else round(float(delta.mastery), 4))
        put("learning_state", delta.learning_state)
        put("progress", None if delta.progress is None else round(float(delta.progress), 4))
        put("my_questions", None if delta.my_questions is None else list(delta.my_questions))
        put("recent_performance", delta.recent_performance)
        put("last_studied_at", delta.last_studied_at)
        put("review_due_at", delta.review_due_at)
        put("next_step", delta.next_step)
        put("misconceptions", None if delta.misconceptions is None else list(delta.misconceptions))
        put("prerequisites", None if delta.prerequisites is None else list(delta.prerequisites))
        put("difficulty", delta.difficulty)
        put("review_priority", delta.review_priority)
        put("stability", delta.stability)

        if delta.evidence_count is not None:
            row.evidence_count = int(delta.evidence_count)
            row.confidence = compute_confidence(row.evidence_count)
        if delta.last_evidence_seq is not None:
            row.last_evidence_seq = max(
                int(row.last_evidence_seq or 0), int(delta.last_evidence_seq)
            )


__all__ = [
    "DEFAULT_MASTERY",
    "InvalidProfileField",
    "ProfileChange",
    "ProfileDelta",
    "ProfileWriter",
    "UnsourcedProfileWrite",
    "profile_id",
    "snapshot",
]
