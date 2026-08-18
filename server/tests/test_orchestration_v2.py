from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_command_inbox_is_idempotent_and_work_claim_is_single_owner(state_db) -> None:
    database, _, learner_id = state_db
    from lingxilearn.store.repositories.agent_tasks import AgentTaskRepository
    from lingxilearn.store.repositories.work_ledger import WorkLedgerRepository

    agent_task_repository = AgentTaskRepository(database)
    work_ledger = WorkLedgerRepository(database)
    task_id = f"v2-task-{uuid4().hex}"
    await agent_task_repository.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="测试持久化编排",
        graph_version="test@v2",
        status="awaiting_user",
    )

    first = await work_ledger.append_command(
        task_id=task_id,
        kind="message",
        payload={"message": "继续"},
        idempotency_key="message-1",
    )
    retry = await work_ledger.append_command(
        task_id=task_id,
        kind="message",
        payload={"message": "继续"},
        idempotency_key="message-1",
    )
    assert first["created"] is True
    assert retry["created"] is False
    assert len(await work_ledger.pending_commands(task_id)) == 1

    turn = await work_ledger.latest_turn(task_id)
    assert turn is not None
    plan = await work_ledger.create_work_plan(
        task_id=task_id,
        turn_id=str(turn["id"]),
        expected_revision=0,
        items=[
            {
                "id": "work-v2-1",
                "work_key": "work-v2-1",
                "candidate_id": "candidate-v2-1",
                "capability": "answer_question",
                "skill_id": "skill.answer",
                "skill_version": "1",
                "skill_checksum": "checksum",
                "provider": "test",
                "input_payload": {"message": "继续"},
                "reserved_tokens": 10,
                "reserved_wall_ms": 100,
                "status": "queued",
            }
        ],
        budget={"token_budget": 100, "wall_ms_budget": 1000},
    )
    assert plan is not None
    assert plan.get("budget_exceeded") is not True

    claims = await asyncio.gather(
        work_ledger.claim_work_item(work_id="work-v2-1", owner="worker-a"),
        work_ledger.claim_work_item(work_id="work-v2-1", owner="worker-b"),
    )
    assert sum(claim is not None for claim in claims) == 1
    owner = next(claim["lease_owner"] for claim in claims if claim is not None)
    assert await work_ledger.finish_work(
        work_id="work-v2-1",
        owner=str(owner),
        status="succeeded",
        result={"schema_id": "answer.v1", "safe_summary": "完成", "usage": {"tokens": 7}},
    )
    assert (await work_ledger.get_work(task_id=task_id, work_id="work-v2-1"))["status"] == "succeeded"


@pytest.mark.asyncio
async def test_confirmation_requires_exact_digest_and_reject_releases_work(state_db) -> None:
    database, _, learner_id = state_db
    from lingxilearn.store.repositories.agent_tasks import AgentTaskRepository
    from lingxilearn.store.repositories.work_ledger import WorkLedgerRepository

    agent_task_repository = AgentTaskRepository(database)
    work_ledger = WorkLedgerRepository(database)
    task_id = f"confirm-task-{uuid4().hex}"
    await agent_task_repository.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="测试确认",
        graph_version="test@v2",
        status="awaiting_user",
    )
    await work_ledger.append_command(
        task_id=task_id,
        kind="message",
        payload={"message": "执行"},
        idempotency_key="confirm-message",
    )
    turn = await work_ledger.latest_turn(task_id)
    assert turn is not None
    plan = await work_ledger.create_work_plan(
        task_id=task_id,
        turn_id=str(turn["id"]),
        expected_revision=0,
        items=[
            {
                "id": "confirm-work",
                "work_key": "confirm-work",
                "candidate_id": "candidate-confirm",
                "capability": "manage_task",
                "provider": "test",
                "status": "waiting_confirmation",
                "confirmation_digest": "digest-1",
            }
        ],
    )
    assert plan is not None
    assert await work_ledger.confirm_work(work_id="confirm-work", payload_digest="wrong", approve=True) is False
    assert await work_ledger.confirm_work(work_id="confirm-work", payload_digest="digest-1", approve=False) is False
    assert (await work_ledger.get_work(task_id=task_id, work_id="confirm-work"))["status"] == "cancelled"


@pytest.mark.asyncio
async def test_create_work_plan_flushes_items_before_dependencies(state_db) -> None:
    database, _, learner_id = state_db
    from lingxilearn.store.repositories.agent_tasks import AgentTaskRepository
    from lingxilearn.store.repositories.work_ledger import WorkLedgerRepository

    agent_task_repository = AgentTaskRepository(database)
    work_ledger = WorkLedgerRepository(database)
    task_id = f"dependency-task-{uuid4().hex}"
    await agent_task_repository.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="测试依赖持久化顺序",
        graph_version="test@v2",
        status="awaiting_user",
    )
    await work_ledger.append_command(
        task_id=task_id,
        kind="message",
        payload={"message": "执行"},
        idempotency_key="dependency-message",
    )
    turn = await work_ledger.latest_turn(task_id)
    assert turn is not None
    plan = await work_ledger.create_work_plan(
        task_id=task_id,
        turn_id=str(turn["id"]),
        expected_revision=0,
        items=[
            {"id": "dependency-work-a", "work_key": "a", "candidate_id": "candidate-a", "capability": "answer_question"},
            {"id": "dependency-work-b", "work_key": "b", "candidate_id": "candidate-b", "capability": "assess.generate"},
        ],
        dependencies=[("dependency-work-b", "dependency-work-a")],
    )
    assert plan is not None
    assert {item["id"] for item in plan["work_items"]} == {"dependency-work-a", "dependency-work-b"}


@pytest.mark.asyncio
async def test_evidence_projection_cursor_continues_after_first_500(state_db) -> None:
    _, runtime, learner_id = state_db
    from lingxilearn.runtime.state_updater import StateUpdater
    from lingxilearn.state.evidence import EvidenceRecord, Signal

    records = [
        EvidenceRecord(
            learner_id=learner_id,
            knowledge_point="kp.cursor",
            signal=Signal.CORRECT,
            source_agent="quiz",
            score=1.0,
            locator={"item": index},
        )
        for index in range(501)
    ]
    assert len(await runtime.append_evidence(records)) == 501

    updater = StateUpdater(runtime)
    await updater.apply(learner_id=learner_id)
    assert await runtime.projection_cursor(learner_id) == 500
    await updater.apply(learner_id=learner_id)
    assert await runtime.projection_cursor(learner_id) == 501
