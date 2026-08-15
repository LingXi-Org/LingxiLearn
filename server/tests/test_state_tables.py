"""The four state tables and their invariants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lingxilearn.state.evidence import EvidenceRecord, InvalidEvidence, Signal
from lingxilearn.state.profile_writer import ProfileDelta, UnsourcedProfileWrite
from lingxilearn.state.session_state import (
    Goal,
    GoalKind,
    GoalStack,
    GoalStatus,
    IllegalTransition,
    RuntimeStatus,
    transition,
)


def _evidence(learner_id: str, **overrides) -> EvidenceRecord:
    payload = {
        "learner_id": learner_id,
        "knowledge_point": "tcp-congestion",
        "signal": Signal.CORRECT,
        "source_agent": "deterministic_grader",
        "score": 0.9,
        "task_id": "task-1",
    }
    payload.update(overrides)
    return EvidenceRecord(**payload)


# --- learning_evidence -----------------------------------------------------


@pytest.mark.asyncio
async def test_evidence_seq_is_monotonic_per_learner(state_db) -> None:
    _database, runtime, learner_id = state_db
    appended = await runtime.append_evidence(
        [
            _evidence(learner_id, knowledge_point="a"),
            _evidence(learner_id, knowledge_point="b", signal=Signal.INCORRECT, score=0.1),
            _evidence(learner_id, knowledge_point="c", signal=Signal.SELF_REPORT, score=None),
        ]
    )
    assert [row["seq"] for row in appended] == [1, 2, 3]

    more = await runtime.append_evidence([_evidence(learner_id, knowledge_point="d")])
    assert more[0]["seq"] == 4


@pytest.mark.asyncio
async def test_evidence_append_is_idempotent_on_identical_observation(state_db) -> None:
    _database, runtime, learner_id = state_db
    first = await runtime.append_evidence([_evidence(learner_id)])
    second = await runtime.append_evidence([_evidence(learner_id)])
    assert first[0]["id"] == second[0]["id"]
    assert first[0]["seq"] == second[0]["seq"]

    stored = await runtime.evidence_after(learner_id, 0)
    assert len(stored) == 1


@pytest.mark.asyncio
async def test_evidence_after_returns_only_unconsumed_rows(state_db) -> None:
    _database, runtime, learner_id = state_db
    await runtime.append_evidence(
        [_evidence(learner_id, knowledge_point=f"kp-{index}") for index in range(5)]
    )
    assert len(await runtime.evidence_after(learner_id, 0)) == 5
    assert len(await runtime.evidence_after(learner_id, 3)) == 2
    assert await runtime.evidence_after(learner_id, 5) == []


def test_graded_evidence_requires_a_score() -> None:
    with pytest.raises(InvalidEvidence):
        EvidenceRecord(
            learner_id="l", knowledge_point="kp", signal=Signal.CORRECT, source_agent="grader"
        )


def test_evidence_requires_a_knowledge_point_and_source() -> None:
    with pytest.raises(InvalidEvidence):
        EvidenceRecord(
            learner_id="l", knowledge_point="", signal=Signal.SELF_REPORT, source_agent="x"
        )
    with pytest.raises(InvalidEvidence):
        EvidenceRecord(
            learner_id="l", knowledge_point="kp", signal=Signal.SELF_REPORT, source_agent=""
        )


def test_evidence_repository_has_no_update_or_delete_path() -> None:
    """Append-only is a property of the API surface, not a convention."""

    from lingxilearn.store import runtime_state

    forbidden = {"update_evidence", "delete_evidence", "edit_evidence", "purge_evidence"}
    assert not forbidden & set(dir(runtime_state.RuntimeStateRepository))

    source = (
        runtime_state.__file__.replace(".pyc", ".py")
    )
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "delete(LearningEvidence" not in text
    assert "update(LearningEvidence" not in text


# --- learning_profile ------------------------------------------------------


@pytest.mark.asyncio
async def test_profile_write_requires_evidence(state_db) -> None:
    with pytest.raises(UnsourcedProfileWrite):
        ProfileDelta(
            learner_id="l",
            knowledge_point_id="kp",
            evidence_ids=[],
            source_agent="state_updater",
            mastery=0.9,
        )


@pytest.mark.asyncio
async def test_profile_delta_creates_then_updates_with_revision(state_db) -> None:
    _database, runtime, learner_id = state_db
    changes = await runtime.apply_profile_deltas(
        [
            ProfileDelta(
                learner_id=learner_id,
                knowledge_point_id="tcp",
                knowledge_point="TCP 拥塞控制",
                evidence_ids=["ev_1"],
                source_agent="state_updater",
                mastery=0.6,
                learning_state="emerging",
                evidence_count=2,
                last_evidence_seq=2,
            )
        ]
    )
    assert len(changes) == 1
    assert changes[0].after["mastery"] == 0.6
    assert changes[0].after["revision"] == 1

    row = await runtime.profile_point(learner_id, "tcp")
    assert row["knowledge_point"] == "TCP 拥塞控制"
    assert row["system"]["evidence_count"] == 2
    assert row["system"]["confidence"] > 0

    changes = await runtime.apply_profile_deltas(
        [
            ProfileDelta(
                learner_id=learner_id,
                knowledge_point_id="tcp",
                evidence_ids=["ev_2"],
                source_agent="state_updater",
                mastery=0.8,
            )
        ]
    )
    assert changes[0].before["mastery"] == 0.6
    assert changes[0].after["mastery"] == 0.8
    assert changes[0].mastery_delta == pytest.approx(0.2)
    assert changes[0].after["revision"] == 2


@pytest.mark.asyncio
async def test_learner_override_survives_the_state_updater(state_db) -> None:
    _database, runtime, learner_id = state_db
    await runtime.apply_profile_deltas(
        [
            ProfileDelta(
                learner_id=learner_id,
                knowledge_point_id="dns",
                evidence_ids=["ev_1"],
                source_agent="state_updater",
                mastery=0.4,
            )
        ]
    )
    await runtime.override_profile(
        learner_id=learner_id,
        knowledge_point_id="dns",
        enabled=True,
        fields={"mastery": 0.95},
    )
    await runtime.apply_profile_deltas(
        [
            ProfileDelta(
                learner_id=learner_id,
                knowledge_point_id="dns",
                evidence_ids=["ev_2"],
                source_agent="state_updater",
                mastery=0.30,
                evidence_count=5,
            )
        ]
    )
    row = await runtime.profile_point(learner_id, "dns")
    # The learner's number stands; the evidence count still advances.
    assert row["mastery"] == 0.95
    assert row["system"]["evidence_count"] == 5
    assert row["system"]["override_flag"] is True


@pytest.mark.asyncio
async def test_profile_rejects_out_of_range_and_unknown_states(state_db) -> None:
    from lingxilearn.state.profile_writer import InvalidProfileField

    with pytest.raises(InvalidProfileField):
        ProfileDelta(
            learner_id="l",
            knowledge_point_id="kp",
            evidence_ids=["ev"],
            source_agent="s",
            mastery=1.4,
        )
    with pytest.raises(InvalidProfileField):
        ProfileDelta(
            learner_id="l",
            knowledge_point_id="kp",
            evidence_ids=["ev"],
            source_agent="s",
            learning_state="totally_mastered",
        )


# --- session_state ---------------------------------------------------------


def test_goal_stack_push_pop_replace_are_reversible() -> None:
    stack = GoalStack()
    long_term = Goal(goal_type="master", topic="计算机网络", kind=GoalKind.LONG_TERM)
    stack.push(long_term)
    current = Goal(goal_type="learn", topic="TCP 拥塞控制")
    push_op = stack.push(current)

    assert stack.current().topic == "TCP 拥塞控制"
    assert stack.long_term().topic == "计算机网络"

    interrupt = Goal(goal_type="ask", topic="什么是慢启动", kind=GoalKind.INTERRUPT)
    stack.push(interrupt)
    assert stack.current().topic == "什么是慢启动"

    stack.pop(reason="answered")
    assert stack.current().topic == "TCP 拥塞控制"

    # The undo record is a full before/after snapshot, so replaying it restores
    # the earlier stack exactly.
    restored = GoalStack(push_op.before)
    assert [g.topic for g in restored.goals] == ["计算机网络"]


def test_goal_stack_replace_swaps_the_current_goal_in_place() -> None:
    stack = GoalStack()
    stack.push(Goal(goal_type="learn", topic="错的主题"))
    op = stack.replace(Goal(goal_type="learn", topic="对的主题"), reason="correction")
    assert op.op == "replace"
    assert len(stack.goals) == 1
    assert stack.current().topic == "对的主题"


def test_goal_stack_is_empty_once_every_goal_is_closed() -> None:
    stack = GoalStack()
    stack.push(Goal(goal_type="learn", topic="X"))
    assert not stack.is_empty()
    stack.pop()
    assert stack.is_empty()
    assert stack.goals[0].status is GoalStatus.SATISFIED


def test_runtime_status_transitions_are_closed() -> None:
    assert transition(RuntimeStatus.PLANNING, RuntimeStatus.EXECUTING) is RuntimeStatus.EXECUTING
    assert transition(RuntimeStatus.EXECUTING, RuntimeStatus.EXECUTING) is RuntimeStatus.EXECUTING
    with pytest.raises(IllegalTransition):
        transition(RuntimeStatus.EXECUTING, RuntimeStatus.COMPLETED)
    with pytest.raises(IllegalTransition):
        transition(RuntimeStatus.COMPLETED, RuntimeStatus.PLANNING)


@pytest.mark.asyncio
async def test_session_state_records_an_undo_log(state_db) -> None:
    _database, runtime, learner_id = state_db
    task_id = "task-goal-stack"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)

    stack = await runtime.goal_stack(task_id)
    await runtime.apply_stack_operation(
        task_id, stack.push(Goal(goal_type="learn", topic="TCP"), reason="initial")
    )
    stack = await runtime.goal_stack(task_id)
    await runtime.apply_stack_operation(
        task_id,
        stack.push(
            Goal(goal_type="ask", topic="慢启动", kind=GoalKind.INTERRUPT), reason="interrupt"
        ),
    )

    snapshot = await runtime.get_session_state(task_id)
    assert [g["topic"] for g in snapshot["goal_stack"]] == ["TCP", "慢启动"]

    history = await runtime.stack_history(task_id)
    assert [item["op"] for item in history] == ["push", "push"]
    assert history[0]["before"]["goal_stack"] == []
    assert history[1]["reason"] == "interrupt"


@pytest.mark.asyncio
async def test_session_state_status_uses_the_transition_table(state_db) -> None:
    _database, runtime, learner_id = state_db
    task_id = "task-status"
    await runtime.ensure_session_state(learner_id=learner_id, task_id=task_id)

    snapshot = await runtime.set_runtime_status(task_id, RuntimeStatus.EXECUTING)
    assert snapshot["runtime_status"] == "EXECUTING"
    with pytest.raises(IllegalTransition):
        await runtime.set_runtime_status(task_id, RuntimeStatus.COMPLETED)


@pytest.mark.asyncio
async def test_session_state_starts_with_a_guardrail_budget(state_db) -> None:
    _database, runtime, learner_id = state_db
    snapshot = await runtime.ensure_session_state(learner_id=learner_id, task_id="task-budget")
    budget = snapshot["budget"]
    assert budget["max_steps"] > 0
    assert budget["max_replans"] > 0
    assert budget["max_heavy_artifacts"] > 0
    assert budget["steps_used"] == 0


# --- scheduling ------------------------------------------------------------


def test_stability_grows_on_recall_and_collapses_on_a_lapse() -> None:
    from lingxilearn.state.scheduling import next_stability

    grown = next_stability(current=2.0, score=1.0, difficulty=0.3)
    lapsed = next_stability(current=2.0, score=0.1, difficulty=0.3)
    assert grown > 2.0
    assert lapsed < 2.0
    # A scaffolded correct answer is worth less interval than an unaided one.
    assert next_stability(current=2.0, score=1.0, difficulty=0.3, hint_level=3) < grown


def test_review_priority_ranks_overdue_weak_material_highest() -> None:
    from lingxilearn.state.scheduling import review_priority

    now = datetime.now(UTC)
    overdue_weak = review_priority(
        mastery=0.2, review_due_at=now - timedelta(days=10), now=now, evidence_count=4
    )
    overdue_strong = review_priority(
        mastery=0.9, review_due_at=now - timedelta(days=10), now=now, evidence_count=4
    )
    not_due = review_priority(
        mastery=0.2, review_due_at=now + timedelta(days=10), now=now, evidence_count=4
    )
    assert overdue_weak > overdue_strong > not_due
