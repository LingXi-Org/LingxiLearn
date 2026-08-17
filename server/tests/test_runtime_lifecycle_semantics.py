"""Fault-injection semantics for the single lifecycle write path (issue #35).

Issue #35 acceptance is not only the structural ban on direct
``set_runtime_status`` calls inside nodes (that ban is guarded by
``test_runtime_module_boundaries.py``).  It also demands *tested* failure and
reconcile semantics for the one owner that remains,
``LoopDeps.transition_status``:

* a persistence failure must raise and abort **before** a graph patch can
  advance the checkpoint, leaving the database un-advanced too — never one
  side moving ahead of the other;
* a checkpoint recovered stale behind a database that is already one legal
  phase ahead must be reconciled from the DB-canonical phase and resolved by
  a single derived patch;
* provider failure must end the run with the database and the checkpoint
  agreeing on the final phase;
* normal completion — a satisfied goal reaching ``COMPLETED`` through the
  real ``evaluate_goal`` node — must leave the database and the returned
  graph patch equal (issue #35's fourth consistency scenario).

Budget exhaustion and HITL pause/resume consistency are covered by
``test_an_exhausted_budget_stops_the_loop_with_a_reason`` and the
``test_turn_complete_requests_a_followup_interaction_and_resumes_to_planning``
pair in ``test_runtime_loop.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from lingxilearn.agents.providers import base as provider_base
from lingxilearn.agents.providers.base import ProviderContext, ProviderError
from lingxilearn.runtime.loop import LoopDeps, build_loop, initial_state
from lingxilearn.runtime.nodes import build_evaluate_goal_node
from lingxilearn.runtime.nodes import evaluation as nodes_evaluation
from lingxilearn.state.session_state import (
    Goal,
    IllegalTransition,
    RuntimeStatus,
    new_budget,
    transition,
)

TEACH_COST = {
    "latency_class": "interactive",
    "latency_weight": 1.0,
    "heavy_artifact": False,
    "blocking": True,
}


def _deps(runtime, learner_id: str, task_id: str, events: list[tuple[str, dict]]):
    return LoopDeps(
        runtime_state=runtime,
        learner_id=learner_id,
        task_id=task_id,
        model=None,
        execution_id="exec-lifecycle",
        emit=lambda kind, payload: events.append((kind, payload)),
    )


async def _seed_teach_skill(runtime) -> None:
    from lingxilearn.state.capabilities import parse
    from lingxilearn.state.skill_catalog import SkillManifest

    await runtime.sync_skill_manifests(
        [
            SkillManifest(
                skill_id="fake-teaching",
                capabilities=(parse("teach.strategy"),),
                provider="fake_teacher",
                cost=dict(TEACH_COST),
                version="1.0.0",
            )
        ]
    )


# --- persistence failure aborts before the graph advances (#35) --------------


@pytest.mark.asyncio
async def test_persistence_failure_aborts_before_a_graph_patch_can_advance(
    state_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DB write failure must propagate; no patch, no advance, no drift."""

    _database, runtime, learner_id = state_db
    task_id = "task-persist-fail"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)

    async def refuse(_task_id: str, _status: Any) -> dict[str, Any] | None:
        raise RuntimeError("db down")

    monkeypatch.setattr(runtime, "set_runtime_status", refuse)
    checkpoint: dict[str, Any] = {"runtime_status": str(RuntimeStatus.PLANNING)}

    with pytest.raises(RuntimeError, match="db down"):
        await _deps(runtime, learner_id, task_id, []).transition_status(
            checkpoint, RuntimeStatus.EXECUTING
        )

    # The read path was never patched, so this checks the real durable row:
    # the canonical phase must still be where it started.
    persisted = await runtime.get_session_state(task_id)
    assert persisted is not None
    assert persisted["runtime_status"] == str(RuntimeStatus.PLANNING)


@pytest.mark.asyncio
async def test_a_persistence_failure_inside_a_node_leaves_the_whole_run_unadvanced(
    state_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inside the graph the same rule holds: the run aborts, nothing advances."""

    _database, runtime, learner_id = state_db
    task_id = "task-node-persist-fail"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)

    async def refuse(_task_id: str, _status: Any) -> dict[str, Any] | None:
        raise RuntimeError("db down")

    monkeypatch.setattr(runtime, "set_runtime_status", refuse)
    graph = build_loop(_deps(runtime, learner_id, task_id, []))

    with pytest.raises(RuntimeError, match="db down"):
        await graph.ainvoke(
            initial_state(
                learner_id=learner_id,
                task_id=task_id,
                utterance="帮我讲讲 TCP 拥塞控制",
                budget=new_budget({"max_steps": 2, "max_replans": 1}),
            ),
            {"recursion_limit": 20},
        )

    persisted = await runtime.get_session_state(task_id)
    assert persisted is not None
    assert persisted["runtime_status"] == str(RuntimeStatus.PLANNING)


# --- stale checkpoint reconciles from the DB-canonical phase (#35) -----------


@pytest.mark.asyncio
async def test_stale_checkpoint_reconciles_from_the_db_canonical_phase(state_db) -> None:
    """A checkpoint one phase behind the DB is healed, not rejected.

    The scenario: a previous round committed EXECUTING to the database, then
    the process died before the checkpoint caught up, so the graph resumes
    with a stale ``planning`` value and the next node asks for OBSERVING.
    ``PLANNING → OBSERVING`` is *not* a legal transition, so this test can
    only pass if validation read the DB-canonical phase (EXECUTING), and the
    stale checkpoint value is reconciled by the one derived patch.
    """

    _database, runtime, learner_id = state_db
    task_id = "task-stale-checkpoint"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)
    await runtime.set_runtime_status(task_id, RuntimeStatus.EXECUTING)

    # Guard the premise: from the stale checkpoint value the request is illegal.
    with pytest.raises(IllegalTransition):
        transition(RuntimeStatus.PLANNING, RuntimeStatus.OBSERVING)

    stale: dict[str, Any] = {"runtime_status": str(RuntimeStatus.PLANNING)}
    patch = await _deps(runtime, learner_id, task_id, []).transition_status(
        stale, RuntimeStatus.OBSERVING
    )

    assert patch == {"runtime_status": str(RuntimeStatus.OBSERVING)}
    persisted = await runtime.get_session_state(task_id)
    assert persisted is not None
    assert persisted["runtime_status"] == str(RuntimeStatus.OBSERVING)


# --- provider failure keeps DB and checkpoint consistent (#35) ---------------


@pytest.mark.asyncio
async def test_provider_failure_ends_with_db_and_checkpoint_agreeing(
    state_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing provider degrades the run to FAILED on both sides alike."""

    async def failing(_context: ProviderContext) -> Any:
        raise ProviderError("模拟提供方故障")

    monkeypatch.setattr(provider_base, "_PROVIDERS", {"fake_teacher": failing})
    monkeypatch.setattr(provider_base, "load_all", lambda: dict(provider_base._PROVIDERS))

    _database, runtime, learner_id = state_db
    await _seed_teach_skill(runtime)
    task_id = "task-provider-fail"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)

    events: list[tuple[str, dict]] = []
    graph = build_loop(_deps(runtime, learner_id, task_id, events))
    final = await graph.ainvoke(
        initial_state(
            learner_id=learner_id,
            task_id=task_id,
            utterance="帮我讲讲 TCP 拥塞控制",
            budget=new_budget({"max_steps": 1, "max_replans": 1}),
        ),
        {"recursion_limit": 40},
    )

    assert final["runtime_status"] == str(RuntimeStatus.FAILED)
    persisted = await runtime.get_session_state(task_id)
    assert persisted is not None
    assert persisted["runtime_status"] == final["runtime_status"]
    assert final.get("finished_reason"), "a failed run must say why in Chinese"
    assert any(kind == "node.failed" for kind, _ in events)


# --- normal completion keeps DB and checkpoint consistent (#35) -------------


@pytest.mark.asyncio
async def test_goal_satisfied_completion_agrees_between_db_and_checkpoint(
    state_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A satisfied goal completes the run through the real evaluate_goal node.

    Determinism comes from stubbing only the *satisfaction probe*
    (``check_goal_satisfied``); everything else is the production path:
    ``evaluate_goal`` pops the single seeded goal, the pure policy decides
    ``goal_satisfied -> COMPLETED`` (no remaining goal), and the phase is
    persisted by the one lifecycle owner, ``LoopDeps.transition_status``.
    """

    _database, runtime, learner_id = state_db
    task_id = "task-normal-completion"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)

    # One real goal on the durable stack, so the satisfaction pop leaves no
    # remaining goal and the decision must be COMPLETED, not REPLANNING.
    goal = Goal(
        goal_type="learn",
        topic="TCP 拥塞控制",
        knowledge_points=("tcp-congestion",),
    )
    stack = await runtime.goal_stack(task_id)
    await runtime.apply_stack_operation(task_id, stack.push(goal, reason="测试"))

    # Advance the durable phase to evaluate_goal's legal pre-phase via the
    # transition table only: PLANNING -> EXECUTING -> OBSERVING -> UPDATING.
    for phase in (RuntimeStatus.EXECUTING, RuntimeStatus.OBSERVING, RuntimeStatus.UPDATING):
        await runtime.set_runtime_status(task_id, phase)

    monkeypatch.setattr(nodes_evaluation, "check_goal_satisfied", lambda *_args, **_kwargs: True)

    events: list[tuple[str, dict]] = []
    node = build_evaluate_goal_node(_deps(runtime, learner_id, task_id, events))
    state: dict[str, Any] = {
        "runtime_status": str(RuntimeStatus.UPDATING),
        "step": 1,
        "goal": goal.to_dict(),
        "outcomes": [],
        "plan": {},
        "last_decision_id": "",
    }

    patch = await node(state, None)

    assert patch["runtime_status"] == str(RuntimeStatus.COMPLETED)
    assert patch.get("finished_reason") == "目标已达成"
    assert any(kind == "goal.popped" for kind, _ in events)

    persisted = await runtime.get_session_state(task_id)
    assert persisted is not None
    assert persisted["runtime_status"] == str(RuntimeStatus.COMPLETED)
    assert persisted["runtime_status"] == patch["runtime_status"]

    # The single goal was popped satisfied, so nothing remained to replan on.
    settled = await runtime.goal_stack(task_id)
    assert settled.current() is None
