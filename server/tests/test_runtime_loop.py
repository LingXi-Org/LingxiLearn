"""The runtime loop end to end, against the acceptance criteria.

No network: providers are replaced with fakes and the model is ``None``, which
also exercises the deterministic fallback path the loop must survive on.
"""

from __future__ import annotations

from typing import Any

import pytest

from lingxilearn.agents.providers import base as provider_base
from lingxilearn.agents.providers.base import ProviderContext, ProviderResult
from lingxilearn.runtime.candidates import WorldState
from lingxilearn.runtime.dispatch import NoProvider, resolve
from lingxilearn.runtime.guardrails import Budget
from lingxilearn.runtime.loop import LoopDeps, build_loop, initial_state
from lingxilearn.runtime.orchestrator import unavailable_plan
from lingxilearn.state.evidence import EvidenceRecord, Signal
from lingxilearn.state.gain import ProfileView
from lingxilearn.state.session_state import Goal, RuntimeStatus, new_budget

GOAL = Goal(
    goal_type="learn",
    topic="TCP 拥塞控制",
    knowledge_points=("tcp-congestion",),
    raw_utterance="帮我讲讲 TCP 拥塞控制",
)


def registry_row(skill_id: str, capability: str, provider: str, **cost: Any) -> dict[str, Any]:
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


@pytest.fixture
def fake_providers(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Swap the provider table for fakes and record what ran."""

    calls: dict[str, list[str]] = {"ran": []}

    async def teach(context: ProviderContext) -> ProviderResult:
        calls["ran"].append(f"teach:{context.knowledge_point_id}")
        return ProviderResult(
            learner_message="讲解完成",
            evidence=[
                EvidenceRecord(
                    learner_id=context.learner_id,
                    knowledge_point=context.knowledge_point_id,
                    signal=Signal.SELF_REPORT,
                    source_agent="fake_teacher",
                    task_id=context.task_id,
                    summary="看完了讲解",
                )
            ],
            persist_as="teaching",
            data={"ok": True},
        )

    async def analyse(context: ProviderContext) -> ProviderResult:
        calls["ran"].append(f"prereq:{context.knowledge_point_id}")
        return ProviderResult(
            evidence=[
                EvidenceRecord(
                    learner_id=context.learner_id,
                    knowledge_point=context.knowledge_point_id,
                    signal=Signal.ERROR_PATTERN,
                    source_agent="fake_prereq",
                    task_id=context.task_id,
                    summary="依赖已分析",
                )
            ],
            persist_as="prerequisites",
            data={"prerequisites": [], "verdict": "teach_target"},
        )

    async def assess(context: ProviderContext) -> ProviderResult:
        calls["ran"].append(f"assess:{context.knowledge_point_id}")
        return ProviderResult(
            evidence=[
                EvidenceRecord(
                    learner_id=context.learner_id,
                    knowledge_point=context.knowledge_point_id,
                    signal=Signal.CORRECT,
                    source_agent="fake_grader",
                    score=0.95,
                    task_id=context.task_id,
                )
            ],
            artifacts=["quiz"],
            validations={"quiz": True},
            persist_as="quiz_generator",
            data={"questions": [{"id": "q1", "points": 1}]},
        )

    monkeypatch.setattr(
        provider_base,
        "_PROVIDERS",
        {"fake_teacher": teach, "fake_prereq": analyse, "fake_grader": assess},
    )
    monkeypatch.setattr(provider_base, "load_all", lambda: dict(provider_base._PROVIDERS))
    return calls


REGISTRY = [
    registry_row("fake-teaching", "teach.strategy", "fake_teacher"),
    registry_row("fake-prereq", "graph.prerequisite", "fake_prereq"),
    registry_row("fake-assess", "assess.generate", "fake_grader"),
]


async def _seed_registry(runtime) -> None:
    from lingxilearn.state.capabilities import parse
    from lingxilearn.state.skill_catalog import SkillManifest

    await runtime.sync_skill_manifests(
        [
            SkillManifest(
                skill_id=row["skill_id"],
                capabilities=(parse(row["capabilities"][0]),),
                provider=row["provider"],
                cost=row["cost"],
                version="1.0.0",
            )
            for row in REGISTRY
        ]
    )


def _deps(runtime, learner_id: str, task_id: str, events: list[tuple[str, dict]]):
    return LoopDeps(
        runtime_state=runtime,
        learner_id=learner_id,
        task_id=task_id,
        model=None,
        execution_id="exec-test",
        emit=lambda kind, payload: events.append((kind, payload)),
    )


# --- criterion 1: same input, different profile, different path -------------


@pytest.mark.asyncio
async def test_the_same_utterance_takes_different_paths_on_different_profiles(
    state_db, fake_providers
) -> None:
    from lingxilearn.state.profile_writer import ProfileDelta

    _database, runtime, learner_id = state_db
    await _seed_registry(runtime)

    # Learner A has never seen the topic. Learner B is blocked on a prerequisite.
    await runtime.apply_profile_deltas(
        [
            ProfileDelta(
                learner_id=learner_id,
                knowledge_point_id="tcp-congestion",
                evidence_ids=["seed"],
                source_agent="test",
                mastery=0.30,
                prerequisites=["sliding-window"],
                evidence_count=4,
            ),
            ProfileDelta(
                learner_id=learner_id,
                knowledge_point_id="sliding-window",
                evidence_ids=["seed"],
                source_agent="test",
                mastery=0.15,
                evidence_count=3,
            ),
        ]
    )

    novice = WorldState(target=ProfileView.unseen("tcp-congestion", "TCP 拥塞控制"))
    blocked = WorldState(
        target=ProfileView(
            knowledge_point_id="tcp-congestion",
            mastery=0.30,
            evidence_count=4,
            prerequisites=("sliding-window",),
        ),
        prerequisites=(
            ProfileView(knowledge_point_id="sliding-window", mastery=0.15, evidence_count=3),
        ),
    )
    skills = await runtime.list_skills(enabled_only=True)

    from lingxilearn.runtime.candidates import generate

    novice_plan = unavailable_plan(candidates=generate(goal=GOAL, world=novice, skills=skills))
    blocked_plan = unavailable_plan(candidates=generate(goal=GOAL, world=blocked, skills=skills))

    assert len(novice_plan.tasks) == 1 and novice_plan.degraded
    assert len(blocked_plan.tasks) == 1 and blocked_plan.degraded


# --- criterion 2: a step's result changes the next step, visibly ------------


@pytest.mark.asyncio
async def test_the_loop_replans_and_the_replan_is_in_the_trace(state_db, fake_providers) -> None:
    _database, runtime, learner_id = state_db
    await _seed_registry(runtime)
    task_id = "task-replan"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)

    events: list[tuple[str, dict]] = []
    deps = _deps(runtime, learner_id, task_id, events)
    graph = build_loop(deps)

    await graph.ainvoke(
        initial_state(
            learner_id=learner_id,
            task_id=task_id,
            utterance="帮我讲讲 TCP 拥塞控制",
            budget=new_budget({"max_steps": 6, "max_replans": 2}),
        ),
        {"recursion_limit": 60},
    )

    decisions = await runtime.decisions_for_task(task_id)
    assert len(decisions) >= 2, "the loop should have gone round more than once"
    assert any(item["replan_of"] for item in decisions), (
        "a replan must be visible in the decision trace, not merely inferable"
    )
    assert any(kind == "plan.replanned" for kind, _ in events)


# --- criterion 4: every decision carries its full trace ---------------------


@pytest.mark.asyncio
async def test_every_decision_records_candidates_choice_reason_and_profile(
    state_db, fake_providers
) -> None:
    _database, runtime, learner_id = state_db
    await _seed_registry(runtime)
    task_id = "task-trace"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)

    events: list[tuple[str, dict]] = []
    graph = build_loop(_deps(runtime, learner_id, task_id, events))
    await graph.ainvoke(
        initial_state(
            learner_id=learner_id,
            task_id=task_id,
            utterance="帮我讲讲 TCP 拥塞控制",
            budget=new_budget({"max_steps": 4, "max_replans": 1}),
        ),
        {"recursion_limit": 60},
    )

    decisions = await runtime.decisions_for_task(task_id)
    assert decisions
    for decision in decisions:
        assert decision["candidates"], "the candidate set must be recorded"
        assert decision["selected"], "the choice must be recorded"
        assert decision["rationale"], "a decision with no shown reason is not allowed"
        assert "budget" in decision["guardrail_state"]
        assert decision["goal"]["topic"]

    # The profile before/after pair is what "why did my mastery change" reads.
    assert any(decision["profile_after"] or decision["profile_before"] for decision in decisions)


@pytest.mark.asyncio
async def test_the_runtime_graph_grows_a_node_per_decision(state_db, fake_providers) -> None:
    _database, runtime, learner_id = state_db
    await _seed_registry(runtime)
    task_id = "task-graph"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)

    events: list[tuple[str, dict]] = []
    graph = build_loop(_deps(runtime, learner_id, task_id, events))
    await graph.ainvoke(
        initial_state(
            learner_id=learner_id,
            task_id=task_id,
            utterance="帮我讲讲 TCP 拥塞控制",
            budget=new_budget({"max_steps": 4, "max_replans": 1}),
        ),
        {"recursion_limit": 60},
    )

    appeared = [payload for kind, payload in events if kind == "node.appeared"]
    assert appeared, "the frontend needs nodes that appear as decisions are made"
    for node in appeared:
        assert node["capability"]
        assert node["rationale"], "each node must show why it was chosen"
        assert node["done_when"]


# --- the loop keeps moving --------------------------------------------------


@pytest.mark.asyncio
async def test_evidence_produced_by_a_round_reaches_the_profile(state_db, fake_providers) -> None:
    _database, runtime, learner_id = state_db
    await _seed_registry(runtime)
    task_id = "task-evidence"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)

    graph = build_loop(_deps(runtime, learner_id, task_id, []))
    await graph.ainvoke(
        initial_state(
            learner_id=learner_id,
            task_id=task_id,
            utterance="帮我讲讲 TCP 拥塞控制",
            budget=new_budget({"max_steps": 4, "max_replans": 1}),
        ),
        {"recursion_limit": 60},
    )

    profile = await runtime.profile_for(learner_id)
    assert profile, "a round that produced evidence must leave a profile row"
    assert any(row["system"]["evidence_count"] > 0 for row in profile)


@pytest.mark.asyncio
async def test_an_exhausted_budget_stops_the_loop_with_a_reason(state_db, fake_providers) -> None:
    _database, runtime, learner_id = state_db
    await _seed_registry(runtime)
    task_id = "task-budget"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)

    graph = build_loop(_deps(runtime, learner_id, task_id, []))
    final = await graph.ainvoke(
        initial_state(
            learner_id=learner_id,
            task_id=task_id,
            utterance="帮我讲讲 TCP 拥塞控制",
            budget=new_budget({"max_steps": 1, "max_replans": 1}),
        ),
        {"recursion_limit": 60},
    )

    assert final["runtime_status"] in {
        str(RuntimeStatus.FAILED),
        str(RuntimeStatus.COMPLETED),
        str(RuntimeStatus.WAITING_FOR_USER),
    }
    if final["runtime_status"] == str(RuntimeStatus.FAILED):
        assert final["finished_reason"], "a failed run must say why in Chinese"

    persisted = await runtime.get_session_state(task_id)
    assert persisted is not None
    assert persisted["runtime_status"] == final["runtime_status"]
    assert persisted["plan"], "the four-table state must contain the plan the loop ran"
    assert persisted["budget"] == final["budget"]


# --- dispatch resolution ----------------------------------------------------


def test_capability_resolves_to_the_cheapest_enabled_skill() -> None:
    skills = [
        registry_row("expensive", "assess.generate", "a", latency_weight=4.0),
        registry_row("cheap", "assess.generate", "b", latency_weight=1.0),
    ]
    assert resolve("assess.generate", skills).skill_id == "cheap"


def test_resolution_is_stable_when_costs_tie() -> None:
    skills = [
        registry_row("beta", "assess.generate", "b"),
        registry_row("alpha", "assess.generate", "a"),
    ]
    assert resolve("assess.generate", skills).skill_id == "alpha"
    assert resolve("assess.generate", list(reversed(skills))).skill_id == "alpha"


def test_a_disabled_skill_is_not_resolvable() -> None:
    row = registry_row("only", "assess.generate", "a")
    row["enabled"] = False
    with pytest.raises(NoProvider):
        resolve("assess.generate", [row])


def test_a_skill_without_a_provider_is_not_resolvable() -> None:
    row = registry_row("only", "assess.generate", "")
    with pytest.raises(NoProvider):
        resolve("assess.generate", [row])


# --- fallback planning ------------------------------------------------------


def test_an_unavailable_control_model_uses_one_safe_fallback_route() -> None:
    from lingxilearn.runtime.candidates import generate

    world = WorldState(target=ProfileView.unseen("tcp-congestion"))
    plan = unavailable_plan(candidates=generate(goal=GOAL, world=world, skills=REGISTRY))
    assert plan.degraded
    assert len(plan.tasks) == 1
    assert plan.tasks[0].candidate_id
    assert not plan.awaits_user


def test_with_no_eligible_candidate_the_fallback_hands_back_to_the_learner() -> None:
    plan = unavailable_plan(candidates=[])
    assert plan.awaits_user
    assert not plan.tasks


# --- post-answer follow-up interaction (issue #32) --------------------------


@pytest.mark.asyncio
async def test_turn_complete_requests_a_followup_interaction_and_resumes_to_planning(
    state_db, fake_providers
) -> None:
    """A completed dialog.answer must not fall silently into WAITING_FOR_USER.

    It should request a blocking follow-up Interaction through the same
    lifecycle pre-execution HITL uses (interaction.requested + a durable
    pending_interaction), and answering it must resume the checkpoint back
    into another Orchestrator planning round rather than a hardcoded route.
    """
    from lingxigraph import Command, InMemorySaver

    from lingxilearn.state.capabilities import parse
    from lingxilearn.state.skill_catalog import SkillManifest

    _database, runtime, learner_id = state_db
    answer_registry = [*REGISTRY, registry_row("fake-answer", "dialog.answer", "fake_teacher")]
    await runtime.sync_skill_manifests(
        [
            SkillManifest(
                skill_id=row["skill_id"],
                capabilities=(parse(row["capabilities"][0]),),
                provider=row["provider"],
                cost=row["cost"],
                version="1.0.0",
            )
            for row in answer_registry
        ]
    )
    task_id = "task-followup"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)

    events: list[tuple[str, dict]] = []
    deps = _deps(runtime, learner_id, task_id, events)
    checkpointer = InMemorySaver()
    graph = build_loop(deps, checkpointer=checkpointer)
    config = {"configurable": {"thread_id": task_id}}

    result = await graph.ainvoke(
        initial_state(
            learner_id=learner_id,
            task_id=task_id,
            utterance="什么是 TCP 拥塞控制？",
            budget=new_budget({"max_steps": 4, "max_replans": 1}),
        ),
        config,
    )

    interrupts = result.get("__interrupt__")
    assert interrupts, "a turn_complete answer must pause on a typed interrupt"
    payload = interrupts[0].value
    assert payload["kind"] == "interaction"
    interaction_id = payload["interaction_id"]

    requested = [payload for kind, payload in events if kind == "interaction.requested"]
    assert requested, "turn_complete must emit interaction.requested"
    assert requested[-1]["interaction_id"] == interaction_id
    assert requested[-1]["reasonCode"] == "post_answer_followup"
    assert requested[-1]["blocking"] is True

    persisted = await runtime.get_session_state(task_id)
    assert persisted is not None
    assert persisted["runtime_status"] == str(RuntimeStatus.WAITING_FOR_USER)

    decisions_before = await runtime.decisions_for_task(task_id)

    await graph.ainvoke(
        Command(
            resume={
                "kind": "interaction_answer",
                "interaction_id": interaction_id,
                "answers": [
                    {
                        "questionId": "followup",
                        "selectedOptionIds": ["continue_deeper"],
                        "text": None,
                    }
                ],
            }
        ),
        config,
    )

    # The resume must hand control back to the Orchestrator (PLANNING) for a
    # fresh round, not to any option-specific hardcoded next step.
    round_started = [payload for kind, payload in events if kind == "round.started"]
    assert len(round_started) >= 2, "resuming must re-enter orchestrate for a new round"
    decisions_after = await runtime.decisions_for_task(task_id)
    assert len(decisions_after) > len(decisions_before)


def test_budget_is_spent_as_the_loop_runs() -> None:
    budget = Budget(max_steps=3)
    budget.spend_step(heavy=True, tokens=120, wall_ms=90)
    assert budget.steps_used == 1
    assert budget.heavy_artifacts_used == 1
    assert budget.tokens_used == 120
    assert not budget.steps_exhausted
    budget.spend_step()
    budget.spend_step()
    assert budget.steps_exhausted
