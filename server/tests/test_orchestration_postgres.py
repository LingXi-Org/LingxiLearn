from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
import pytest_asyncio

from lingxilearn.config import Settings


@pytest_asyncio.fixture
async def postgres_repositories():
    url = os.getenv("LINGXILEARN_POSTGRES_TEST_URL")
    if not url:
        pytest.skip("LINGXILEARN_POSTGRES_TEST_URL is not configured")

    from lingxilearn.store.repositories import Database, Repository

    settings = Settings(_env_file="", database_url=url)
    db_a = Database(settings)
    db_b = Database(settings)
    repo_a = Repository(db_a)
    repo_b = Repository(db_b)
    learner_id = f"pg-learner-{uuid4().hex}"
    await repo_a.ensure_learner(learner_id)
    try:
        yield repo_a, repo_b, learner_id
    finally:
        await db_a.dispose()
        await db_b.dispose()


@pytest.mark.asyncio
async def test_postgres_claim_and_budget_reservation_are_cross_instance_atomic(
    postgres_repositories,
) -> None:
    repo_a, repo_b, learner_id = postgres_repositories
    task_id = f"pg-task-{uuid4().hex}"
    work_one = f"pg-work-{uuid4().hex}"
    await repo_a.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="PostgreSQL V2 并发验收",
        graph_version="test@v2",
        status="awaiting_user",
    )

    await repo_a.append_command(
        task_id=task_id,
        kind="message",
        payload={"message": "开始"},
        idempotency_key="pg-message-1",
    )
    turn = await repo_a.latest_turn(task_id)
    assert turn is not None
    plan = await repo_a.create_work_plan(
        task_id=task_id,
        turn_id=str(turn["id"]),
        expected_revision=0,
        items=[
            {
                "id": work_one,
                "work_key": work_one,
                "candidate_id": "pg-candidate-1",
                "capability": "answer_question",
                "provider": "test",
                "reserved_tokens": 60,
            }
        ],
        budget={"token_budget": 100, "wall_ms_budget": 1000},
    )
    assert plan is not None
    assert plan.get("budget_exceeded") is not True

    claims = await asyncio.gather(
        repo_a.claim_work_item(work_id=work_one, owner="pg-a"),
        repo_b.claim_work_item(work_id=work_one, owner="pg-b"),
    )
    assert sum(claim is not None for claim in claims) == 1

    await repo_b.append_command(
        task_id=task_id,
        kind="message",
        payload={"message": "再次开始"},
        idempotency_key="pg-message-2",
    )
    second_turn = await repo_b.latest_turn(task_id)
    assert second_turn is not None
    assert second_turn["id"] != turn["id"]
    work_two = f"pg-work-{uuid4().hex}"
    competing = await repo_b.create_work_plan(
        task_id=task_id,
        turn_id=str(second_turn["id"]),
        expected_revision=0,
        items=[
            {
                "id": work_two,
                "work_key": work_two,
                "candidate_id": "pg-candidate-2",
                "capability": "answer_question",
                "provider": "test",
                "reserved_tokens": 50,
            }
        ],
        budget={"token_budget": 100, "wall_ms_budget": 1000},
    )
    assert competing is not None
    assert competing.get("budget_exceeded") is True
