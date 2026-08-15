"""The limits that keep an autonomous loop from running away.

Every rule here is enforced in code before a task executes.  None of it lives in
a prompt, because a prompt is a request and a budget is not negotiable:

* step and replan ceilings, token and wall-clock budgets;
* a capability allow-list — a plan may only name registered, enabled capabilities;
* a cap on expensive artifact generation per task;
* irreversible actions must be confirmed by the learner first;
* every decision must carry a rationale the learner could read;
* deviating from the literal request requires a negotiation sentence.

A rejected plan is not a crash: :func:`check_plan` returns the violations and the
loop degrades — replans, asks, or stops with a reason — rather than proceeding.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..state.capabilities import Capability, UnknownCapability, info, parse
from ..state.session_state import Goal
from .contracts import HoldDecision, OrchestrationPlan, PlannedTask


class Violation(StrEnum):
    STEP_BUDGET = "step_budget_exhausted"
    REPLAN_BUDGET = "replan_budget_exhausted"
    TOKEN_BUDGET = "token_budget_exhausted"
    TIME_BUDGET = "time_budget_exhausted"
    HEAVY_ARTIFACT_CAP = "heavy_artifact_cap_reached"
    CAPABILITY_NOT_ALLOWED = "capability_not_allowed"
    MISSING_RATIONALE = "missing_rationale"
    MISSING_NEGOTIATION = "missing_negotiation"
    UNCONFIRMED_IRREVERSIBLE = "unconfirmed_irreversible_action"
    EMPTY_PLAN = "empty_plan"
    TOO_MANY_TASKS = "too_many_tasks"


MAX_TASKS_PER_ROUND = 6
"""A longer plan is a guess; the loop replans after each round anyway."""
MAX_REVISIONS_PER_TASK = 2
MAX_OPEN_HOLDS = 6


@dataclass(frozen=True, slots=True)
class GuardrailFinding:
    """One rejected thing, with a reason that can be shown to the learner."""

    violation: Violation
    detail: str
    task_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation": str(self.violation),
            "detail": self.detail,
            "task_id": self.task_id,
        }


@dataclass(frozen=True, slots=True)
class GuardrailVerdict:
    """Whether the plan may run, and which tasks survived."""

    findings: tuple[GuardrailFinding, ...] = ()
    allowed_tasks: tuple[PlannedTask, ...] = ()
    fatal: bool = False
    """True when the run cannot continue at all, not merely that a task was cut."""

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def runnable(self) -> bool:
        return bool(self.allowed_tasks) and not self.fatal

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [item.to_dict() for item in self.findings],
            "allowed": [task.id for task in self.allowed_tasks],
            "fatal": self.fatal,
        }


@dataclass
class Budget:
    """The mutable half of the guardrails, persisted on ``session_state``."""

    steps_used: int = 0
    max_steps: int = 24
    replans_used: int = 0
    max_replans: int = 6
    tokens_used: int = 0
    token_budget: int = 400_000
    wall_ms_used: int = 0
    wall_ms_budget: int = 1_800_000
    heavy_artifacts_used: int = 0
    max_heavy_artifacts: int = 6
    forged_skills_used: int = 0
    max_forged_skills: int = 1

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> Budget:
        data = dict(value or {})
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: int(v) for k, v in data.items() if k in known and v is not None})

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    # -- exhaustion checks ---------------------------------------------------

    @property
    def steps_exhausted(self) -> bool:
        return self.steps_used >= self.max_steps

    @property
    def replans_exhausted(self) -> bool:
        return self.replans_used >= self.max_replans

    @property
    def tokens_exhausted(self) -> bool:
        return self.tokens_used >= self.token_budget

    @property
    def time_exhausted(self) -> bool:
        return self.wall_ms_used >= self.wall_ms_budget

    @property
    def heavy_exhausted(self) -> bool:
        return self.heavy_artifacts_used >= self.max_heavy_artifacts

    def exhausted(self) -> Violation | None:
        if self.steps_exhausted:
            return Violation.STEP_BUDGET
        if self.tokens_exhausted:
            return Violation.TOKEN_BUDGET
        if self.time_exhausted:
            return Violation.TIME_BUDGET
        return None

    # -- consumption ---------------------------------------------------------

    def spend_step(self, *, heavy: bool = False, tokens: int = 0, wall_ms: int = 0) -> None:
        self.steps_used += 1
        self.tokens_used += max(0, int(tokens))
        self.wall_ms_used += max(0, int(wall_ms))
        if heavy:
            self.heavy_artifacts_used += 1

    def spend_replan(self) -> None:
        self.replans_used += 1


def allowed_capabilities(skills: Iterable[Mapping[str, Any]]) -> set[str]:
    """The allow-list: capabilities some enabled, executable skill actually provides."""

    allowed: set[str] = set()
    for row in skills:
        if not row.get("enabled", True) or not row.get("provider"):
            continue
        allowed.update(str(tag) for tag in (row.get("capabilities") or ()))
    return allowed


def _is_irreversible(capability: Capability) -> bool:
    return info(capability).irreversible


def _task_deviates(task: PlannedTask, goal: Goal, requested: frozenset[str]) -> bool:
    """Whether running this task is not what the learner literally asked for."""

    if task.knowledge_point_id and goal.knowledge_points:
        if task.knowledge_point_id not in goal.knowledge_points:
            return True
    if requested and task.capability not in requested:
        return True
    return False


def check_plan(
    plan: OrchestrationPlan,
    *,
    goal: Goal,
    budget: Budget,
    skills: Sequence[Mapping[str, Any]],
    requested_capabilities: frozenset[str] = frozenset(),
    confirmed_actions: frozenset[str] = frozenset(),
    settings_allow_list: frozenset[str] | None = None,
) -> GuardrailVerdict:
    """Decide which of the plan's tasks may run.

    Budget exhaustion is fatal — the run stops with a reason.  A single bad task
    is not: it is dropped, the finding is recorded, and the rest proceeds, which
    keeps one malformed task from wasting a learner's whole session.
    """

    findings: list[GuardrailFinding] = []

    exhausted = budget.exhausted()
    if exhausted is not None:
        return GuardrailVerdict(
            findings=(
                GuardrailFinding(
                    exhausted,
                    f"运行预算已用尽（steps {budget.steps_used}/{budget.max_steps}、"
                    f"tokens {budget.tokens_used}/{budget.token_budget}）",
                ),
            ),
            fatal=True,
        )

    if not plan.tasks:
        if plan.awaits_user:
            # Waiting for the learner with nothing queued is a legitimate plan.
            return GuardrailVerdict()
        return GuardrailVerdict(
            findings=(GuardrailFinding(Violation.EMPTY_PLAN, "计划为空且未等待学习者"),),
        )

    if len(plan.tasks) > MAX_TASKS_PER_ROUND:
        findings.append(
            GuardrailFinding(
                Violation.TOO_MANY_TASKS,
                f"一轮最多 {MAX_TASKS_PER_ROUND} 个任务，收到 {len(plan.tasks)} 个；已截断",
            )
        )

    allow = allowed_capabilities(skills)
    if settings_allow_list is not None:
        allow &= set(settings_allow_list)

    allowed: list[PlannedTask] = []
    heavy_planned = budget.heavy_artifacts_used

    conversational_planned = 0
    for task in plan.tasks[:MAX_TASKS_PER_ROUND]:
        try:
            capability = parse(task.capability)
        except UnknownCapability:
            findings.append(
                GuardrailFinding(
                    Violation.CAPABILITY_NOT_ALLOWED,
                    f"未知能力 {task.capability!r}",
                    task.id,
                )
            )
            continue

        if task.capability not in allow:
            findings.append(
                GuardrailFinding(
                    Violation.CAPABILITY_NOT_ALLOWED,
                    f"能力 {task.capability} 不在白名单内或没有可用 provider",
                    task.id,
                )
            )
            continue

        if info(capability).conversational:
            conversational_planned += 1
            if conversational_planned > 1:
                findings.append(
                    GuardrailFinding(
                        Violation.TOO_MANY_TASKS,
                        "一轮最多安排一个对话类任务",
                        task.id,
                    )
                )
                continue

        if not task.rationale.strip():
            findings.append(
                GuardrailFinding(
                    Violation.MISSING_RATIONALE,
                    "每个决策都必须带可展示给学习者的理由",
                    task.id,
                )
            )
            continue

        if _is_irreversible(capability) and task.capability not in confirmed_actions:
            findings.append(
                GuardrailFinding(
                    Violation.UNCONFIRMED_IRREVERSIBLE,
                    f"{info(capability).label} 是不可逆操作，需要学习者确认后才能执行",
                    task.id,
                )
            )
            continue

        deviating = _task_deviates(task, goal, requested_capabilities)
        if deviating and not (plan.negotiation or "").strip():
            findings.append(
                GuardrailFinding(
                    Violation.MISSING_NEGOTIATION,
                    "计划偏离了学习者的字面要求，必须先给出协商话术",
                    task.id,
                )
            )
            continue

        if task.estimated_cost.heavy_artifact:
            if heavy_planned >= budget.max_heavy_artifacts:
                findings.append(
                    GuardrailFinding(
                        Violation.HEAVY_ARTIFACT_CAP,
                        f"本任务的重资产生成次数已达上限 {budget.max_heavy_artifacts}",
                        task.id,
                    )
                )
                continue
            heavy_planned += 1

        allowed.append(task)

    return GuardrailVerdict(findings=tuple(findings), allowed_tasks=tuple(allowed))


def apply_hold_policy(
    decisions: Sequence[HoldDecision],
    board: Mapping[str, Any],
    budget: Budget,
    *,
    goal_satisfied: bool = False,
) -> list[HoldDecision]:
    """Apply deterministic hold limits before any model decision is executed."""

    holds = dict(board.get("holds") or {})
    result: list[HoldDecision] = []
    for decision in decisions:
        row = holds.get(decision.task_key)
        if row is None:
            continue
        revisions = int(row.get("revisions") or 0)
        action = decision.action
        instruction = decision.instruction.strip()
        if action == "revise" and not instruction:
            action = "close"
        if (
            action == "revise"
            and (
                revisions >= MAX_REVISIONS_PER_TASK
                or budget.exhausted() is not None
                or goal_satisfied
                or len(holds) > MAX_OPEN_HOLDS
            )
        ):
            action = "close"
            instruction = ""
        result.append(HoldDecision(task_key=decision.task_key, action=action, instruction=instruction))
    if len(holds) > MAX_OPEN_HOLDS:
        known = {item.task_key for item in result}
        result.extend(
            HoldDecision(task_key=key, action="close")
            for key in holds
            if key not in known
        )
        return [item.model_copy(update={"action": "close", "instruction": ""}) for item in result]
    return result


def check_replan(budget: Budget) -> GuardrailFinding | None:
    """Whether another replan is permitted."""

    if budget.replans_exhausted:
        return GuardrailFinding(
            Violation.REPLAN_BUDGET,
            f"重规划次数已达上限 {budget.max_replans}，停止循环并交还给学习者",
        )
    return None


def degrade_message(findings: Sequence[GuardrailFinding]) -> str:
    """One Chinese sentence a learner can act on, built from the findings."""

    if not findings:
        return ""
    reasons = "；".join(dict.fromkeys(item.detail for item in findings))
    return f"这一步没有按原计划继续：{reasons}。"


__all__ = [
    "MAX_TASKS_PER_ROUND",
    "MAX_REVISIONS_PER_TASK",
    "MAX_OPEN_HOLDS",
    "apply_hold_policy",
    "Budget",
    "GuardrailFinding",
    "GuardrailVerdict",
    "Violation",
    "allowed_capabilities",
    "check_plan",
    "check_replan",
    "degrade_message",
]
