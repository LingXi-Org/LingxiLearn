"""Recording why the runtime did what it did.

Acceptance criterion 4 in one module: every decision keeps its candidate set,
the choice, the reason, the evidence it produced, and the profile values before
and after.  ``replan_of`` links a decision to the one it is redoing, which is
what makes a replan visible in the log rather than inferable from timestamps.

The trace is not a debug log.  It is the data the learner-facing "why this?"
drill-down reads, so the reasons in it are written to be shown.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..state.profile_writer import ProfileChange
from ..state.session_state import Goal
from ..store.runtime_state import RuntimeStateRepository
from .contracts import CandidateAction, OrchestrationPlan, TaskOutcome
from .guardrails import Budget, GuardrailVerdict

logger = logging.getLogger(__name__)

MAX_TRACED_CANDIDATES = 24
"""Enough to answer "why not X" without storing a combinatorial dump."""


@dataclass(slots=True)
class DecisionRecord:
    """One round of the loop, as it will be persisted and streamed."""

    step: int
    goal: Goal
    candidates: Sequence[CandidateAction]
    plan: OrchestrationPlan
    guardrails: GuardrailVerdict
    budget: Budget
    outcomes: list[TaskOutcome] = field(default_factory=list)
    profile_before: dict[str, Any] = field(default_factory=dict)
    profile_after: dict[str, Any] = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)
    replan_of: str | None = None
    decision_id: str = ""

    def selected(self) -> dict[str, Any]:
        return {
            "tasks": [
                {
                    "id": task.id,
                    "capability": task.capability,
                    "knowledge_point_id": task.knowledge_point_id,
                    "rationale": task.rationale,
                    "done_when": task.done_when.describe(),
                    "expected_learning_gain": task.expected_learning_gain,
                }
                for task in self.plan.tasks
            ],
            "allowed": [task.id for task in self.guardrails.allowed_tasks],
            "awaits_user": self.plan.awaits_user,
            "negotiation": self.plan.negotiation,
            "degraded": self.plan.degraded,
        }

    def rationale(self) -> str:
        """One learner-readable paragraph explaining this round."""

        parts = [self.plan.reasoning.strip()] if self.plan.reasoning.strip() else []
        parts.extend(
            f"{task.capability}：{task.rationale}"
            for task in self.plan.tasks
            if task.rationale.strip()
        )
        if self.plan.negotiation:
            parts.append(f"协商：{self.plan.negotiation}")
        return " ".join(parts)


def summarise_profile(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The comparable slice of the profile, small enough to store twice a round."""

    return {
        str(row.get("knowledge_point_id")): {
            "mastery": row.get("mastery"),
            "learning_state": row.get("learning_state"),
            "evidence_count": (row.get("system") or {}).get("evidence_count"),
            "misconceptions": (row.get("system") or {}).get("misconceptions") or [],
            "review_priority": (row.get("system") or {}).get("review_priority"),
        }
        for row in rows
        if row.get("knowledge_point_id")
    }


def changes_to_dict(changes: Sequence[ProfileChange]) -> dict[str, Any]:
    return {change.knowledge_point_id: change.to_dict() for change in changes}


class DecisionTracer:
    """Persists decision records and projects them as runtime events."""

    def __init__(
        self,
        runtime_state: RuntimeStateRepository,
        *,
        learner_id: str,
        task_id: str,
        execution_id: str = "",
        emit: Any = None,
    ) -> None:
        self._state = runtime_state
        self._learner_id = learner_id
        self._task_id = task_id
        self._execution_id = execution_id
        self._emit = emit
        self._last_id: str | None = None

    @property
    def last_decision_id(self) -> str | None:
        return self._last_id

    async def next_step(self) -> int:
        return await self._state.next_decision_step(self._task_id)

    async def record(self, record: DecisionRecord) -> dict[str, Any]:
        """Write one decision and return the stored row."""

        candidates = [
            item.to_dict() for item in list(record.candidates)[:MAX_TRACED_CANDIDATES]
        ]
        stored = await self._state.record_decision(
            learner_id=self._learner_id,
            task_id=self._task_id,
            execution_id=self._execution_id,
            step=record.step,
            goal=record.goal.to_dict(),
            candidates=candidates,
            selected=record.selected(),
            rationale=record.rationale(),
            evidence_ids=list(record.evidence_ids),
            profile_before=dict(record.profile_before),
            profile_after=dict(record.profile_after),
            guardrail_state={
                **record.guardrails.to_dict(),
                "budget": record.budget.to_dict(),
            },
            outcome={"tasks": [item.to_dict() for item in record.outcomes]},
            replan_of=record.replan_of,
        )
        record.decision_id = str(stored["id"])
        self._last_id = record.decision_id

        self._project("decision.recorded", stored)
        for task in record.plan.tasks:
            # One node per planned task: the runtime graph grows as decisions
            # are made rather than being drawn in advance.
            self._project(
                "node.appeared",
                {
                    "decision_id": record.decision_id,
                    "step": record.step,
                    "node_id": f"{record.step}:{task.id}",
                    "task_id": task.id,
                    "capability": task.capability,
                    "depends_on": list(task.depends_on),
                    "knowledge_point_id": task.knowledge_point_id,
                    "rationale": task.rationale,
                    "done_when": task.done_when.describe(),
                    "allowed": task.id
                    in {item.id for item in record.guardrails.allowed_tasks},
                },
            )
        if record.replan_of:
            self._project(
                "plan.replanned",
                {
                    "decision_id": record.decision_id,
                    "replan_of": record.replan_of,
                    "step": record.step,
                    "tasks": [
                        {
                            "id": task.id,
                            "capability": task.capability,
                            "rationale": task.rationale,
                            "depends_on": list(task.depends_on),
                        }
                        for task in record.plan.tasks
                    ],
                },
            )
        else:
            self._project(
                "plan.created",
                {
                    "decision_id": record.decision_id,
                    "step": record.step,
                    "tasks": [
                        {
                            "id": task.id,
                            "capability": task.capability,
                            "rationale": task.rationale,
                            "depends_on": list(task.depends_on),
                        }
                        for task in record.plan.tasks
                    ],
                },
            )
        return stored

    async def finish(self, decision_id: str, outcomes: Sequence[TaskOutcome]) -> None:
        await self._state.update_decision_outcome(
            decision_id, {"tasks": [item.to_dict() for item in outcomes]}
        )

    def profile_changed(self, changes: Sequence[ProfileChange]) -> None:
        for change in changes:
            self._project("profile.updated", change.to_dict())

    def guardrail_triggered(self, verdict: GuardrailVerdict) -> None:
        for finding in verdict.findings:
            self._project("guardrail.triggered", finding.to_dict())

    def _project(self, kind: str, payload: Mapping[str, Any]) -> None:
        if self._emit is None:
            return
        try:
            self._emit(kind, dict(payload))
        except Exception:  # noqa: BLE001 - telemetry must never break a run
            logger.debug("decision trace projection failed: %s", kind, exc_info=True)


__all__ = [
    "MAX_TRACED_CANDIDATES",
    "DecisionRecord",
    "DecisionTracer",
    "changes_to_dict",
    "summarise_profile",
]
