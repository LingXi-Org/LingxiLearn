"""The contracts the runtime loop plans and executes against.

Two ideas carry most of the weight here:

* A plan names **capabilities**, never agents.  ``PlannedTask.capability`` is a
  tag from the closed vocabulary; which skill and which provider serve it is
  resolved at dispatch time from ``skill_registry``.  That is what keeps the
  domain topology out of the graph.
* A task's completion is a **declarative predicate**, not "the agent returned".
  :class:`DoneCondition` is evaluated against the four state tables and the
  artifact store by :mod:`lingxilearn.runtime.completion`, so a provider that
  finishes without producing the intended change does not count as done.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..state.capabilities import Capability, UnknownCapability, parse

DoneKind = Literal[
    "artifact_exists",
    "artifact_valid",
    "evidence_observed",
    "profile_reaches",
    "user_replied",
    "quiz_graded",
    "always",
    "all_of",
    "any_of",
]


class DoneCondition(BaseModel):
    """A machine-checkable statement of what "finished" means for one task.

    Prose conditions ("until the learner understands") are rejected at parse
    time: every field the evaluator needs is explicit here.
    """

    model_config = ConfigDict(extra="ignore")

    kind: DoneKind
    artifact: str = ""
    """For ``artifact_exists`` / ``artifact_valid``: lesson-intro, deck, visual, quiz."""
    knowledge_point_id: str = ""
    signal: str = ""
    """For ``evidence_observed``: the evidence signal that must appear."""
    mastery: float = Field(default=0.0, ge=0.0, le=1.0)
    """For ``profile_reaches``: the mastery the profile row must reach."""
    min_count: int = Field(default=1, ge=1)
    conditions: list[DoneCondition] = Field(default_factory=list)
    """Operands for ``all_of`` / ``any_of``."""

    @model_validator(mode="after")
    def _require_the_fields_the_kind_needs(self) -> DoneCondition:
        if self.kind in {"artifact_exists", "artifact_valid"} and not self.artifact:
            raise ValueError(f"{self.kind} requires an artifact name")
        if self.kind == "evidence_observed" and not self.signal:
            raise ValueError("evidence_observed requires a signal")
        if self.kind == "profile_reaches" and not self.knowledge_point_id:
            raise ValueError("profile_reaches requires a knowledge_point_id")
        if self.kind in {"all_of", "any_of"} and not self.conditions:
            raise ValueError(f"{self.kind} requires at least one nested condition")
        return self

    def describe(self) -> str:
        """A short Chinese phrase for the decision trace and the runtime graph."""

        match self.kind:
            case "artifact_exists":
                return f"产出 {self.artifact}"
            case "artifact_valid":
                return f"{self.artifact} 通过校验"
            case "evidence_observed":
                return f"观察到 {self.signal} 证据 ×{self.min_count}"
            case "profile_reaches":
                return f"{self.knowledge_point_id} 掌握度达到 {self.mastery:.2f}"
            case "user_replied":
                return "学习者已回复"
            case "quiz_graded":
                return "测评已判分"
            case "always":
                return "执行即完成"
            case "all_of":
                return "同时满足：" + "；".join(c.describe() for c in self.conditions)
            case "any_of":
                return "任一满足：" + "；".join(c.describe() for c in self.conditions)
        return self.kind


class Cost(BaseModel):
    """What one run of a capability is expected to spend."""

    model_config = ConfigDict(extra="ignore")

    latency_class: str = "interactive"
    latency_weight: float = 1.0
    heavy_artifact: bool = False
    blocking: bool = True
    irreversible: bool = False
    parallel_safe: bool = False
    critical_path: bool = True

    @property
    def normalized(self) -> float:
        """A single comparable number; heavy artifacts cost more than their latency."""

        return max(0.25, self.latency_weight + (1.5 if self.heavy_artifact else 0.0))


class CandidateAction(BaseModel):
    """One scored option the orchestrator was allowed to choose from.

    The full candidate set is written to ``decision_trace`` so a learner can see
    not just what ran but what else was on the table and why it lost.
    """

    model_config = ConfigDict(extra="ignore")

    # Kept optional for deserialising pre-V2 traces; new candidates always
    # receive one from candidate generation.
    candidate_id: str = ""
    capability: str
    skill_id: str
    provider: str
    skill_version: str = ""
    skill_checksum: str = ""
    knowledge_point_id: str = ""
    gain: float = 0.0
    cost: float = 1.0
    utility: float = 0.0
    reason: str = ""
    eligible: bool = True
    blocked_by: str = ""
    parallel_safe: bool = False
    critical_path: bool = True
    """Why an ineligible candidate was excluded; kept for the trace."""

    @field_validator("capability")
    @classmethod
    def _known_capability(cls, value: str) -> str:
        parse(value)  # raises UnknownCapability outside the closed vocabulary
        return value

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PlannedTask(BaseModel):
    """One unit of work, addressed by capability and closed by a predicate."""

    model_config = ConfigDict(extra="ignore")

    id: str
    candidate_id: str = ""
    capability: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    done_when: DoneCondition
    rationale: str = Field(min_length=1)
    """Shown to the learner verbatim; guardrails reject an empty one."""
    expected_learning_gain: float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_cost: Cost = Field(default_factory=Cost)
    knowledge_point_id: str = ""

    @field_validator("capability")
    @classmethod
    def _known_capability(cls, value: str) -> str:
        parse(value)
        return value

    @property
    def resolved_capability(self) -> Capability:
        return parse(self.capability)


class HoldDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_key: str
    action: Literal["revise", "close"]
    instruction: str = ""


class OrchestrationPlan(BaseModel):
    """What the orchestrator decided this round, and why."""

    model_config = ConfigDict(extra="ignore")

    reasoning: str = ""
    hypotheses: list[str] = Field(default_factory=list)
    tasks: list[PlannedTask] = Field(default_factory=list)
    goal_satisfied_when: DoneCondition | None = None
    awaits_user: bool = False
    negotiation: str | None = None
    candidates_considered: list[CandidateAction] = Field(default_factory=list)
    deviates_from_goal: bool = False
    """Set when the top-ranked capability is not what the learner literally asked for."""
    degraded: bool = False
    """Set when the plan came from the deterministic fallback rather than the model."""
    holds: list[HoldDecision] = Field(default_factory=list)
    delivery_order: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _task_ids_are_unique_and_dependencies_resolve(self) -> OrchestrationPlan:
        ids = [task.id for task in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("planned task ids must be unique")
        known = set(ids)
        for task in self.tasks:
            unknown = [dep for dep in task.depends_on if dep not in known]
            if unknown:
                raise ValueError(f"task {task.id} depends on unknown tasks: {unknown}")
            if task.id in task.depends_on:
                raise ValueError(f"task {task.id} depends on itself")
        return self

    def ordered_tasks(self) -> list[PlannedTask]:
        """Dependency order. Cycles raise rather than deadlocking the loop."""

        return [task for tier in self.tiers() for task in tier]

    def tiers(self) -> list[list[PlannedTask]]:
        """Return stable dependency tiers without flattening ready tasks."""
        remaining = {task.id: task for task in self.tasks}
        done: set[str] = set()
        tiers: list[list[PlannedTask]] = []
        while remaining:
            ready = [
                task for task in remaining.values() if all(dep in done for dep in task.depends_on)
            ]
            if not ready:
                raise ValueError(f"cyclic task dependencies: {sorted(remaining)}")
            ready.sort(key=lambda t: (-t.expected_learning_gain, t.id))
            tiers.append(ready)
            done.update(task.id for task in ready)
            for task in ready:
                remaining.pop(task.id)
        return tiers

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class TaskOutcome(BaseModel):
    """What actually happened when a planned task ran."""

    model_config = ConfigDict(extra="ignore")

    task_id: str
    capability: str
    node_id: str = ""
    """Unique execution identity; ``task_id`` remains the logical plan id."""
    provider: str = ""
    skill_id: str = ""
    status: Literal["completed", "incomplete", "failed", "skipped", "blocked"] = "completed"
    satisfied: bool = False
    """Whether ``done_when`` held afterwards. Running is not finishing."""
    detail: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    learner_message: str = ""
    tokens_used: int = 0
    duration_ms: int = 0
    heavy: bool = False
    held: bool = False
    revision: int = 0

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


__all__ = [
    "CandidateAction",
    "Cost",
    "DoneCondition",
    "DoneKind",
    "OrchestrationPlan",
    "HoldDecision",
    "PlannedTask",
    "TaskOutcome",
    "UnknownCapability",
]
