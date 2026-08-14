from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from lingxigraph import EventKind

from lingxilearn.runtime.schedules import SchedulerWorker, next_schedule_time, validate_schedule
from lingxilearn.runtime.sim_semantics import SimRunProjector, SimRuntimeError


def event(kind, *, node="lecture_hook", step=1, task_id="task-1", data=None):
    return SimpleNamespace(
        kind=kind,
        run_id="run-1",
        step=step,
        node=node,
        task_id=task_id,
        namespace=("agent",),
        checkpoint_id="cp-1",
        span_id=f"span-{node}-{step}",
        timestamp=None,
        data=data or {},
    )


def test_projection_uses_actual_nodes_and_preserves_runtime_metadata():
    projector = SimRunProjector("exec-1", "task-1", "knowledge_deep_dive.v1")
    started = projector.consume(event(EventKind.NODE_STARTED), agent="lecture_hook")
    completed = projector.consume(
        event(EventKind.NODE_COMPLETED, data={"update": {"topic": "StateGraph"}}),
        agent="lecture_hook",
    )
    snapshot = projector.snapshot()
    assert started["execution_id"] == "exec-1"
    assert started["payload"]["blockId"] == completed["payload"]["blockId"]
    assert snapshot["workflowState"]["blocks"]
    assert snapshot["traceSpans"][0]["status"] == "completed"


def test_parallel_and_loop_instances_are_projected_from_events():
    projector = SimRunProjector("exec-2", "task-1", "v1")
    for node in ("lecture_hook", "interactive_lecture_deck"):
        projector.consume(event(EventKind.NODE_STARTED, node=node, step=1), agent=node)
    projector.consume(event(EventKind.NODE_STARTED, node="await_user", step=2), agent="await_user")
    projector.consume(event(EventKind.NODE_STARTED, node="await_user", step=3), agent="await_user")
    state = projector.snapshot()["workflowState"]
    assert state["parallels"]["parallel:1"]["blockIds"]
    assert state["loops"]["loop:await_user"]["iterations"]


def test_unknown_primitive_fails_closed():
    projector = SimRunProjector("exec-3", "task-1", "v1")
    with pytest.raises(SimRuntimeError):
        projector.consume(event(EventKind.NODE_STARTED, node="unregistered_node"))


def test_runtime_loop_nodes_are_registered():
    from lingxilearn.runtime.sim_semantics import PrimitiveCatalog

    catalog = PrimitiveCatalog()
    catalog.validate(
        {
            "interpret_goal",
            "orchestrate",
            "dispatch",
            "observe",
            "update_state",
            "evaluate_goal",
            "await_user",
        }
    )


def test_retry_translation_is_opt_in_and_only_idempotent():
    from lingxilearn.runtime.sim_semantics import PrimitiveCatalog

    catalog = PrimitiveCatalog()
    assert (
        catalog.lingxi_retry_policy("knowledge.search", max_tries=3, wait_seconds=2).jitter is False
    )
    assert catalog.lingxi_retry_policy("lecture_hook") is None
    with pytest.raises(SimRuntimeError):
        catalog.lingxi_retry_policy("lecture_hook", max_tries=2)


def test_schedule_validation_uses_iana_timezone_and_cron():
    cron, zone = validate_schedule("*/15 * * * *", "Asia/Shanghai")
    assert cron == "*/15 * * * *"
    assert zone == "Asia/Shanghai"
    next_run = next_schedule_time(cron, zone, datetime(2026, 8, 14, tzinfo=UTC))
    assert next_run.tzinfo is not None


def test_scheduler_runs_one_catch_up_then_skips_missed_slots():
    class Repo:
        async def claim_due_schedule(self, **_kwargs):
            return {
                "schedule_id": "schedule-1",
                "run_id": "run-1",
                "scheduled_for": datetime(2026, 8, 14, 9, 0, tzinfo=UTC),
                "cron": "*/15 * * * *",
                "timezone": "UTC",
            }

        async def finish_schedule_claim(self, **kwargs):
            self.finished = kwargs

    async def launch(_claim):
        return "execution-1"

    async def run():
        repo = Repo()
        result = await SchedulerWorker(repo, launch).run_once(
            datetime(2026, 8, 14, 10, 1, tzinfo=UTC)
        )
        assert result is not None
        assert result["next_run_at"] == datetime(2026, 8, 14, 10, 15, tzinfo=UTC)
        assert repo.finished["execution_id"] == "execution-1"

    import asyncio

    asyncio.run(run())
