"""Candidate scoring, completion predicates and guardrails.

These four modules are pure, so the properties the refactor is judged on can be
asserted here without a database or a model.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from lingxilearn.runtime import candidates as candidate_module
from lingxilearn.runtime.candidates import WorldState, best, deviates, eligible_only, generate
from lingxilearn.runtime.completion import CompletionContext, evaluate
from lingxilearn.runtime.contracts import (
    Cost,
    DoneCondition,
    OrchestrationPlan,
    PlannedTask,
)
from lingxilearn.runtime.guardrails import (
    Budget,
    Violation,
    allowed_capabilities,
    check_plan,
    check_replan,
)
from lingxilearn.state.gain import ProfileView
from lingxilearn.state.session_state import Goal

NOW = datetime(2026, 8, 14, tzinfo=UTC)


def skill(skill_id: str, capability: str, provider: str, **cost) -> dict:
    return {
        "skill_id": skill_id,
        "capabilities": [capability],
        "provider": provider,
        "enabled": True,
        "preconditions": {},
        "cost": {
            "latency_class": "interactive",
            "latency_weight": 1.0,
            "heavy_artifact": False,
            "blocking": True,
            **cost,
        },
    }


REGISTRY = [
    skill("lesson-intro", "content.lesson_intro", "lesson_intro", heavy_artifact=True),
    skill("interactive-lecture-deck", "content.deck", "lecture_deck", heavy_artifact=True,
          latency_weight=2.0),
    skill("interactive-visual-explainer", "content.visual", "visual_explainer",
          heavy_artifact=True, latency_weight=2.0),
    skill("prerequisite-analyzer", "graph.prerequisite", "prerequisite_analyzer"),
    skill("quiz-generator", "assess.generate", "quiz_generator"),
    skill("adaptive-pedagogy", "teach.strategy", "adaptive_pedagogy"),
    skill("knowledge-qa", "dialog.answer", "answer_user"),
    skill("review-scheduler", "review.schedule", "review_scheduler"),
    skill("deterministic-grader", "assess.grade", "deterministic_grader"),
    skill("curriculum-graph-builder", "graph.build", "curriculum_graph"),
]

GOAL = Goal(
    goal_type="learn",
    topic="TCP 拥塞控制",
    knowledge_points=("tcp-congestion",),
    raw_utterance="帮我讲讲 TCP 拥塞控制",
)


# --- acceptance criterion 1: the same input diverges on profile -------------


def test_same_goal_different_profiles_produce_different_top_choices() -> None:
    """The headline property: routing is computed from state, not from the utterance."""

    novice = WorldState(
        target=ProfileView.unseen("tcp-congestion", "TCP 拥塞控制"),
        now=NOW,
    )
    blocked = WorldState(
        target=ProfileView(
            knowledge_point_id="tcp-congestion",
            knowledge_point="TCP 拥塞控制",
            mastery=0.30,
            evidence_count=4,
            prerequisites=("sliding-window",),
        ),
        prerequisites=(
            ProfileView(
                knowledge_point_id="sliding-window",
                knowledge_point="滑动窗口",
                mastery=0.18,
                evidence_count=3,
            ),
        ),
        now=NOW,
    )

    novice_top = best(generate(goal=GOAL, world=novice, skills=REGISTRY))
    blocked_top = best(generate(goal=GOAL, world=blocked, skills=REGISTRY))

    assert novice_top is not None and blocked_top is not None
    assert (novice_top.capability, novice_top.knowledge_point_id) != (
        blocked_top.capability,
        blocked_top.knowledge_point_id,
    ), "identical input against different profiles must not take the same path"
    # And specifically: the blocked learner gets worked on where they are stuck,
    # which is the prerequisite, not the knowledge point they named.
    assert novice_top.knowledge_point_id == "tcp-congestion"
    assert blocked_top.knowledge_point_id == "sliding-window"


def test_a_learner_with_material_and_thin_evidence_gets_assessed() -> None:
    world = WorldState(
        target=ProfileView(
            knowledge_point_id="tcp-congestion",
            knowledge_point="TCP 拥塞控制",
            mastery=0.5,
            evidence_count=0,
            prerequisites=("sliding-window",),
        ),
        prerequisites=(
            ProfileView(knowledge_point_id="sliding-window", mastery=0.9, evidence_count=5),
        ),
        artifacts=frozenset({"lesson-intro", "lecture-deck"}),
        now=NOW,
    )
    top = best(generate(goal=GOAL, world=world, skills=REGISTRY))
    assert top is not None
    assert top.capability == "assess.generate"


def test_misconceptions_promote_targeted_explanation_over_new_material() -> None:
    registry = [*REGISTRY, skill("adaptive-pedagogy-explain", "teach.explain", "adaptive_pedagogy")]
    world = WorldState(
        target=ProfileView(
            knowledge_point_id="tcp-congestion",
            mastery=0.4,
            evidence_count=4,
            misconceptions=("把拥塞窗口当成接收窗口",),
            prerequisites=("sliding-window",),
        ),
        prerequisites=(
            ProfileView(knowledge_point_id="sliding-window", mastery=0.85, evidence_count=4),
        ),
        artifacts=frozenset({"lesson-intro", "lecture-deck"}),
        has_open_quiz=True,
        now=NOW,
    )
    top = best(generate(goal=GOAL, world=world, skills=registry))
    assert top is not None
    assert top.capability == "teach.explain"
    assert "误区" in top.reason


def test_scoring_is_deterministic_across_runs() -> None:
    world = WorldState(target=ProfileView.unseen("tcp-congestion"), now=NOW)
    first = [(c.capability, c.utility) for c in generate(goal=GOAL, world=world, skills=REGISTRY)]
    second = [(c.capability, c.utility) for c in generate(goal=GOAL, world=world, skills=REGISTRY)]
    assert first == second


def test_ineligible_candidates_are_kept_with_a_reason() -> None:
    """"Why didn't it do X" has to be answerable from the trace."""

    world = WorldState(
        target=ProfileView.unseen("tcp-congestion"),
        artifacts=frozenset({"lesson-intro"}),
        now=NOW,
    )
    produced = generate(goal=GOAL, world=world, skills=REGISTRY)
    intro = next(c for c in produced if c.capability == "content.lesson_intro")
    assert not intro.eligible
    assert intro.blocked_by

    grade = next(c for c in produced if c.capability == "assess.grade")
    assert not grade.eligible
    assert grade.blocked_by == "没有待判分的作答"


def test_eligible_candidates_come_first_and_are_sorted_by_utility() -> None:
    world = WorldState(target=ProfileView.unseen("tcp-congestion"), now=NOW)
    produced = generate(goal=GOAL, world=world, skills=REGISTRY)
    eligible = eligible_only(produced)
    assert produced[: len(eligible)] == eligible
    assert eligible == sorted(
        eligible, key=lambda c: (-c.utility, c.capability, c.knowledge_point_id, c.skill_id)
    )


def test_heavy_artifacts_cost_more_than_their_latency() -> None:
    world = WorldState(target=ProfileView.unseen("tcp-congestion"), now=NOW)
    produced = {c.capability: c for c in generate(goal=GOAL, world=world, skills=REGISTRY)}
    assert produced["content.deck"].cost > produced["graph.prerequisite"].cost


def test_a_due_review_outranks_starting_new_material() -> None:
    world = WorldState(
        target=ProfileView(
            knowledge_point_id="three-way-handshake",
            mastery=0.5,
            evidence_count=4,
            review_priority=0.9,
            review_due_at=NOW - timedelta(days=7),
        ),
        artifacts=frozenset({"lesson-intro", "lecture-deck"}),
        has_open_quiz=True,
        now=NOW,
    )
    top = best(generate(goal=GOAL, world=world, skills=REGISTRY))
    assert top is not None
    assert top.capability == "review.schedule"


def test_deviation_is_detected_for_another_knowledge_point() -> None:
    world = WorldState(target=ProfileView.unseen("tcp-congestion"), now=NOW)
    candidate = generate(goal=GOAL, world=world, skills=REGISTRY)[0]
    assert not deviates(GOAL, candidate, world)

    off_target = candidate.model_copy(update={"knowledge_point_id": "sliding-window"})
    assert deviates(GOAL, off_target, world)


def test_requested_capability_raises_but_does_not_force_the_ranking() -> None:
    base = WorldState(
        target=ProfileView(
            knowledge_point_id="tcp-congestion", mastery=0.30, evidence_count=4,
            prerequisites=("sliding-window",),
        ),
        prerequisites=(
            ProfileView(knowledge_point_id="sliding-window", mastery=0.18, evidence_count=3),
        ),
        now=NOW,
    )
    asked = replace(base, requested_capabilities=frozenset({"content.visual"}))

    plain = {c.capability: c.utility for c in generate(goal=GOAL, world=base, skills=REGISTRY)}
    nudged = {c.capability: c.utility for c in generate(goal=GOAL, world=asked, skills=REGISTRY)}
    assert nudged["content.visual"] > plain["content.visual"]
    # Still loses to unblocking the prerequisite the learner is actually stuck on.
    assert best(generate(goal=GOAL, world=asked, skills=REGISTRY)).knowledge_point_id == (
        "sliding-window"
    )


def test_unknown_capability_tags_in_the_registry_are_skipped() -> None:
    rogue = [*REGISTRY, skill("rogue", "teach.vibes", "nobody")]
    world = WorldState(target=ProfileView.unseen("tcp-congestion"), now=NOW)
    produced = generate(goal=GOAL, world=world, skills=rogue)
    assert all(c.capability != "teach.vibes" for c in produced)


def test_min_utility_threshold_is_applied() -> None:
    assert candidate_module.MIN_UTILITY > 0


# --- completion: running is not finishing -----------------------------------


class _Probe:
    def __init__(self, existing: set[str], valid: set[str]) -> None:
        self._existing = existing
        self._valid = valid

    def exists(self, artifact: str) -> bool:
        return artifact in self._existing

    def is_valid(self, artifact: str) -> bool:
        return artifact in self._valid


def test_artifact_that_exists_but_fails_validation_is_not_done() -> None:
    context = CompletionContext(artifacts=_Probe({"lecture-deck"}, set()))
    verdict = evaluate(DoneCondition(kind="artifact_valid", artifact="lecture-deck"), context)
    assert not verdict.satisfied
    assert "未通过校验" in verdict.detail


def test_evidence_condition_counts_matching_signals() -> None:
    context = CompletionContext(
        evidence=[
            {"signal": "correct", "knowledge_point": "tcp-congestion"},
            {"signal": "incorrect", "knowledge_point": "tcp-congestion"},
        ]
    )
    assert evaluate(DoneCondition(kind="evidence_observed", signal="correct"), context)
    assert not evaluate(
        DoneCondition(kind="evidence_observed", signal="correct", min_count=2), context
    )


def test_profile_condition_reads_the_current_mastery() -> None:
    context = CompletionContext(profile={"tcp-congestion": {"mastery": 0.62}})
    assert evaluate(
        DoneCondition(kind="profile_reaches", knowledge_point_id="tcp-congestion", mastery=0.6),
        context,
    )
    assert not evaluate(
        DoneCondition(kind="profile_reaches", knowledge_point_id="tcp-congestion", mastery=0.8),
        context,
    )


def test_all_of_and_any_of_compose() -> None:
    context = CompletionContext(
        artifacts=_Probe({"lesson-intro"}, {"lesson-intro"}),
        evidence=[{"signal": "correct", "knowledge_point": "kp"}],
    )
    both = DoneCondition(
        kind="all_of",
        conditions=[
            DoneCondition(kind="artifact_valid", artifact="lesson-intro"),
            DoneCondition(kind="evidence_observed", signal="correct"),
        ],
    )
    either = DoneCondition(
        kind="any_of",
        conditions=[
            DoneCondition(kind="artifact_valid", artifact="lecture-deck"),
            DoneCondition(kind="evidence_observed", signal="correct"),
        ],
    )
    assert evaluate(both, context)
    assert evaluate(either, context)


def test_prose_done_conditions_are_rejected_at_parse_time() -> None:
    with pytest.raises(ValueError):
        DoneCondition(kind="profile_reaches")  # no knowledge point to check
    with pytest.raises(ValueError):
        DoneCondition(kind="artifact_valid")  # no artifact named
    with pytest.raises(ValueError):
        DoneCondition(kind="evidence_observed")  # no signal named


def test_unknown_condition_kinds_fail_closed() -> None:
    condition = DoneCondition(kind="always")
    object.__setattr__(condition, "kind", "vibes")
    assert not evaluate(condition, CompletionContext())


# --- guardrails --------------------------------------------------------------


def _task(task_id: str, capability: str, **overrides) -> PlannedTask:
    payload = {
        "id": task_id,
        "capability": capability,
        "done_when": DoneCondition(kind="always"),
        "rationale": "因为档案显示这里最薄弱",
        "knowledge_point_id": "tcp-congestion",
    }
    payload.update(overrides)
    return PlannedTask(**payload)


def _plan(*tasks: PlannedTask, **overrides) -> OrchestrationPlan:
    return OrchestrationPlan(tasks=list(tasks), **overrides)


def test_allow_list_excludes_capabilities_without_a_provider() -> None:
    registry = [*REGISTRY, {"skill_id": "x", "capabilities": ["meta.report"], "provider": "",
                            "enabled": True, "cost": {}, "preconditions": {}}]
    allow = allowed_capabilities(registry)
    assert "meta.report" not in allow
    assert "content.deck" in allow


def test_a_capability_outside_the_allow_list_is_rejected() -> None:
    verdict = check_plan(
        _plan(_task("t1", "meta.report")),
        goal=GOAL,
        budget=Budget(),
        skills=REGISTRY,
    )
    assert not verdict.runnable
    assert verdict.findings[0].violation is Violation.CAPABILITY_NOT_ALLOWED


def test_a_task_without_a_rationale_is_rejected() -> None:
    with pytest.raises(ValueError):
        _task("t1", "content.deck", rationale="")


def test_deviating_without_negotiation_is_rejected() -> None:
    off_target = _task("t1", "content.deck", knowledge_point_id="sliding-window")
    verdict = check_plan(_plan(off_target), goal=GOAL, budget=Budget(), skills=REGISTRY)
    assert not verdict.runnable
    assert verdict.findings[0].violation is Violation.MISSING_NEGOTIATION

    negotiated = check_plan(
        _plan(off_target, negotiation="先花 8 分钟把滑动窗口过一遍再回来，可以吗？"),
        goal=GOAL,
        budget=Budget(),
        skills=REGISTRY,
    )
    assert negotiated.runnable


def test_irreversible_actions_need_confirmation() -> None:
    verdict = check_plan(
        _plan(_task("t1", "graph.build")), goal=GOAL, budget=Budget(), skills=REGISTRY
    )
    assert not verdict.runnable
    assert verdict.findings[0].violation is Violation.UNCONFIRMED_IRREVERSIBLE

    confirmed = check_plan(
        _plan(_task("t1", "graph.build")),
        goal=GOAL,
        budget=Budget(),
        skills=REGISTRY,
        confirmed_actions=frozenset({"graph.build"}),
    )
    assert confirmed.runnable


def test_heavy_artifact_cap_stops_the_third_deck() -> None:
    heavy = _task("t1", "content.deck", estimated_cost=Cost(heavy_artifact=True))
    budget = Budget(heavy_artifacts_used=2, max_heavy_artifacts=2)
    verdict = check_plan(_plan(heavy), goal=GOAL, budget=budget, skills=REGISTRY)
    assert not verdict.runnable
    assert verdict.findings[0].violation is Violation.HEAVY_ARTIFACT_CAP


def test_exhausted_step_budget_is_fatal() -> None:
    verdict = check_plan(
        _plan(_task("t1", "teach.strategy")),
        goal=GOAL,
        budget=Budget(steps_used=24, max_steps=24),
        skills=REGISTRY,
    )
    assert verdict.fatal
    assert verdict.findings[0].violation is Violation.STEP_BUDGET


def test_replan_budget_stops_the_loop() -> None:
    assert check_replan(Budget(replans_used=1, max_replans=6)) is None
    finding = check_replan(Budget(replans_used=6, max_replans=6))
    assert finding is not None and finding.violation is Violation.REPLAN_BUDGET


def test_one_bad_task_does_not_kill_the_whole_plan() -> None:
    verdict = check_plan(
        _plan(_task("t1", "meta.report"), _task("t2", "teach.strategy")),
        goal=GOAL,
        budget=Budget(),
        skills=REGISTRY,
    )
    assert verdict.runnable
    assert [task.id for task in verdict.allowed_tasks] == ["t2"]
    assert len(verdict.findings) == 1


def test_plans_are_truncated_to_the_round_limit() -> None:
    tasks = [_task(f"t{i}", "teach.strategy") for i in range(5)]
    verdict = check_plan(_plan(*tasks), goal=GOAL, budget=Budget(), skills=REGISTRY)
    assert len(verdict.allowed_tasks) == 3
    assert any(f.violation is Violation.TOO_MANY_TASKS for f in verdict.findings)


def test_an_empty_plan_is_only_legal_when_waiting_for_the_learner() -> None:
    assert check_plan(_plan(), goal=GOAL, budget=Budget(), skills=REGISTRY).findings
    assert not check_plan(
        _plan(awaits_user=True), goal=GOAL, budget=Budget(), skills=REGISTRY
    ).findings


def test_budget_round_trips_through_the_session_state_json() -> None:
    budget = Budget(steps_used=3, heavy_artifacts_used=1)
    assert Budget.from_dict(budget.to_dict()) == budget
    # Unknown keys from an older row must not break the load.
    assert Budget.from_dict({"steps_used": 2, "legacy_field": 9}).steps_used == 2


# --- plan contracts ----------------------------------------------------------


def test_plan_orders_tasks_by_dependency() -> None:
    plan = _plan(
        _task("b", "teach.strategy", depends_on=["a"]),
        _task("a", "graph.prerequisite"),
        _task("c", "assess.generate", depends_on=["b"]),
    )
    assert [task.id for task in plan.ordered_tasks()] == ["a", "b", "c"]


def test_plan_rejects_unknown_and_self_dependencies() -> None:
    with pytest.raises(ValueError):
        _plan(_task("a", "teach.strategy", depends_on=["ghost"]))
    with pytest.raises(ValueError):
        _plan(_task("a", "teach.strategy", depends_on=["a"]))


def test_plan_rejects_duplicate_task_ids() -> None:
    with pytest.raises(ValueError):
        _plan(_task("a", "teach.strategy"), _task("a", "assess.generate"))


def test_cyclic_dependencies_raise_instead_of_deadlocking() -> None:
    plan = _plan(_task("a", "teach.strategy"), _task("b", "assess.generate", depends_on=["a"]))
    object.__setattr__(plan.tasks[0], "depends_on", ["b"])
    with pytest.raises(ValueError, match="cyclic"):
        plan.ordered_tasks()


def test_a_task_cannot_name_a_capability_outside_the_vocabulary() -> None:
    """Pydantic wraps the domain error, but the plan is still rejected."""

    with pytest.raises(ValidationError) as caught:
        _task("a", "teach.vibes")
    assert "unknown capability" in str(caught.value)
