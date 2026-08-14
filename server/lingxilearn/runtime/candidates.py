"""Generate and score the actions the orchestrator is allowed to choose from.

This is the deterministic half of routing.  Given a goal and the learner's
profile, it enumerates every registered skill whose preconditions currently hold
and scores each as ``expected_learning_gain / cost``.  The model never invents an
action; it reorders a list produced here.

That split is what makes acceptance criterion 1 testable: the same utterance
against two different profiles produces two different candidate orderings before
any model is involved.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from ..state.capabilities import Capability, UnknownCapability, info, parse
from ..state.gain import ProfileView, estimate
from ..state.session_state import Goal
from .contracts import CandidateAction, Cost

MIN_UTILITY = 0.05
"""Below this an action is not worth a turn; it stays in the trace as ineligible."""


@dataclass(frozen=True, slots=True)
class WorldState:
    """Everything candidate generation is allowed to look at.

    A value object rather than a live session: scoring must be reproducible, and
    a test has to be able to construct one by hand.
    """

    target: ProfileView
    prerequisites: tuple[ProfileView, ...] = ()
    due_for_review: tuple[ProfileView, ...] = ()
    requested_capabilities: frozenset[str] = frozenset()
    """Capabilities the learner explicitly asked for; raises but never forces rank."""
    awaiting_user_reply: bool = False
    has_open_quiz: bool = False
    has_ungraded_submission: bool = False
    artifacts: frozenset[str] = frozenset()
    open_questions: int = 0
    goal_type: str = "learn"
    now: datetime = field(default_factory=lambda: datetime.now(UTC))

    def enriched(self, view: ProfileView, *, is_target: bool) -> ProfileView:
        """A profile view with the artifact and quiz facts the scorer reads.

        Artifacts and open quizzes are task-scoped and belong to the goal's
        target, so a prerequisite subject sees none of them — which is correct:
        nothing has been produced for it yet.
        """

        return replace(
            view,
            has_lesson_intro=is_target and "lesson-intro" in self.artifacts,
            has_deck=is_target and "lecture-deck" in self.artifacts,
            has_visual=is_target and "visual" in self.artifacts,
            has_open_quiz=is_target and self.has_open_quiz,
            open_questions=self.open_questions if is_target else 0,
        )

    def subjects(self) -> list[tuple[ProfileView, bool]]:
        """The knowledge points worth acting on this round, target first.

        A prerequisite the learner has not met is its own subject: when the
        target is blocked, the useful action is teaching *the prerequisite*, not
        teaching the target more slowly.  Acting on one is a deviation from the
        literal request, which is exactly why guardrails then demand a
        negotiation sentence before it runs.
        """

        found: list[tuple[ProfileView, bool]] = [(self.target, True)]
        for prerequisite in self.prerequisites:
            if prerequisite.is_weak:
                found.append((prerequisite, False))
        return found


@dataclass(frozen=True, slots=True)
class RegisteredSkill:
    """The registry row, reduced to what candidate generation needs."""

    skill_id: str
    capabilities: tuple[str, ...]
    provider: str
    cost: dict[str, Any]
    preconditions: dict[str, Any]
    enabled: bool = True

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> RegisteredSkill:
        return cls(
            skill_id=str(row.get("skill_id") or ""),
            capabilities=tuple(str(c) for c in (row.get("capabilities") or ())),
            provider=str(row.get("provider") or ""),
            cost=dict(row.get("cost") or {}),
            preconditions=dict(row.get("preconditions") or {}),
            enabled=bool(row.get("enabled", True)),
        )


def _precondition_block(
    capability: Capability,
    skill: RegisteredSkill,
    world: WorldState,
    view: ProfileView,
    *,
    is_target: bool,
) -> str:
    """Return why this skill cannot run right now, or "" when it can.

    Preconditions are about *state*, not about intent.  "The learner did not ask
    for a diagram" is not a precondition — that is ranking, and it belongs in the
    gain estimate where it can be outvoted by evidence.
    """

    if not skill.enabled:
        return "技能未启用"
    if not skill.provider:
        return "没有可执行的 provider"

    match capability:
        case Capability.ASSESS_GRADE:
            if not (is_target and world.has_ungraded_submission):
                return "没有待判分的作答"
        case Capability.ASSESS_INTERPRET:
            if view.evidence_count == 0:
                return "还没有任何作答证据可解读"
        case Capability.CONTENT_LESSON_INTRO:
            if view.has_lesson_intro:
                return "课程引入已存在"
        case Capability.CONTENT_DECK:
            if view.has_deck:
                return "讲义课件已存在"
        case Capability.ASSESS_GENERATE:
            if view.has_open_quiz:
                return "已有未作答的检测题"
        case Capability.DIALOG_ANSWER:
            if not view.open_questions:
                return "没有待回答的提问"
        case Capability.META_REPORT:
            if not is_target:
                return "报告只针对当前目标"
            if view.evidence_count == 0:
                return "没有可用于报告的证据"
        case Capability.REVIEW_SCHEDULE:
            if not is_target:
                return "复习调度只针对当前目标"
            if not world.due_for_review and view.review_priority < 0.3:
                return "没有到期或高优先级的复习点"
        case Capability.META_AUTHOR_SKILL:
            # Forging is a last resort; it is never a normal candidate.
            return "仅在出现能力缺口时可用"
        case Capability.META_EVALUATE:
            return "评测不在学习者运行路径上"
        case Capability.DIALOG_NEGOTIATE:
            # Negotiation is attached to a deviating plan, not scheduled alone.
            return "协商随计划附带，不单独调度"
    return ""


def _prerequisite_reason(reason: str, view: ProfileView) -> str:
    """Mark a candidate as being about a prerequisite, not the requested point."""

    label = view.knowledge_point or view.knowledge_point_id
    return f"{reason}（前置知识「{label}」）"


def _cost_of(skill: RegisteredSkill, capability: Capability) -> Cost:
    detail = info(capability)
    return Cost(
        latency_class=str(skill.cost.get("latency_class") or "interactive"),
        latency_weight=float(skill.cost.get("latency_weight") or 1.0),
        heavy_artifact=bool(skill.cost.get("heavy_artifact") or detail.heavy_artifact),
        blocking=bool(skill.cost.get("blocking", True)),
        irreversible=detail.irreversible,
    )


def generate(
    *,
    goal: Goal,
    world: WorldState,
    skills: Sequence[Mapping[str, Any]],
) -> list[CandidateAction]:
    """Score every registered skill against the current state.

    Returns eligible candidates first, sorted by utility, then the ineligible
    ones with the reason they were excluded.  Ineligible candidates are kept
    because "why didn't it do X" is a question the trace has to answer.
    """

    eligible: list[CandidateAction] = []
    excluded: list[CandidateAction] = []

    for subject, is_target in world.subjects():
        view = world.enriched(subject, is_target=is_target)
        # Only the target is judged against prerequisites; a prerequisite
        # subject is the base case and would otherwise recurse forever.
        against = world.prerequisites if is_target else ()

        for row in skills:
            skill = RegisteredSkill.from_row(row)
            for tag in skill.capabilities:
                try:
                    capability = parse(tag)
                except UnknownCapability:
                    continue

                cost = _cost_of(skill, capability)
                block = _precondition_block(capability, skill, world, view, is_target=is_target)
                requested = is_target and tag in world.requested_capabilities
                gain = estimate(
                    capability,
                    view,
                    prerequisites=against,
                    now=world.now,
                    requested=requested,
                )
                utility = round(gain.value / cost.normalized, 4)
                candidate = CandidateAction(
                    capability=tag,
                    skill_id=skill.skill_id,
                    provider=skill.provider,
                    knowledge_point_id=view.knowledge_point_id,
                    gain=gain.value,
                    cost=cost.normalized,
                    utility=utility,
                    reason=gain.reason if is_target else _prerequisite_reason(gain.reason, view),
                    eligible=not block and utility >= MIN_UTILITY,
                    blocked_by=block or ("学习收益过低" if utility < MIN_UTILITY else ""),
                )
                (eligible if candidate.eligible else excluded).append(candidate)

    # Deterministic ordering: utility desc, then capability and knowledge point.
    # Ties must not depend on dict iteration order, or two identical profiles
    # could diverge for no reason.
    eligible.sort(key=lambda c: (-c.utility, c.capability, c.knowledge_point_id, c.skill_id))
    excluded.sort(key=lambda c: (c.capability, c.knowledge_point_id, c.skill_id))
    return eligible + excluded


def eligible_only(candidates: Sequence[CandidateAction]) -> list[CandidateAction]:
    return [item for item in candidates if item.eligible]


def best(candidates: Sequence[CandidateAction]) -> CandidateAction | None:
    """The deterministic fallback choice used when the model is unavailable."""

    return next((item for item in candidates if item.eligible), None)


def deviates(goal: Goal, candidate: CandidateAction, world: WorldState) -> bool:
    """True when acting on ``candidate`` is not what the learner literally asked for.

    Two shapes count as deviation: working on a different knowledge point than
    the goal names, and ignoring an explicitly requested capability in favour of
    something else.  Both require a negotiation sentence before execution.
    """

    if candidate.knowledge_point_id and goal.knowledge_points:
        if candidate.knowledge_point_id not in goal.knowledge_points:
            return True
    if world.requested_capabilities and candidate.capability not in world.requested_capabilities:
        return True
    return False


__all__ = [
    "MIN_UTILITY",
    "RegisteredSkill",
    "WorldState",
    "best",
    "deviates",
    "eligible_only",
    "generate",
]
