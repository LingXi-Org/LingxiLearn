"""Review scheduling: how long a memory should hold and when to test it again.

An SM-2-shaped model, simplified to the two numbers the profile actually needs:
``stability`` (how many days the memory is expected to survive) and
``review_due_at``.  ``review_priority`` blends overdue-ness with weakness, so
the orchestrator can rank "revisit this" against "teach something new" on one
comparable scale.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

MIN_STABILITY_DAYS = 0.25
MAX_STABILITY_DAYS = 180.0
INITIAL_STABILITY_DAYS = 1.0


def next_stability(
    *, current: float, score: float, difficulty: float, hint_level: int = 0
) -> float:
    """Grow stability on a clean recall, cut it hard on a failure.

    A correct answer that needed a level-3 scaffold is not a clean recall, so
    the growth factor is discounted the same way mastery credit is.
    """

    stability = max(float(current), 0.0) or INITIAL_STABILITY_DAYS
    clamped = max(0.0, min(1.0, float(score)))
    ease = 1.3 + 1.7 * (1.0 - max(0.0, min(1.0, float(difficulty))))
    scaffold = {0: 1.0, 1: 0.85, 2: 0.7, 3: 0.5}.get(max(0, min(int(hint_level), 3)), 0.5)

    if clamped >= 0.6:
        grown = stability * (1.0 + (ease - 1.0) * clamped * scaffold)
    else:
        # A lapse resets most of the interval but never all of it; the learner
        # has still seen the material once.
        grown = stability * (0.25 + 0.35 * clamped)
    return round(max(MIN_STABILITY_DAYS, min(MAX_STABILITY_DAYS, grown)), 4)


def due_at(*, stability: float, last_studied_at: datetime | None = None) -> datetime:
    anchor = last_studied_at or datetime.now(UTC)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=UTC)
    return anchor + timedelta(days=max(MIN_STABILITY_DAYS, float(stability)))


def review_priority(
    *,
    mastery: float,
    review_due_at: datetime | None,
    now: datetime | None = None,
    evidence_count: int = 0,
    has_misconceptions: bool = False,
) -> float:
    """0..1 urgency of revisiting this knowledge point.

    Overdue weak material outranks overdue strong material, and an unresolved
    misconception keeps a point warm even when it is not yet due.
    """

    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)

    weakness = 1.0 - max(0.0, min(1.0, float(mastery)))

    overdue = 0.0
    if review_due_at is not None:
        due = review_due_at if review_due_at.tzinfo else review_due_at.replace(tzinfo=UTC)
        overdue_days = (moment - due).total_seconds() / 86_400.0
        if overdue_days > 0:
            # Saturating: two weeks overdue and a month overdue are both "now".
            overdue = min(1.0, overdue_days / 14.0)

    # Thin evidence is its own reason to revisit: the estimate is not trustworthy.
    uncertainty = 1.0 / (1.0 + 0.6 * max(0, int(evidence_count)))

    score = 0.45 * overdue + 0.35 * weakness + 0.20 * uncertainty
    if has_misconceptions:
        score = min(1.0, score + 0.15)
    return round(max(0.0, min(1.0, score)), 4)


def confidence(evidence_count: int, *, consistency: float = 1.0) -> float:
    """How much to trust the mastery estimate: more consistent evidence, more trust."""

    saturation = 1.0 - 1.0 / (1.0 + 0.5 * max(0, int(evidence_count)))
    return round(max(0.0, min(1.0, saturation * max(0.0, min(1.0, consistency)))), 4)


__all__ = [
    "INITIAL_STABILITY_DAYS",
    "MAX_STABILITY_DAYS",
    "MIN_STABILITY_DAYS",
    "confidence",
    "due_at",
    "next_stability",
    "review_priority",
]
