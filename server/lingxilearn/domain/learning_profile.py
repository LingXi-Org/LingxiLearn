"""Evidence-backed learner profile changes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

LEARNING_STATES = {
    "unknown",
    "not_observed",
    "emerging",
    "demonstrated",
    "misconception_evidence",
    "needs_recheck",
}
DEFAULT_MASTERY = 0.35


class UnsourcedProfileWrite(ValueError):
    """A profile change arrived without the evidence that justifies it."""


class InvalidProfileField(ValueError):
    """A profile change carried a value outside its declared domain."""


@dataclass(frozen=True, slots=True)
class ProfileDelta:
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


def profile_id(learner_id: str, knowledge_point_id: str) -> str:
    return f"{learner_id}:{knowledge_point_id}"
