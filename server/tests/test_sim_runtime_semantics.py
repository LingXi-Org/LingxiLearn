from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from lingxigraph import EventKind

from lingxilearn.runtime.schedules import SchedulerWorker, next_schedule_time, validate_schedule
from lingxilearn.runtime.sim_semantics import (
    SimRunProjector,
    SimRuntimeError,
    replay_sim_trace,
    visible_execution,
)


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


def test_parallel_semantic_nodes_are_projected_but_runtime_mechanics_are_hidden():
    projector = SimRunProjector("exec-2", "task-1", "v1")
    for node in ("lecture_hook", "interactive_lecture_deck"):
        projector.consume(event(EventKind.NODE_STARTED, node=node, step=1), agent=node)
    projector.consume(event(EventKind.NODE_STARTED, node="await_user", step=2), agent="await_user")
    projector.consume(event(EventKind.NODE_STARTED, node="await_user", step=3), agent="await_user")
    state = projector.snapshot()["workflowState"]
    assert state["parallels"]["parallel:1"]["blockIds"]
    assert not state["loops"]
    assert {block["name"] for block in state["blocks"].values()} == {
        "Lesson Intro",
        "Lecture Deck",
    }


def test_unknown_runtime_node_is_hidden_and_catalog_still_fails_closed():
    projector = SimRunProjector("exec-3", "task-1", "v1")
    projected = projector.consume(event(EventKind.NODE_STARTED, node="unregistered_node"))
    assert projected["payload"]["hiddenBy"] == "lingxi-runtime"
    assert not projector.snapshot()["workflowState"]["blocks"]
    with pytest.raises(SimRuntimeError):
        projector.catalog.resolve("unregistered_node")


def test_planned_capabilities_become_semantic_nodes_and_hidden_tasks_collapse_to_edges():
    projector = SimRunProjector("exec-semantic", "task-1", "v1")
    projector.consume_runtime_event(
        "node.appeared",
        {"task_id": "intro", "step": 1, "capability": "content.lesson_intro"},
    )
    projector.consume_runtime_event(
        "node.appeared",
        {
            "task_id": "runtime-check",
            "step": 1,
            "capability": "meta.evaluate",
            "depends_on": ["intro"],
        },
    )
    projector.consume_runtime_event(
        "node.appeared",
        {
            "task_id": "probe",
            "step": 1,
            "capability": "assess.generate",
            "depends_on": ["runtime-check"],
        },
    )
    projector.consume_runtime_event(
        "node.started",
        {
            "task_id": "probe",
            "capability": "assess.generate",
            "provider": "pack_probe",
        },
    )
    state = projector.snapshot()["workflowState"]
    assert {block["name"] for block in state["blocks"].values()} == {
        "Lesson Intro",
        "Knowledge Probe",
    }
    probe = next(block for block in state["blocks"].values() if block["name"] == "Knowledge Probe")
    assert probe["executionState"] == "running"
    assert probe["data"]["nodeKind"] == "deterministic"
    assert state["edges"][0]["data"]["label"] == "Lingxi Runtime"


def test_replanned_logical_task_ids_keep_distinct_runtime_blocks():
    projector = SimRunProjector("exec-replan", "task-1", "v1")
    projector.consume_runtime_event(
        "node.appeared",
        {
            "task_id": "t1",
            "node_id": "exec-replan:1:t1",
            "step": 1,
            "capability": "content.lesson_intro",
        },
    )
    projector.consume_runtime_event(
        "node.appeared",
        {
            "task_id": "t1",
            "node_id": "exec-replan:2:t1",
            "step": 2,
            "capability": "content.deck",
        },
    )
    projector.consume_runtime_event(
        "node.started",
        {
            "task_id": "t1",
            "node_id": "exec-replan:2:t1",
            "step": 2,
            "capability": "content.deck",
            "provider": "lecture_deck",
        },
    )

    blocks = projector.snapshot()["workflowState"]["blocks"]
    assert set(blocks) == {"plan:1:exec-replan:1:t1", "plan:2:exec-replan:2:t1"}
    assert blocks["plan:1:exec-replan:1:t1"]["executionState"] == "queued"
    assert blocks["plan:2:exec-replan:2:t1"]["executionState"] == "running"


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


def test_trace_replay_accepts_catalog_primitives_without_explicit_labels():
    trace = replay_sim_trace(
        [
            {
                "kind": "node.started",
                "agent": "coordinator",
                "payload": {"data": {}},
                "runtime": {"node": "orchestrate", "step": 1, "task_id": "task-1"},
                "ts": "2026-08-16T01:21:00+00:00",
            }
        ],
        execution_id="exec-replay",
        task_id="task-1",
        graph_version="v1",
        status="failed",
    )
    assert trace[0]["children"][0]["name"] == "orchestrate"


def test_trace_replay_keeps_concurrent_same_model_events_in_their_runtime_bucket():
    records = [
        {
            "kind": "model.started",
            "agent": "lesson_intro",
            "payload": {"model": "same-model"},
            "runtime": {"span_id": "native-a", "node": "provider", "work_item_id": "work-a"},
            "ts": "2026-08-16T01:00:00.100000+00:00",
        },
        {
            "kind": "model.started",
            "agent": "lesson_intro",
            "payload": {"model": "same-model"},
            "runtime": {"span_id": "native-b", "node": "provider", "work_item_id": "work-b"},
            "ts": "2026-08-16T01:00:00.150000+00:00",
        },
        {
            "kind": "assistant.delta",
            "agent": "lesson_intro",
            "payload": {"delta": "A"},
            "runtime": {"span_id": "native-a", "node": "provider", "work_item_id": "work-a"},
            "ts": "2026-08-16T01:00:00.200000+00:00",
        },
        {
            "kind": "assistant.delta",
            "agent": "lesson_intro",
            "payload": {"delta": "B"},
            "runtime": {"span_id": "native-b", "node": "provider", "work_item_id": "work-b"},
            "ts": "2026-08-16T01:00:00.250000+00:00",
        },
        {
            "kind": "model.completed",
            "agent": "lesson_intro",
            "payload": {"model": "same-model"},
            "runtime": {"span_id": "native-a", "node": "provider", "work_item_id": "work-a"},
            "ts": "2026-08-16T01:00:00.500000+00:00",
        },
        {
            "kind": "model.completed",
            "agent": "lesson_intro",
            "payload": {"model": "same-model"},
            "runtime": {"span_id": "native-b", "node": "provider", "work_item_id": "work-b"},
            "ts": "2026-08-16T01:00:00.550000+00:00",
        },
    ]
    trace = replay_sim_trace(
        records,
        execution_id="exec-concurrent-models",
        task_id="task-1",
        graph_version="v1",
        status="completed",
        started_at="2026-08-16T01:00:00+00:00",
        ended_at="2026-08-16T01:00:01+00:00",
    )
    model_spans = [
        span
        for agent in trace[0]["children"]
        for span in agent.get("children") or []
        if span.get("type") == "model"
    ]
    assert [
        next(
            event["runtime"]["span_id"]
            for event in span["events"]
            if event["kind"] == "model.completed"
        )
        for span in model_spans
    ] == ["native-a", "native-b"]


@pytest.mark.parametrize(
    ("alias", "label"),
    [
        ("answer_user", "Tutor"),
        ("learning_companion", "Learning Companion"),
        ("dialog.converse", "Learning Companion"),
        ("probe_user", "Socratic Probe"),
        ("dialog.probe", "Socratic Probe"),
        ("adaptive_pedagogy", "Adaptive Tutor"),
        ("lesson_intro", "Lesson Intro"),
        ("lecture_deck", "Lecture Deck"),
        ("visual_explainer", "Visual Explainer"),
        ("quiz_generator", "Quiz Generator"),
        ("formative_assessor", "Formative Assessor"),
        ("retrieval_practice", "Retrieval Practice"),
        ("prerequisite_analyzer", "Curriculum Mapper"),
        ("learner_reflector", "Learner Reflector"),
        ("pack_investigate", "Investigator"),
        ("pack_report", "Learning Reporter"),
        ("skill_forge", "Skill Forge"),
        ("pack_probe", "Knowledge Probe"),
        ("deterministic_grader", "Deterministic Grader"),
    ],
)
def test_visible_execution_vocabulary(alias, label):
    assert visible_execution(alias).label == label


@pytest.mark.parametrize(
    "mechanic",
    [
        "interpret_goal",
        "orchestrate",
        "dispatch",
        "observe",
        "update_state",
        "evaluate_goal",
        "await_user",
        "ProfileWriter",
        "Skill Registry",
        "Skill Resolver",
        "Guardrails",
        "Completion Evaluator",
        "Artifact Validator",
        "Evidence Emitter",
        "Structured Output",
        "Graceful Degradation",
        "Decision Trace",
        "Budget Manager",
    ],
)
def test_runtime_mechanics_never_become_visible_nodes(mechanic):
    assert visible_execution(mechanic) is None


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
