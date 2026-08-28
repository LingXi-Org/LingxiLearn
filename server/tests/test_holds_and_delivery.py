from __future__ import annotations

import pytest

from lingxilearn.runtime.contracts import HoldDecision
from lingxilearn.runtime.guardrails import (
    MAX_OPEN_HOLDS,
    MAX_REVISIONS_PER_TASK,
    Budget,
    apply_hold_policy,
)


def test_empty_revision_instruction_closes_and_unknown_hold_is_dropped() -> None:
    board = {"holds": {"3:t2": {"revisions": 0}}}
    result = apply_hold_policy(
        [
            HoldDecision(task_key="3:t2", action="revise"),
            HoldDecision(task_key="missing", action="revise", instruction="try"),
        ],
        board,
        Budget(),
    )
    assert result == [HoldDecision(task_key="3:t2", action="close")]


def test_revision_limit_and_budget_force_close() -> None:
    board = {"holds": {"3:t2": {"revisions": MAX_REVISIONS_PER_TASK}}}
    decision = HoldDecision(task_key="3:t2", action="revise", instruction="只调整图例")
    assert apply_hold_policy([decision], board, Budget())[0].action == "close"
    budget = Budget(tokens_used=1, token_budget=1)
    board = {"holds": {"3:t2": {"revisions": 0}}}
    assert apply_hold_policy([decision], board, budget)[0].action == "close"


def test_too_many_holds_closes_every_open_hold() -> None:
    board = {"holds": {f"1:t{i}": {"revisions": 0} for i in range(MAX_OPEN_HOLDS + 1)}}
    decisions = [HoldDecision(task_key="1:t0", action="revise", instruction="微调")]
    result = apply_hold_policy(decisions, board, Budget())
    assert len(result) == MAX_OPEN_HOLDS + 1
    assert all(item.action == "close" for item in result)


@pytest.mark.asyncio
async def test_board_round_trip(state_db) -> None:
    database, runtime, learner_id = state_db
    task_id = "board-round-trip"
    from lingxilearn.store.repositories.agent_tasks import AgentTaskRepository

    await AgentTaskRepository(database).create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="board round trip",
        graph_version="test@v1",
        status="queued",
    )
    await runtime.ensure_agent_task_state(learner_id=learner_id, task_id=task_id)
    board = {
        "holds": {"3:t2": {"task_id": "t2", "artifacts": ["visual"], "revisions": 0}},
        "order": ["lesson-intro", "visual"],
        "delivery": [{"artifact": "visual", "task_key": "3:t2", "state": "unlocked"}],
        "cursor": 0,
    }
    await runtime.save_board(task_id, board)
    assert await runtime.get_board(task_id) == board
