"""Evidence-backed mastery.

A mastery number the learner cannot interrogate is just a vibe.  Every update
here records what moved it and why, so the UI can answer "为什么你说我这里薄弱？"
with a list of attempts rather than "模型觉得".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

FLOOR, CEILING = 0.0, 1.0
DEFAULT_PRIOR = 0.35
"""Where an unseen concept starts — deliberately below the midpoint."""


def hint_discount(hint_level: int) -> float:
    """Credit earned shrinks with how much help was needed.

    Solving at H0 is worth full credit; arriving at the same answer after a
    level-3 scaffold is worth less, because it evidences less.
    """
    return {0: 1.0, 1: 0.85, 2: 0.7, 3: 0.5}.get(max(0, min(hint_level, 3)), 0.5)


def learning_rate(evidence_count: int) -> float:
    """Early observations move the estimate a lot; later ones refine it."""
    return max(0.18, 0.55 / (1.0 + 0.35 * max(0, evidence_count)))


@dataclass(frozen=True, slots=True)
class MasteryChange:
    concept: str
    before: float
    after: float
    reason: str
    evidence_ids: list[str] = field(default_factory=list)

    @property
    def delta(self) -> float:
        return round(self.after - self.before, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept": self.concept,
            "before": round(self.before, 4),
            "after": round(self.after, 4),
            "delta": self.delta,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
        }


def apply(
    current: dict[str, float],
    concept_scores: dict[str, float],
    *,
    hint_level: int = 0,
    evidence_ids: list[str] | None = None,
    counts: dict[str, int] | None = None,
    reason: str = "",
) -> tuple[dict[str, float], list[MasteryChange]]:
    """Fold graded results into the learner model.

    Returns the updated scores plus a per-concept explanation of the move.
    """
    counts = counts or {}
    updated = dict(current)
    changes: list[MasteryChange] = []
    discount = hint_discount(hint_level)

    for concept, raw in concept_scores.items():
        before = updated.get(concept, DEFAULT_PRIOR)
        credit = max(FLOOR, min(CEILING, raw)) * discount
        alpha = learning_rate(counts.get(concept, 0))
        after = max(FLOOR, min(CEILING, before + alpha * (credit - before)))
        updated[concept] = round(after, 4)
        changes.append(
            MasteryChange(
                concept=concept,
                before=before,
                after=updated[concept],
                reason=reason or f"score={raw:.2f} hint_level={hint_level}",
                evidence_ids=list(evidence_ids or []),
            )
        )
    return updated, changes


def weakest(mastery: dict[str, float], concepts: list[str], *, limit: int = 3) -> list[str]:
    """The concepts to teach first: lowest estimated mastery, stable ordering."""
    scored = [(mastery.get(c, DEFAULT_PRIOR), i, c) for i, c in enumerate(concepts)]
    scored.sort(key=lambda t: (t[0], t[1]))
    return [c for _, _, c in scored[:limit]]


def gain(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    concepts = set(before) | set(after)
    return {
        c: round(after.get(c, DEFAULT_PRIOR) - before.get(c, DEFAULT_PRIOR), 4) for c in concepts
    }
