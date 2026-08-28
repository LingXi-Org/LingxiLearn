"""Work-scheduler ownership tests against the real work ledger (issue #60).

The scheduler is the dispatcher's only door to the ledger: claim eligibility
(dependencies succeeded, lease free), single-owner atomic claim under
concurrency, lease heartbeat, and terminal finish.  These tests run against a
the migrated PostgreSQL ledger so parallel-safe claim semantics are exercised,
not mocked or emulated.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from lingxilearn.runtime.dispatch.scheduler import WorkScheduler


def _scheduler(task_id: str, ledger: Any) -> WorkScheduler:
    return WorkScheduler(SimpleNamespace(task_id=task_id, work_ledger=ledger))


async def _plan_with_dependency(database: Any, learner_id: str) -> tuple[str, Any]:
    """One task with A → B dependency; both work items queued."""

    from lingxilearn.store.repositories.agent_tasks import AgentTaskRepository
    from lingxilearn.store.repositories.work_ledger import WorkLedgerRepository

    agent_task_repository = AgentTaskRepository(database)
    work_ledger = WorkLedgerRepository(database)
    task_id = f"sched-task-{uuid4().hex}"
    await agent_task_repository.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="测试调度归属",
        graph_version="test@v2",
        status="awaiting_user",
    )
    await work_ledger.append_command(
        task_id=task_id,
        kind="message",
        payload={"message": "开始"},
        idempotency_key=f"message-{uuid4().hex}",
    )
    turn = await work_ledger.latest_turn(task_id)
    assert turn is not None

    def item(work_id: str) -> dict[str, Any]:
        return {
            "id": work_id,
            "work_key": work_id,
            "candidate_id": f"candidate-{work_id}",
            "capability": "content.visual",
            "skill_id": "skill.visual",
            "skill_version": "1",
            "skill_checksum": "checksum",
            "provider": "test",
            "input_payload": {},
            "reserved_tokens": 1,
            "reserved_wall_ms": 1,
            "status": "queued",
        }

    plan = await work_ledger.create_work_plan(
        task_id=task_id,
        turn_id=str(turn["id"]),
        expected_revision=0,
        items=[item("work-a"), item("work-b")],
        dependencies=[("work-b", "work-a")],
        budget={"token_budget": 100, "wall_ms_budget": 1000},
    )
    assert plan is not None
    return task_id, work_ledger


async def test_tracks_requires_work_id_and_ledger(state_db) -> None:
    _, _, _ = state_db
    scheduler = WorkScheduler(SimpleNamespace(task_id="t", work_ledger=None))
    assert scheduler.tracks("work-a") is False
    assert scheduler.tracks("") is False


async def test_dependency_blocked_work_is_not_claimable(state_db) -> None:
    database, _, learner_id = state_db
    task_id, ledger = await _plan_with_dependency(database, learner_id)
    scheduler = _scheduler(task_id, ledger)

    assert await scheduler.claim("work-b") is None, "dependency has not succeeded"
    claimed = await scheduler.claim("work-a")
    assert claimed is not None
    assert claimed["lease_owner"] == f"dispatcher:{task_id}"
    assert int(claimed["attempts"]) == 1


async def test_parallel_claim_has_a_single_owner(state_db) -> None:
    database, _, learner_id = state_db
    task_id, ledger = await _plan_with_dependency(database, learner_id)
    scheduler_a = _scheduler(task_id, ledger)
    scheduler_b = _scheduler(f"{task_id}-rival", ledger)

    first, second = await asyncio.gather(scheduler_a.claim("work-a"), scheduler_b.claim("work-a"))
    assert [claim is not None for claim in (first, second)].count(True) == 1


async def test_finish_succeeded_unblocks_dependent_work(state_db) -> None:
    database, _, learner_id = state_db
    task_id, ledger = await _plan_with_dependency(database, learner_id)
    scheduler = _scheduler(task_id, ledger)

    assert await scheduler.claim("work-a") is not None
    finished = await scheduler.finish(
        "work-a",
        status="succeeded",
        result={"schema_id": "visual.v1", "safe_summary": "完成", "usage": {"tokens": 1}},
    )
    assert finished is True
    assert await scheduler.claim("work-b") is not None, "dependency succeeded: ready"


async def test_failed_dependency_marks_dependent_blocked(state_db) -> None:
    database, _, learner_id = state_db
    task_id, ledger = await _plan_with_dependency(database, learner_id)
    scheduler = _scheduler(task_id, ledger)

    assert await scheduler.claim("work-a") is not None
    await scheduler.finish(
        "work-a",
        status="failed",
        result={"safe_summary": "provider error", "error_code": "provider_error"},
    )
    assert await scheduler.claim("work-b") is None
    row = await ledger.get_work(task_id=task_id, work_id="work-b")
    assert row is not None and row["status"] == "blocked"


async def test_finish_releases_the_lease(state_db) -> None:
    database, _, learner_id = state_db
    task_id, ledger = await _plan_with_dependency(database, learner_id)
    scheduler = _scheduler(task_id, ledger)

    assert await scheduler.claim("work-a") is not None
    await scheduler.finish("work-a", status="failed", result={"safe_summary": "boom"})
    row = await ledger.get_work(task_id=task_id, work_id="work-a")
    assert row is not None
    assert row["status"] == "failed"
    assert row["lease_owner"] is None


async def test_heartbeat_starts_and_stops_cleanly(state_db) -> None:
    database, _, learner_id = state_db
    task_id, ledger = await _plan_with_dependency(database, learner_id)
    scheduler = _scheduler(task_id, ledger)

    assert await scheduler.claim("work-a") is not None
    heartbeat = scheduler.start_heartbeat("work-a")
    assert not heartbeat.done()
    await scheduler.stop_heartbeat(heartbeat)
    assert heartbeat.done()
    # Stopping nothing is a no-op, so callers never need a None guard.
    await scheduler.stop_heartbeat(None)
