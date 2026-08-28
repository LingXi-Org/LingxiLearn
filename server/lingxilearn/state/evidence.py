"""Structured learning evidence — the only thing an agent may say about a learner.

Agents never write ``learning_profile`` and never hand each other prose.  They
emit :class:`EvidenceRecord` values, the repository appends them, and
``runtime.state_updater`` is the single consumer that turns them into profile
changes.

The digest reuses the scheme in :mod:`lingxilearn.kernel.evidence` so a replayed
node cannot silently substitute a different value behind the same identity.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Signal(StrEnum):
    """What was actually observed. Deliberately behavioural, never a judgement."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    NO_ANSWER = "no_answer"
    SELF_REPORT = "self_report"
    DWELL_TIME = "dwell_time"
    ERROR_PATTERN = "error_pattern"
    ARTIFACT_VIEWED = "artifact_viewed"
    HINT_USED = "hint_used"


GRADED_SIGNALS = frozenset({Signal.CORRECT, Signal.INCORRECT, Signal.NO_ANSWER})
"""Signals that carry a score and therefore move mastery on their own."""


class InvalidEvidence(ValueError):
    """The record cannot be appended: it says nothing usable about the learner."""


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """One structured observation about one knowledge point."""

    learner_id: str
    knowledge_point: str
    signal: Signal
    source_agent: str
    task_id: str
    summary: str = ""
    score: float | None = None
    """0..1 for graded signals; ``None`` when the signal carries no score."""
    misconceptions: tuple[str, ...] = ()
    hint_level: int = 0
    locator: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not str(self.learner_id).strip():
            raise InvalidEvidence("evidence requires a learner_id")
        if not str(self.knowledge_point).strip():
            raise InvalidEvidence("evidence requires a knowledge_point")
        if not str(self.source_agent).strip():
            raise InvalidEvidence("evidence requires a source_agent")
        if not str(self.task_id).strip():
            raise InvalidEvidence("evidence requires a task_id")
        if self.signal in GRADED_SIGNALS and self.score is None:
            raise InvalidEvidence(f"{self.signal} evidence requires a score")
        if self.score is not None and not 0.0 <= float(self.score) <= 1.0:
            raise InvalidEvidence("evidence score must be within 0..1")

    @property
    def digest(self) -> str:
        return _digest(
            {
                "knowledge_point": self.knowledge_point,
                "signal": str(self.signal),
                "score": self.score,
                "locator": self.locator,
                "payload": self.payload,
            }
        )

    @property
    def evidence_id(self) -> str:
        """Content-addressed id, so the same observation appended twice collapses."""

        return f"ev_{self.digest.removeprefix('sha256:')}"

    def to_row(self) -> dict[str, Any]:
        """The column values the repository appends; ``seq`` is assigned there."""

        return {
            "learner_id": self.learner_id,
            "task_id": self.task_id,
            "evidence_id": self.evidence_id,
            "kind": "learner_action",
            "source": f"{self.source_agent}:{self.signal}",
            "summary": self.summary or f"{self.knowledge_point} · {self.signal}",
            "locator": dict(self.locator),
            "value": {
                "score": self.score,
                "misconceptions": list(self.misconceptions),
                "hint_level": int(self.hint_level),
            },
            "digest": self.digest,
            "knowledge_point": self.knowledge_point,
            "signal": str(self.signal),
            "source_agent": self.source_agent,
            "payload": dict(self.payload),
            "observed_at": self.observed_at,
        }


def graded(row: Mapping[str, Any]) -> bool:
    """True when a stored evidence row carries a usable score."""

    return str(row.get("signal") or "") in {str(s) for s in GRADED_SIGNALS}


def score_of(row: Mapping[str, Any]) -> float | None:
    value = row.get("value")
    if not isinstance(value, dict):
        return None
    score = value.get("score")
    return float(score) if isinstance(score, (int, float)) else None


def misconceptions_of(row: Mapping[str, Any]) -> list[str]:
    value = row.get("value")
    if not isinstance(value, dict):
        return []
    return [str(tag) for tag in (value.get("misconceptions") or [])]


def hint_level_of(row: Mapping[str, Any]) -> int:
    value = row.get("value")
    if not isinstance(value, dict):
        return 0
    level = value.get("hint_level")
    return int(level) if isinstance(level, (int, float)) else 0


__all__ = [
    "GRADED_SIGNALS",
    "EvidenceRecord",
    "InvalidEvidence",
    "Signal",
    "graded",
    "hint_level_of",
    "misconceptions_of",
    "score_of",
]
