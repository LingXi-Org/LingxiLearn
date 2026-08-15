"""Did the learner learn? Measured from the decision trace, not from opinions.

Every metric here is computed from ``decision_trace``'s recorded before/after
profile values and the evidence rows behind them, which means it can be run over
any past task without re-executing anything.

Deliberately absent: any measure of how the session felt. A learner can enjoy a
session that taught them nothing, and a tutor optimised for satisfaction becomes
a chat companion. What is measured here is movement in mastery, whether that
movement was paid for with evidence, whether prerequisites got closed, and
whether misconceptions actually went away.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

DEFAULT_MASTERY = 0.35


@dataclass(frozen=True, slots=True)
class GainReport:
    """One task's learning outcome."""

    task_id: str
    mastery_gain: float
    """Total mastery movement across all knowledge points, signed."""
    gain_per_evidence: float
    """Mastery gained per evidence row. The efficiency number."""
    gain_per_step: float
    """Mastery gained per orchestrator decision. The cost-of-routing number."""
    evidence_count: int
    decision_count: int
    replan_count: int
    unsourced_changes: int
    """Profile movements with no evidence cited. Should always be zero."""
    prerequisite_closure: float
    misconception_resolution: float
    points_improved: int
    points_regressed: int
    per_point: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "mastery_gain": round(self.mastery_gain, 4),
            "gain_per_evidence": round(self.gain_per_evidence, 4),
            "gain_per_step": round(self.gain_per_step, 4),
            "evidence_count": self.evidence_count,
            "decision_count": self.decision_count,
            "replan_count": self.replan_count,
            "unsourced_changes": self.unsourced_changes,
            "prerequisite_closure": round(self.prerequisite_closure, 4),
            "misconception_resolution": round(self.misconception_resolution, 4),
            "points_improved": self.points_improved,
            "points_regressed": self.points_regressed,
            "per_point": {k: round(v, 4) for k, v in self.per_point.items()},
        }


def _mastery_of(snapshot: Mapping[str, Any], point: str) -> float:
    row = snapshot.get(point)
    if not isinstance(row, Mapping):
        return DEFAULT_MASTERY
    value = row.get("mastery")
    return float(value) if isinstance(value, (int, float)) else DEFAULT_MASTERY


def mastery_gain(decisions: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Net mastery movement per knowledge point across the whole task.

    Taken from the first ``profile_before`` and the last ``profile_after`` that
    mention each point, so intermediate churn inside a task does not inflate the
    total.
    """

    first: dict[str, float] = {}
    last: dict[str, float] = {}
    for decision in decisions:
        before = decision.get("profile_before") or {}
        after = decision.get("profile_after") or {}
        for point in before:
            first.setdefault(point, _mastery_of(before, point))
        for point in after:
            first.setdefault(point, _mastery_of(after, point))
            last[point] = _mastery_of(after, point)
    return {point: round(last[point] - first.get(point, DEFAULT_MASTERY), 4) for point in last}


def prerequisite_closure(decisions: Sequence[Mapping[str, Any]]) -> float:
    """Of the prerequisites this task found unmet, how many did it close?

    A runtime that correctly notices a missing prerequisite and then never fixes
    it has diagnosed, not taught.
    """

    unmet: set[str] = set()
    for decision in decisions:
        before = decision.get("profile_before") or {}
        for row in before.values():
            if not isinstance(row, Mapping):
                continue
            for prerequisite in row.get("prerequisites") or []:
                name = str(prerequisite)
                if isinstance(before.get(name), Mapping) and _mastery_of(before, name) < 0.6:
                    unmet.add(name)

    if not unmet:
        return 1.0
    final = (decisions[-1].get("profile_after") or {}) if decisions else {}
    closed = sum(1 for point in unmet if _mastery_of(final, point) >= 0.6)
    return round(closed / len(unmet), 4)


def misconception_resolution(decisions: Sequence[Mapping[str, Any]]) -> float:
    """Of the misconceptions seen during the task, how many were retired?"""

    seen: set[str] = set()
    for decision in decisions:
        for snapshot in (decision.get("profile_before") or {}, decision.get("profile_after") or {}):
            for row in snapshot.values():
                if isinstance(row, Mapping):
                    seen.update(str(tag) for tag in (row.get("misconceptions") or []))
    if not seen:
        return 1.0

    remaining: set[str] = set()
    final = (decisions[-1].get("profile_after") or {}) if decisions else {}
    for row in final.values():
        if isinstance(row, Mapping):
            remaining.update(str(tag) for tag in (row.get("misconceptions") or []))
    return round((len(seen) - len(seen & remaining)) / len(seen), 4)


def evaluate_task(
    task_id: str,
    decisions: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]] = (),
) -> GainReport:
    """Score one task from its recorded trace."""

    per_point = mastery_gain(decisions)
    total = round(sum(per_point.values()), 4)
    evidence_count = len(evidence) or sum(
        len(decision.get("evidence_ids") or []) for decision in decisions
    )
    replans = sum(1 for decision in decisions if decision.get("replan_of"))

    # A profile that moved without citing evidence means the single-writer rule
    # leaked somewhere. It should be structurally impossible, so measure it.
    unsourced = 0
    for decision in decisions:
        before = decision.get("profile_before") or {}
        after = decision.get("profile_after") or {}
        moved = any(_mastery_of(before, point) != _mastery_of(after, point) for point in after)
        if moved and not (decision.get("evidence_ids") or []):
            unsourced += 1

    return GainReport(
        task_id=task_id,
        mastery_gain=total,
        gain_per_evidence=round(total / evidence_count, 4) if evidence_count else 0.0,
        gain_per_step=round(total / len(decisions), 4) if decisions else 0.0,
        evidence_count=evidence_count,
        decision_count=len(decisions),
        replan_count=replans,
        unsourced_changes=unsourced,
        prerequisite_closure=prerequisite_closure(decisions),
        misconception_resolution=misconception_resolution(decisions),
        points_improved=sum(1 for value in per_point.values() if value > 0),
        points_regressed=sum(1 for value in per_point.values() if value < 0),
        per_point=per_point,
    )


async def evaluate_learner(
    runtime_state: Any, learner_id: str, task_ids: Sequence[str]
) -> dict[str, Any]:
    """Aggregate several tasks for one learner."""

    reports = []
    for task_id in task_ids:
        decisions = await runtime_state.decisions_for_task(task_id)
        evidence = await runtime_state.evidence_for_task(task_id)
        reports.append(evaluate_task(task_id, decisions, evidence))

    total_gain = round(sum(item.mastery_gain for item in reports), 4)
    total_evidence = sum(item.evidence_count for item in reports)
    return {
        "learner_id": learner_id,
        "tasks": [item.to_dict() for item in reports],
        "mastery_gain": total_gain,
        "gain_per_evidence": round(total_gain / total_evidence, 4) if total_evidence else 0.0,
        "unsourced_changes": sum(item.unsourced_changes for item in reports),
    }


__all__ = [
    "GainReport",
    "evaluate_learner",
    "evaluate_task",
    "mastery_gain",
    "misconception_resolution",
    "prerequisite_closure",
]
