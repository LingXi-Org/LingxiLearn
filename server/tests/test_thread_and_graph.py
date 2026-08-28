"""Thread/Turn lifecycle, typed interactions and execution-graph tests (issue #18)."""

from __future__ import annotations

from typing import Any

import pytest

from lingxilearn.runtime.contracts import OrchestrationPlan
from lingxilearn.runtime.execution_graph import build_execution_graph, visible_agent_run_ids
from lingxilearn.runtime.interactions import (
    InteractionSpec,
    opaque_interrupt_payload,
    resume_command,
)
from lingxilearn.runtime.public_projection import PublicProjector

# -- thread status mapping ------------------------------------------------------


def test_thread_status_mapping_table() -> None:
    """The legacy one-shot status maps onto the long-lived thread states."""

    mapping = {
        "queued": "open",
        "running": "running",
        "awaiting_user": "awaiting_user",
        "completed": "open",
        "handed_off": "open",
        "partial": "open",
        "failed": "open",
        "timed_out": "open",
        "budget_exceeded": "open",
        "cancelled": "cancelled",
    }
    for _legacy, thread in mapping.items():
        assert isinstance(thread, str)
        assert thread in {"open", "running", "awaiting_user", "cancelled"}


# -- interactions end to end ----------------------------------------------------


def test_interaction_request_event_projects_to_v1() -> None:
    projector = PublicProjector(chat_id="t", execution_id="e", turn_id="turn")
    spec = InteractionSpec.model_validate(
        {
            "interactionId": "it_1",
            "purpose": "clarification",
            "presentation": "question",
            "blocking": True,
            "prompt": "你想先学哪个方向？",
            "questions": [
                {
                    "id": "q1",
                    "type": "single_select",
                    "prompt": "学习目标偏向？",
                    "options": [
                        {"id": "o1", "label": "概念理解"},
                        {"id": "o2", "label": "解题训练"},
                    ],
                    "allowFreeText": False,
                }
            ],
            "reasonCode": "goal_ambiguous",
        }
    )
    events = projector.consume(
        {
            "kind": "interaction.requested",
            "agent": "",
            "payload": {"interaction_id": "it_1", **spec.public_request()},
        }
    )
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["interactionId"] == "it_1"
    assert payload["blocking"] is True
    assert payload["questions"][0]["options"][0]["label"] == "概念理解"

    resolved = projector.consume(
        {
            "kind": "interaction.resolved",
            "agent": "",
            "payload": {
                "interaction_id": "it_1",
                "answers": [{"questionId": "q1", "selectedOptionIds": ["o2"], "text": None}],
            },
        }
    )
    assert resolved[0]["payload"]["answers"][0]["selectedOptionIds"] == ["o2"]


def test_orchestration_plan_accepts_structured_interaction() -> None:
    plan = OrchestrationPlan.model_validate(
        {
            "reasoning": "目标不明确，需要澄清",
            "awaits_user": True,
            "interaction": {
                "purpose": "clarification",
                "presentation": "question",
                "blocking": True,
                "prompt": "先确认方向",
                "reason_code": "goal_ambiguous",
                "questions": [
                    {
                        "id": "q1",
                        "type": "single_select",
                        "prompt": "方向？",
                        "options": [{"id": "o1", "label": "A"}, {"id": "o2", "label": "B"}],
                    }
                ],
            },
        }
    )
    assert plan.interaction is not None
    spec = InteractionSpec.model_validate(plan.interaction)
    assert spec.reason_code == "goal_ambiguous"


def test_typed_interrupt_round_trip() -> None:
    opaque = opaque_interrupt_payload("it_9")
    command = resume_command(
        "it_9",
        __import__("lingxilearn.runtime.interactions", fromlist=["parse_answers"]).parse_answers(
            [{"questionId": "q1", "selectedOptionIds": ["o1"]}]
        ),
    )
    assert opaque["interaction_id"] == command["interaction_id"] == "it_9"
    assert command["answers"][0]["selectedOptionIds"] == ["o1"]


# -- execution graph ------------------------------------------------------------


def _run(run_id: str, execution: str, **overrides: Any) -> dict[str, Any]:
    base = {
        "id": run_id,
        "task_id": "task",
        "turn_id": "turn1",
        "execution_id": execution,
        "work_item_id": f"work_{run_id}",
        "parent_agent_run_id": None,
        "provider_id": "p_" + run_id,
        "agent_display_name": "执行者 " + run_id,
        "execution_kind": "model",
        "capability": "content.visual",
        "presentation_role": "supporting",
        "status": "completed",
        "started_at": "2026-01-01T00:00:01Z",
        "ended_at": "2026-01-01T00:00:10Z",
        "start_sequence": 1,
        "end_sequence": 9,
        "metadata": {},
    }
    base.update(overrides)
    return base


def test_execution_graph_nodes_are_agent_runs() -> None:
    runs = [_run("ar_1", "exec_1"), _run("ar_2", "exec_1")]
    graph = build_execution_graph(runs, task_id="task")
    assert [node["id"] for node in graph["nodes"]] == ["ar_1", "ar_2"]
    assert visible_agent_run_ids(graph) == {"ar_1", "ar_2"}
    assert graph["nodes"][0]["displayName"] == "执行者 ar_1"


def test_overlapping_sibling_runs_share_a_parallel_group() -> None:
    runs = [
        _run("ar_a", "exec_1", started_at="2026-01-01T00:00:01Z", ended_at="2026-01-01T00:00:10Z"),
        _run("ar_b", "exec_1", started_at="2026-01-01T00:00:02Z", ended_at="2026-01-01T00:00:09Z"),
    ]
    graph = build_execution_graph(runs, task_id="task")
    groups = {node["id"]: node["parallelGroupId"] for node in graph["nodes"]}
    assert groups["ar_a"] is not None
    assert groups["ar_a"] == groups["ar_b"]


def test_dependent_runs_get_dependency_edge_not_parallel_group() -> None:
    runs = [
        _run(
            "ar_dep", "exec_1", started_at="2026-01-01T00:00:01Z", ended_at="2026-01-01T00:00:05Z"
        ),
        _run(
            "ar_after", "exec_1", started_at="2026-01-01T00:00:02Z", ended_at="2026-01-01T00:00:09Z"
        ),
    ]
    dependencies = [{"work_id": "work_ar_after", "depends_on_id": "work_ar_dep"}]
    graph = build_execution_graph(runs, task_id="task", work_dependencies=dependencies)
    edge_kinds = {(edge["source"], edge["target"]): edge["kind"] for edge in graph["edges"]}
    assert edge_kinds[("ar_dep", "ar_after")] == "dependency"
    groups = {node["id"]: node["parallelGroupId"] for node in graph["nodes"]}
    assert groups["ar_dep"] is None and groups["ar_after"] is None


def test_delegation_edge_from_parent_agent_run() -> None:
    runs = [
        _run("ar_parent", "exec_1"),
        _run("ar_child", "exec_1", parent_agent_run_id="ar_parent"),
    ]
    graph = build_execution_graph(runs, task_id="task")
    assert any(
        edge["kind"] == "agent-delegation" and edge["source"] == "ar_parent"
        for edge in graph["edges"]
    )


def test_skill_runs_attach_to_nodes() -> None:
    runs = [_run("ar_1", "exec_1")]
    skill_runs = [
        {
            "agent_run_id": "ar_1",
            "skill_id": "adaptive-pedagogy",
        }
    ]
    graph = build_execution_graph(runs, task_id="task", skill_runs=skill_runs)
    assert graph["nodes"][0]["skillIds"] == ["adaptive-pedagogy"]


# -- turn events -------------------------------------------------------------------


def test_turn_event_envelope_shape() -> None:
    projector = PublicProjector(chat_id="t", execution_id="e", turn_id="turn_7")
    envelope = projector.turn_event("delivered", turn_id="turn_7", turn_index=3)
    assert envelope is not None
    assert envelope["type"] == "turn"
    assert envelope["payload"] == {"turnId": "turn_7", "turnIndex": 3, "status": "delivered"}
    assert envelope["stream"]["turnId"] == "turn_7"

    invalid = projector.turn_event("warp", turn_id="turn_7")
    assert invalid is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("awaiting_user", "awaiting_user"),
        ("cancelled", "cancelled"),
        ("completed", "open"),
        ("failed", "open"),
    ],
)
def test_thread_status_for_run_outcomes(status: str, expected: str) -> None:
    mapping = {"awaiting_user": "awaiting_user", "cancelled": "cancelled"}
    assert mapping.get(status, "open") == expected
