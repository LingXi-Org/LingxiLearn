"""The demoted router, and the single writer of the learning profile."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lingxilearn.runtime.goal_interpreter import (
    apply_to_stack,
    build_goal,
    fallback_goal,
    interpret,
)
from lingxilearn.runtime.state_updater import StateUpdater
from lingxilearn.state.evidence import EvidenceRecord, Signal
from lingxilearn.state.session_state import Goal, GoalKind, GoalStack

NOW = datetime(2026, 8, 14, tzinfo=UTC)

PROFILE_ROWS = [
    {"knowledge_point_id": "tcp-congestion", "knowledge_point": "TCP 拥塞控制"},
    {"knowledge_point_id": "sliding-window", "knowledge_point": "滑动窗口"},
]


# --- goal interpreter --------------------------------------------------------


def test_goal_has_no_route_field_and_never_grows_one() -> None:
    """The whole point of the demotion: it says what, not what-runs-next."""

    goal = build_goal({"topic": "TCP"}, utterance="讲讲 TCP")
    payload = goal.to_dict()
    for forbidden in ("route", "agent", "workflow", "next_node"):
        assert forbidden not in payload


def test_known_knowledge_points_are_reused_rather_than_reinvented() -> None:
    goal = build_goal(
        {"topic": "我想搞懂 TCP 拥塞控制"}, utterance="我想搞懂 TCP 拥塞控制",
        profile_rows=PROFILE_ROWS,
    )
    assert goal.knowledge_points == ("tcp-congestion",)


def test_an_unseen_topic_gets_a_stable_id() -> None:
    first = build_goal({"topic": "量子隧穿"}, utterance="讲讲量子隧穿")
    second = build_goal({"topic": "量子隧穿"}, utterance="再讲讲量子隧穿")
    assert first.knowledge_points == second.knowledge_points
    assert first.knowledge_points[0]


def test_unknown_goal_types_fall_back_to_learn() -> None:
    assert build_goal({"goal_type": "vibe", "topic": "x"}, utterance="x").goal_type == "learn"
    assert build_goal({"goal_type": "review", "topic": "x"}, utterance="x").goal_type == "review"


def test_urgency_is_clamped_and_survives_garbage() -> None:
    assert build_goal({"topic": "x", "urgency": 3}, utterance="x").urgency == 1.0
    assert build_goal({"topic": "x", "urgency": "soon"}, utterance="x").urgency == 0.5


def test_fallback_goal_keeps_the_loop_moving_without_a_model() -> None:
    goal = fallback_goal("帮我讲讲 TCP", profile_rows=PROFILE_ROWS)
    assert goal.goal_type == "learn"
    assert goal.topic == "帮我讲讲 TCP"
    assert goal.created_by.endswith("fallback")


@pytest.mark.asyncio
async def test_interpret_without_a_model_degrades_instead_of_raising() -> None:
    goal = await interpret(utterance="讲讲 TCP", model=None, profile_rows=PROFILE_ROWS)
    assert goal.topic == "讲讲 TCP"


@pytest.mark.asyncio
async def test_interpret_rejects_an_empty_utterance() -> None:
    with pytest.raises(ValueError):
        await interpret(utterance="   ", model=None)


def test_an_interruption_stacks_and_a_correction_replaces() -> None:
    stack = GoalStack()
    apply_to_stack(stack, Goal(goal_type="learn", topic="TCP 拥塞控制"))
    assert len(stack.goals) == 1

    apply_to_stack(
        stack, Goal(goal_type="ask", topic="什么是慢启动", kind=GoalKind.INTERRUPT)
    )
    assert len(stack.goals) == 2
    assert stack.current().topic == "什么是慢启动"

    apply_to_stack(stack, Goal(goal_type="ask", topic="其实我问的是快重传"), is_correction=True)
    assert len(stack.goals) == 2
    assert stack.current().topic == "其实我问的是快重传"


def test_stack_operations_carry_an_undo_snapshot() -> None:
    stack = GoalStack()
    apply_to_stack(stack, Goal(goal_type="learn", topic="A"))
    operation = apply_to_stack(
        stack, Goal(goal_type="ask", topic="B", kind=GoalKind.INTERRUPT)
    )
    assert operation.op == "push"
    assert [g["topic"] for g in operation.before] == ["A"]
    assert [g["topic"] for g in operation.after] == ["A", "B"]


# --- state updater -----------------------------------------------------------


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


@pytest.mark.asyncio
async def test_evidence_moves_mastery_and_records_before_and_after(state_db) -> None:
    _database, runtime, learner_id = state_db
    await runtime.append_evidence(
        [
            _evidence(learner_id, score=0.9, locator={"q": 1}),
            _evidence(learner_id, score=1.0, locator={"q": 2}),
        ]
    )
    changes = await StateUpdater(runtime).apply(learner_id=learner_id, now=NOW)

    assert len(changes) == 1
    change = changes[0]
    assert change.knowledge_point_id == "tcp-congestion"
    assert change.after["mastery"] > change.before.get("mastery", 0.35)
    assert change.evidence_ids
    assert change.mastery_delta > 0


@pytest.mark.asyncio
async def test_a_second_pass_consumes_nothing_new(state_db) -> None:
    """The high-water mark is what keeps evidence append-only and idempotent."""

    _database, runtime, learner_id = state_db
    await runtime.append_evidence([_evidence(learner_id, locator={"q": 1})])
    updater = StateUpdater(runtime)

    assert await updater.apply(learner_id=learner_id, now=NOW)
    assert await updater.apply(learner_id=learner_id, now=NOW) == []

    await runtime.append_evidence([_evidence(learner_id, score=0.2, signal=Signal.INCORRECT,
                                             locator={"q": 2})])
    assert await updater.apply(learner_id=learner_id, now=NOW)


@pytest.mark.asyncio
async def test_one_strong_answer_is_needs_recheck_not_demonstrated(state_db) -> None:
    """Claiming mastery from a single observation is how a learner model loses trust."""

    _database, runtime, learner_id = state_db
    await runtime.append_evidence([_evidence(learner_id, score=1.0, locator={"q": 1})])
    await StateUpdater(runtime).apply(learner_id=learner_id, now=NOW)

    row = await runtime.profile_point(learner_id, "tcp-congestion")
    assert row["learning_state"] == "needs_recheck"


@pytest.mark.asyncio
async def test_hinted_answers_earn_less_credit_than_unaided_ones(state_db) -> None:
    _database, runtime, learner_id = state_db
    updater = StateUpdater(runtime)

    await runtime.append_evidence(
        [_evidence(learner_id, knowledge_point="unaided", score=1.0, hint_level=0)]
    )
    await runtime.append_evidence(
        [_evidence(learner_id, knowledge_point="scaffolded", score=1.0, hint_level=3)]
    )
    await updater.apply(learner_id=learner_id, now=NOW)

    unaided = await runtime.profile_point(learner_id, "unaided")
    scaffolded = await runtime.profile_point(learner_id, "scaffolded")
    assert unaided["mastery"] > scaffolded["mastery"]


@pytest.mark.asyncio
async def test_misconceptions_accumulate_and_retire_on_clean_evidence(state_db) -> None:
    _database, runtime, learner_id = state_db
    updater = StateUpdater(runtime)

    await runtime.append_evidence(
        [
            _evidence(
                learner_id,
                signal=Signal.INCORRECT,
                score=0.0,
                misconceptions=("把拥塞窗口当成接收窗口",),
                locator={"q": 1},
            )
        ]
    )
    await updater.apply(learner_id=learner_id, now=NOW)
    row = await runtime.profile_point(learner_id, "tcp-congestion")
    assert row["system"]["misconceptions"] == ["把拥塞窗口当成接收窗口"]
    assert row["learning_state"] == "misconception_evidence"

    await runtime.append_evidence(
        [
            _evidence(
                learner_id,
                score=1.0,
                hint_level=0,
                misconceptions=("把拥塞窗口当成接收窗口",),
                locator={"q": 2},
            )
        ]
    )
    await updater.apply(learner_id=learner_id, now=NOW)
    row = await runtime.profile_point(learner_id, "tcp-congestion")
    assert row["system"]["misconceptions"] == []


@pytest.mark.asyncio
async def test_self_reports_land_in_my_questions(state_db) -> None:
    _database, runtime, learner_id = state_db
    await runtime.append_evidence(
        [
            _evidence(
                learner_id,
                signal=Signal.SELF_REPORT,
                score=None,
                summary="cwnd 和 rwnd 到底谁说了算",
                source_agent="answer_user",
            )
        ]
    )
    await StateUpdater(runtime).apply(learner_id=learner_id, now=NOW)

    row = await runtime.profile_point(learner_id, "tcp-congestion")
    assert row["my_questions"] == ["cwnd 和 rwnd 到底谁说了算"]
    # A question is not a graded attempt, so it must not move mastery.
    assert row["mastery"] == pytest.approx(0.35)


@pytest.mark.asyncio
async def test_a_wrong_answer_schedules_a_sooner_review(state_db) -> None:
    _database, runtime, learner_id = state_db
    updater = StateUpdater(runtime)

    await runtime.append_evidence(
        [_evidence(learner_id, knowledge_point="solid", score=1.0, locator={"q": 1}),
         _evidence(learner_id, knowledge_point="solid", score=1.0, locator={"q": 2})]
    )
    await runtime.append_evidence(
        [_evidence(learner_id, knowledge_point="shaky", signal=Signal.INCORRECT, score=0.0,
                   locator={"q": 1}),
         _evidence(learner_id, knowledge_point="shaky", signal=Signal.INCORRECT, score=0.1,
                   locator={"q": 2})]
    )
    await updater.apply(learner_id=learner_id, now=NOW)

    solid = await runtime.profile_point(learner_id, "solid")
    shaky = await runtime.profile_point(learner_id, "shaky")
    assert solid["system"]["stability"] > shaky["system"]["stability"]
    assert shaky["system"]["review_priority"] > solid["system"]["review_priority"]


@pytest.mark.asyncio
async def test_the_updater_writes_through_the_profile_writer_only(state_db) -> None:
    """A change with no evidence behind it must not be constructible."""

    _database, runtime, learner_id = state_db
    changes = await StateUpdater(runtime).apply(learner_id=learner_id, now=NOW)
    assert changes == []  # nothing to fold, so nothing written

    await runtime.append_evidence([_evidence(learner_id)])
    changes = await StateUpdater(runtime).apply(learner_id=learner_id, now=NOW)
    assert all(change.evidence_ids for change in changes)
    assert all(change.source_agent == "state_updater" for change in changes)
