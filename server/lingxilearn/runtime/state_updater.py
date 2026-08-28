"""Fold new evidence into the learning profile.

The single consumer of ``learning_evidence``. Agents produce evidence; this
decides what the evidence means.

Mastery arithmetic is not reinvented here — :mod:`lingxilearn.kernel.mastery`
already models evidence-weighted updates with hint discounting, and it stays the
authority.  What this adds is the profile-shaped bookkeeping around it:
scheduling, misconception aggregation, and a before/after record for the trace.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from ..domain.learning_profile import DEFAULT_MASTERY, ProfileChange, ProfileDelta
from ..kernel import mastery as mastery_model
from ..ports.runtime_state import RuntimeStatePort
from ..state.evidence import Signal, graded, hint_level_of, misconceptions_of, score_of
from ..state.scheduling import due_at, next_stability, review_priority

logger = logging.getLogger(__name__)

RECENT_WINDOW = 8
"""How many observations ``recent_performance`` summarises."""

_STATE_BY_MASTERY = (
    (0.75, "demonstrated"),
    (0.45, "emerging"),
    (0.0, "not_observed"),
)


def _learning_state(
    *, mastery: float, evidence_count: int, has_misconceptions: bool, graded_count: int
) -> str:
    """Map the numbers onto the shared learning-state vocabulary.

    Deliberately conservative: high mastery on one observation is
    ``needs_recheck``, not ``demonstrated``.  Claiming someone has demonstrated
    something they did once is how a learner model loses trust.
    """

    if evidence_count == 0:
        return "unknown"
    if has_misconceptions:
        return "misconception_evidence"
    if graded_count < 2:
        return "needs_recheck"
    for threshold, state in _STATE_BY_MASTERY:
        if mastery >= threshold:
            return state
    return "not_observed"


def _recent_performance(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    window = list(rows)[-RECENT_WINDOW:]
    scored_values = [score_of(row) for row in window if graded(row)]
    scored: list[float] = [value for value in scored_values if value is not None]
    return {
        "observations": len(window),
        "graded": len(scored),
        "recent_scores": [round(value, 3) for value in scored],
        "recent_mean": round(sum(scored) / len(scored), 4) if scored else None,
        "last_signal": str(window[-1].get("signal") or "") if window else "",
        "last_at": str(window[-1].get("observed_at") or "") if window else "",
    }


def _questions(existing: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Learner-authored questions, newest last, de-duplicated."""

    found = list(existing)
    for row in rows:
        if str(row.get("signal") or "") != str(Signal.SELF_REPORT):
            continue
        summary = str(row.get("summary") or "").strip()
        if summary and summary not in found:
            found.append(summary)
    return found[-12:]


def _misconceptions(existing: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Aggregate misconception tags; a later correct answer retires one.

    Retiring on a clean unaided correct answer is the only way a misconception
    ever leaves the profile, which keeps "resolved" backed by evidence rather
    than by time passing.
    """

    found = list(existing)
    for row in rows:
        for tag in misconceptions_of(row):
            if tag not in found:
                found.append(tag)
        if (
            str(row.get("signal") or "") == str(Signal.CORRECT)
            and hint_level_of(row) == 0
            and (score_of(row) or 0.0) >= 0.9
        ):
            resolved = misconceptions_of(row)
            found = [tag for tag in found if tag not in resolved] if resolved else found
    return found


def _group_by_point(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        point = str(row.get("knowledge_point") or "").strip()
        if point:
            grouped.setdefault(point, []).append(row)
    return grouped


class StateUpdater:
    """Reads unconsumed evidence, writes the profile, reports what changed."""

    def __init__(self, runtime_state: RuntimeStatePort) -> None:
        self._state = runtime_state

    async def apply(
        self,
        *,
        learner_id: str,
        source_agent: str = "state_updater",
        now: datetime | None = None,
        limit: int = 500,
    ) -> list[ProfileChange]:
        """Fold every evidence row past the profile's high-water mark.

        The watermark is per knowledge point, so evidence for a point that has
        not been seen yet is picked up on its first update rather than being
        skipped because some other point had already advanced.
        """

        moment = now or datetime.now(UTC)
        async with self._state.projection_lock(learner_id):
            watermark = await self._state.projection_cursor(learner_id)
            pending = await self._state.evidence_after(learner_id, watermark, limit=limit)
            if not pending:
                return []

            grouped = _group_by_point(pending)
            existing = {
                row["knowledge_point_id"]: row for row in await self._state.profile_for(learner_id)
            }

            deltas: list[ProfileDelta] = []
            for point, rows in grouped.items():
                current = existing.get(point)
                point_watermark = int(
                    ((current or {}).get("system") or {}).get("last_evidence_seq") or 0
                )
                fresh = [row for row in rows if int(row.get("seq") or 0) > point_watermark]
                if not fresh:
                    continue
                deltas.append(
                    self._delta_for(
                        learner_id=learner_id,
                        point=point,
                        current=current,
                        fresh=fresh,
                        source_agent=source_agent,
                        now=moment,
                    )
                )

            if not deltas:
                await self._state.advance_projection_cursor(
                    learner_id, max(int(row.get("seq") or 0) for row in pending)
                )
                return []
            changes = await self._state.apply_profile_deltas(deltas)
            await self._state.advance_projection_cursor(
                learner_id, max(int(row.get("seq") or 0) for row in pending)
            )
            return changes

    def _delta_for(
        self,
        *,
        learner_id: str,
        point: str,
        current: Mapping[str, Any] | None,
        fresh: Sequence[Mapping[str, Any]],
        source_agent: str,
        now: datetime,
    ) -> ProfileDelta:
        system = dict((current or {}).get("system") or {})
        before_mastery = float((current or {}).get("mastery") or DEFAULT_MASTERY)
        prior_count = int(system.get("evidence_count") or 0)
        difficulty = float(system.get("difficulty") or 0.5)
        stability = float(system.get("stability") or 0.0)

        mastery = before_mastery
        graded_rows = [row for row in fresh if graded(row)]

        # One fold per graded observation: hint level is per attempt, and
        # kernel.mastery discounts credit by it.
        for index, row in enumerate(graded_rows):
            score = score_of(row)
            if score is None:
                continue
            updated, _changes = mastery_model.apply(
                {point: mastery},
                {point: score},
                hint_level=hint_level_of(row),
                evidence_ids=[str(row.get("evidence_id") or "")],
                counts={point: prior_count + index},
                reason=f"signal={row.get('signal')}",
            )
            mastery = updated[point]
            stability = next_stability(
                current=stability,
                score=score,
                difficulty=difficulty,
                hint_level=hint_level_of(row),
            )

        evidence_count = prior_count + len(fresh)
        misconceptions = _misconceptions(system.get("misconceptions") or [], fresh)
        last_studied = now
        review_due = (
            due_at(stability=stability, last_studied_at=last_studied) if stability else None
        )
        priority = review_priority(
            mastery=mastery,
            review_due_at=review_due,
            now=now,
            evidence_count=evidence_count,
            has_misconceptions=bool(misconceptions),
        )

        return ProfileDelta(
            learner_id=learner_id,
            knowledge_point_id=point,
            evidence_ids=[str(row.get("evidence_id") or "") for row in fresh],
            source_agent=source_agent,
            knowledge_point=(current or {}).get("knowledge_point") or point,
            mastery=mastery,
            learning_state=_learning_state(
                mastery=mastery,
                evidence_count=evidence_count,
                has_misconceptions=bool(misconceptions),
                graded_count=len([row for row in fresh if graded(row)]) + prior_count,
            ),
            my_questions=_questions((current or {}).get("my_questions") or [], fresh),
            recent_performance=_recent_performance(fresh),
            last_studied_at=last_studied,
            review_due_at=review_due,
            misconceptions=misconceptions,
            review_priority=priority,
            stability=stability,
            evidence_count=evidence_count,
            last_evidence_seq=max(int(row.get("seq") or 0) for row in fresh),
            reason=f"折叠 {len(fresh)} 条新证据",
        )


__all__ = ["RECENT_WINDOW", "StateUpdater"]
