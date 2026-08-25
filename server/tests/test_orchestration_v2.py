from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_drain_before_checkpoint_crash_keeps_command_replayable(state_db) -> None:
    database, _, learner_id = state_db
    from lingxilearn.runtime.nodes.orchestration import build_orchestrate_node
    from lingxilearn.state.session_state import RuntimeStatus, new_budget
    from lingxilearn.store.repositories.agent_tasks import AgentTaskRepository
    from lingxilearn.store.repositories.work_ledger import WorkLedgerRepository

    tasks = AgentTaskRepository(database)
    ledger = WorkLedgerRepository(database)
    task_id = f"steer-crash-{uuid4().hex}"
    await tasks.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="解释 TCP",
        graph_version="test@v2",
        status="running",
    )
    command = await ledger.append_command(
        task_id=task_id,
        kind="message",
        payload={"message": "补充例子"},
        idempotency_key="steer-crash-message",
        delivery_mode="steering",
    )

    class Deps:
        work_ledger = ledger
        emit = None
        execution_id = "exec-crash"
        turn_id = str(command["turn_id"])

        async def transition_status(
            self, _state: dict[str, Any], status: RuntimeStatus, **_kwargs: Any
        ) -> dict[str, Any]:
            return {"runtime_status": str(status)}

    class Dispatcher:
        def retarget(self, **kwargs: Any) -> None:
            if "user_message" in kwargs:
                raise RuntimeError("crash before node return/checkpoint")

    event = SimpleNamespace(
        id="steer-crash",
        sequence=1,
        kind="user_message",
        payload={"message": "补充例子", "command_id": command["id"]},
        metadata={"turn_id": command["turn_id"]},
        created_at=datetime.now(UTC),
    )
    runtime = SimpleNamespace(drain_steering=lambda: [event])
    node = build_orchestrate_node(Deps(), dispatcher=Dispatcher())

    with pytest.raises(RuntimeError, match="before node return"):
        await node(
            {
                "runtime_status": str(RuntimeStatus.REPLANNING),
                "goal": {},
                "budget": new_budget(),
                "user_message": {},
            },
            runtime,
        )

    remaining = await ledger.pending_commands(task_id)
    assert [row["id"] for row in remaining] == [command["id"]]
    assert remaining[0]["consumed_at"] is None


@pytest.mark.asyncio
async def test_command_delivery_lease_has_one_owner_and_is_reclaimable(state_db) -> None:
    database, _, learner_id = state_db
    from lingxilearn.store.repositories.agent_tasks import AgentTaskRepository
    from lingxilearn.store.repositories.work_ledger import WorkLedgerRepository

    tasks = AgentTaskRepository(database)
    ledger_a = WorkLedgerRepository(database)
    ledger_b = WorkLedgerRepository(database)
    task_id = f"delivery-lease-{uuid4().hex}"
    await tasks.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="测试 owner lease",
        graph_version="test@v2",
        status="queued",
    )
    command = await ledger_a.append_command(
        task_id=task_id,
        kind="initial_prompt",
        payload={"message": "测试 owner lease"},
        idempotency_key="lease-command",
        delivery_mode="new_turn",
    )

    assert await ledger_a.claim_command_delivery(
        str(command["id"]), "exec-a", lease_seconds=1
    )
    assert not await ledger_b.claim_command_delivery(
        str(command["id"]), "exec-b", lease_seconds=1
    )
    await asyncio.sleep(1.05)
    assert await ledger_b.claim_command_delivery(
        str(command["id"]), "exec-b", lease_seconds=1
    )
    replayed = await ledger_a.command(str(command["id"]))
    assert replayed is not None
    assert replayed["delivery_execution_id"] == "exec-b"
    assert replayed["consumed_at"] is None


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
