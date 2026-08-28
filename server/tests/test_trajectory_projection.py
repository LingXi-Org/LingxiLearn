import json
from datetime import UTC, datetime
from typing import Any

import pytest

from lingxilearn.api.workspace_route_shared import _utc_datetime
from lingxilearn.application.agent_events import (
    AgentEventService,
    _annotate_truncated_trajectory,
)
from lingxilearn.runtime.trajectory import TRAJECTORY_LANES, build_trajectory_projection


def test_projection_uses_execution_clock_and_eight_lanes() -> None:
    started = "2026-08-16T00:00:00+00:00"
    events = [
        {"kind": "round.started", "ts": started, "payload": {"step": 1, "decision_id": "d1"}},
        {
            "kind": "node.appeared",
            "ts": "2026-08-16T00:00:00.100000+00:00",
            "payload": {"node_id": "n1", "task_id": "t1", "capability": "search", "decision_id": "d1", "step": 1},
        },
        {
            "kind": "work.claimed",
            "ts": "2026-08-16T00:00:00.200000+00:00",
            "payload": {"node_id": "n1", "work_item_id": "w1", "attempt": 1},
        },
        {
            "kind": "node.started",
            "ts": "2026-08-16T00:00:00.300000+00:00",
            "payload": {"node_id": "n1", "task_id": "t1", "provider": "provider"},
        },
        {
            "kind": "node.completed",
            "ts": "2026-08-16T00:00:00.800000+00:00",
            "payload": {"node_id": "n1", "task_id": "t1", "status": "completed"},
        },
        {
            "kind": "round.completed",
            "ts": "2026-08-16T00:00:00.900000+00:00",
            "payload": {"step": 1, "decision_id": "d1", "runtime_status": "completed"},
        },
    ]
    trace = [
        {
            "id": "model-1",
            "name": "Model",
            "kind": "model",
            "startedAt": "2026-08-16T00:00:00.350000+00:00",
            "endedAt": "2026-08-16T00:00:00.700000+00:00",
            "tokens": {"total": 12},
        }
    ]
    projection = build_trajectory_projection(
        {"id": "exec-1", "started_at": started, "ended_at": "2026-08-16T00:00:01+00:00", "status": "completed"},
        events,
        trace,
    )

    assert [lane["id"] for lane in projection["lanes"]] == list(TRAJECTORY_LANES[i][0] for i in range(8))
    assert projection["clock"]["startedAt"] == started
    assert projection["lanes"][1]["items"][0]["relativeStartMs"] == 0
    task = projection["lanes"][2]["items"][0]
    assert task["parentId"] == "round:d1"
    assert task["precision"] == "exact"
    queue = next(item for item in projection["lanes"][6]["items"] if item["kind"] == "queue.wait")
    assert queue["durationMs"] == 100


def test_projection_is_execution_scoped_by_input_events() -> None:
    projection = build_trajectory_projection(
        {
            "id": "exec-2",
            "started_at": datetime(2026, 8, 16, tzinfo=UTC),
            "ended_at": datetime(2026, 8, 16, 0, 0, 1, tzinfo=UTC),
            "status": "completed",
        },
        [{"kind": "agent.output", "payload": {"message": "only this run"}, "ts": "2026-08-16T00:00:00.500000+00:00"}],
    )
    output_items = [
        item
        for item in projection["lanes"][7]["items"]
        if item["kind"] == "agent.output"
    ]
    assert output_items and output_items[0]["metadata"]["message"] == "only this run"


def test_round_lifecycle_uses_step_and_suppresses_legacy_fallback() -> None:
    projection = build_trajectory_projection(
        {
            "id": "exec-round",
            "started_at": "2026-08-16T00:00:00+00:00",
            "ended_at": "2026-08-16T00:00:01+00:00",
            "status": "completed",
        },
        [
            {
                "kind": "plan.created",
                "ts": "2026-08-16T00:00:00.050000+00:00",
                "payload": {"step": 1, "decision_id": "legacy"},
            },
            {
                "kind": "round.started",
                "ts": "2026-08-16T00:00:00.100000+00:00",
                "payload": {"step": 1},
            },
            {
                "kind": "node.appeared",
                "ts": "2026-08-16T00:00:00.200000+00:00",
                "payload": {"node_id": "n1", "step": 1},
            },
            {
                "kind": "round.completed",
                "ts": "2026-08-16T00:00:00.500000+00:00",
                "payload": {"step": 1, "decision_id": "d1", "runtime_status": "completed"},
            },
            {
                "kind": "decision.recorded",
                "ts": "2026-08-16T00:00:00.600000+00:00",
                "payload": {"step": 1, "decision_id": "legacy"},
            },
        ],
    )

    rounds = [item for item in projection["lanes"][1]["items"] if item["kind"] == "round"]
    assert len(rounds) == 1
    assert rounds[0]["id"] == "round:d1"
    assert rounds[0]["durationMs"] == 400
    task = projection["lanes"][2]["items"][0]
    assert task["parentId"] == rounds[0]["id"]


def test_control_and_resource_projection_is_independent_and_first_output_is_execution_scoped() -> None:
    projection = build_trajectory_projection(
        {
            "id": "exec-resources",
            "started_at": "2026-08-16T00:00:00+00:00",
            "ended_at": "2026-08-16T00:00:01+00:00",
        },
        [
            {
                "kind": "assistant.delta",
                "ts": "2026-08-16T00:00:00.500000+00:00",
                "payload": {"stream_id": "s", "text": "first"},
            },
            {
                "kind": "agent.output.delta",
                "ts": "2026-08-16T00:00:00.600000+00:00",
                "payload": {"stream_id": "s", "text": "second"},
            },
        ],
        [
            {
                "id": "interpret-1",
                "name": "Interpret goal",
                "kind": "router_v2",
                "primitive": "interpret_goal",
                "category": "control",
                "startedAt": "2026-08-16T00:00:00.100000+00:00",
                "endedAt": "2026-08-16T00:00:00.200000+00:00",
            },
            {
                "id": "model-1",
                "name": "Model",
                "kind": "model",
                "startedAt": "2026-08-16T00:00:00.200000+00:00",
                "endedAt": "2026-08-16T00:00:00.400000+00:00",
                "tokens": {"total": 4},
            },
            {
                "id": "tool-1",
                "name": "Tool",
                "kind": "tool",
                "startedAt": "2026-08-16T00:00:00.400000+00:00",
                "endedAt": "2026-08-16T00:00:00.450000+00:00",
            },
        ],
    )

    control = projection["lanes"][1]["items"]
    resources = projection["lanes"][6]["items"]
    output = projection["lanes"][7]["items"]
    assert any(item["kind"] == "interpret_goal" for item in control)
    assert {item["kind"] for item in resources} >= {"model.duration", "tool.duration", "tokens"}
    assert sum(item["kind"] == "first.output" for item in output) == 1


def test_sqlite_naive_running_timestamp_is_safe_for_aware_duration_math() -> None:
    started = _utc_datetime(datetime(2026, 8, 16, 0, 0, 0))
    now = _utc_datetime(datetime(2026, 8, 16, 0, 0, 1, tzinfo=UTC))
    assert started is not None and now is not None
    assert int((now - started).total_seconds() * 1000) == 1000


def test_concurrent_same_model_ttft_uses_event_identity_and_delta_only_payloads() -> None:
    """Production deltas carry no model name, so identity must do the join."""

    projection = build_trajectory_projection(
        {
            "id": "exec-concurrent-models",
            "started_at": "2026-08-16T00:00:00+00:00",
            "ended_at": "2026-08-16T00:00:01+00:00",
            "status": "completed",
        },
        [
            {
                "kind": "assistant.delta",
                "agent": "lesson_intro",
                "runtime": {
                    "span_id": "model-a",
                    "node": "provider",
                    "work_item_id": "work-a",
                },
                "ts": "2026-08-16T00:00:00.250000+00:00",
                "payload": {"delta": "A"},
            },
            {
                "kind": "assistant.delta",
                "agent": "lesson_intro",
                "runtime": {"node": "provider", "work_item_id": "work-b"},
                "ts": "2026-08-16T00:00:00.350000+00:00",
                "payload": {"delta": "B"},
            },
        ],
        [
            {
                "id": "agent-a",
                "kind": "agent",
                "agent": "lesson_intro",
                "node": "provider",
                "runtime": {"work_item_id": "work-a"},
                "startedAt": "2026-08-16T00:00:00.100000+00:00",
                "endedAt": "2026-08-16T00:00:00.800000+00:00",
                "children": [
                    {
                        "id": "model-a",
                        "kind": "model",
                        "model": "same-model",
                        "runtime": {
                            "span_id": "model-a",
                            "node": "provider",
                            "work_item_id": "work-a",
                        },
                        "startedAt": "2026-08-16T00:00:00.200000+00:00",
                        "endedAt": "2026-08-16T00:00:00.600000+00:00",
                    }
                ],
            },
            {
                "id": "agent-b",
                "kind": "agent",
                "agent": "lesson_intro",
                "node": "provider",
                "runtime": {"work_item_id": "work-b"},
                "startedAt": "2026-08-16T00:00:00.100000+00:00",
                "endedAt": "2026-08-16T00:00:00.800000+00:00",
                "children": [
                    {
                        "id": "model-b",
                        "kind": "model",
                        "model": "same-model",
                        "runtime": {"node": "provider", "work_item_id": "work-b"},
                        "startedAt": "2026-08-16T00:00:00.200000+00:00",
                        "endedAt": "2026-08-16T00:00:00.700000+00:00",
                    }
                ],
            },
        ],
    )

    ttft = [
        item
        for item in projection["lanes"][6]["items"]
        if item["kind"] == "model.ttft"
    ]
    assert {item["parentId"] for item in ttft} == {"action:model-a", "action:model-b"}
    by_parent = {item["parentId"]: item for item in ttft}
    assert by_parent["action:model-a"]["durationMs"] == 50
    assert by_parent["action:model-b"]["durationMs"] == 150
    assert by_parent["action:model-a"]["metadata"]["agent"] == "lesson_intro"
    assert by_parent["action:model-b"]["metadata"]["runtime"]["work_item_id"] == "work-b"


@pytest.mark.asyncio
async def test_execution_snapshot_event_reader_pages_past_5000_without_truncating() -> None:
    class PagedRepo:
        def __init__(self) -> None:
            self.events = [
                {
                    "sequence": sequence,
                    "kind": "checkpoint.saved",
                    "payload": {"sequence": sequence},
                    "runtime": {},
                    "ts": f"2026-08-16T00:00:{sequence // 1000:02d}.{sequence % 1000:03d}+00:00",
                }
                for sequence in range(1, 5002)
            ]
            self.calls: list[int] = []

        async def agent_event_count_for_execution(self, _execution_id: str) -> int:
            return len(self.events)

        async def agent_events_for_execution(
            self, _execution_id: str, _learner_id: str, *, limit: int, after: int
        ) -> list[dict[str, Any]]:
            self.calls.append(after)
            return self.events[after : after + limit]

    repo = PagedRepo()
    events = AgentEventService.__new__(AgentEventService)
    events._agent_tasks = repo

    records, status = await events._agent_events_for_execution_snapshot("exec", "learner")

    assert len(records) == 5001
    assert status["truncated"] is False
    assert status["complete"] is True
    assert repo.calls == [0, 5000]


def test_truncated_event_read_marks_only_uncertain_trajectory_tail_inferred() -> None:
    trajectory = {
        "lanes": [
            {
                "id": "run",
                "items": [{"id": "run:1", "precision": "exact"}],
            },
            {
                "id": "action",
                "items": [
                    {
                        "id": "action:before",
                        "startTime": "2026-08-16T00:00:00.100000+00:00",
                        "precision": "exact",
                    },
                    {
                        "id": "action:after",
                        "startTime": "2026-08-16T00:00:00.900000+00:00",
                        "precision": "exact",
                    },
                ],
            },
        ]
    }
    _annotate_truncated_trajectory(
        trajectory,
        {
            "truncated": True,
            "complete": False,
            "truncatedAfter": "2026-08-16T00:00:00.800000+00:00",
        },
    )
    before, after = trajectory["lanes"][1]["items"]
    assert before["precision"] == "exact"
    assert after["precision"] == "inferred"
    assert after["metadata"]["eventLogTruncated"] is True


# -- publication boundary (issue #18 §5.4/§20) --------------------------------

RAW_MODEL_JSON = (
    '{"answer": "正确选项是 B", "confidence": 0.91, "reasoning": "先排除 A"'
)


def _raw_stream_projection() -> dict[str, Any]:
    """A run whose provider streamed raw model text before publishing output."""

    return build_trajectory_projection(
        {
            "id": "exec-raw",
            "started_at": "2026-08-16T00:00:00+00:00",
            "ended_at": "2026-08-16T00:00:02+00:00",
            "status": "completed",
        },
        [
            {
                "kind": "assistant.delta",
                "agent": "answer_user",
                "ts": "2026-08-16T00:00:00.400000+00:00",
                "payload": {"delta": RAW_MODEL_JSON, "stream_id": "s1"},
            },
            {
                "kind": "assistant.delta",
                "agent": "answer_user",
                "ts": "2026-08-16T00:00:00.600000+00:00",
                "payload": {"delta": '}', "stream_id": "s1"},
            },
            {
                "kind": "agent.output.delta",
                "agent": "answer_user",
                "ts": "2026-08-16T00:00:01+00:00",
                "payload": {"delta": "先想想两个态叠加", "stream_id": "s2"},
            },
            {
                "kind": "agent.output",
                "agent": "answer_user",
                "ts": "2026-08-16T00:00:01.500000+00:00",
                "payload": {"message": "先想想两个态叠加意味着什么。", "stream_id": "s2"},
            },
        ],
    )


def test_raw_model_stream_keeps_its_timing_but_never_its_text() -> None:
    projection = _raw_stream_projection()
    output_items = projection["lanes"][7]["items"]
    raw = [item for item in output_items if item["id"].startswith("output:assistant.delta")]

    # The item still exists: time-to-first-output must stay measurable.
    assert raw, "the raw stream must remain visible as timing"
    assert raw[0]["metadata"]["events"] == 2
    assert raw[0]["metadata"]["chars"] == len(RAW_MODEL_JSON) + 1
    assert "delta" not in raw[0]["metadata"]

    serialized = json.dumps(projection, ensure_ascii=False)
    assert RAW_MODEL_JSON not in serialized
    assert "正确选项是 B" not in serialized
    assert "先排除 A" not in serialized

    # The provider's own published lane is what the learner already saw.
    settled = [item for item in output_items if item["kind"] == "agent.output"]
    assert settled and settled[0]["metadata"]["message"] == "先想想两个态叠加意味着什么。"
    streamed = [item for item in output_items if item["id"].startswith("output:agent.output.delta")]
    assert streamed and "delta" not in streamed[0]["metadata"]


def test_private_payload_keys_never_reach_item_metadata() -> None:
    projection = build_trajectory_projection(
        {
            "id": "exec-private",
            "started_at": "2026-08-16T00:00:00+00:00",
            "ended_at": "2026-08-16T00:00:01+00:00",
            "status": "completed",
        },
        [
            {
                "kind": "decision.recorded",
                "ts": "2026-08-16T00:00:00.500000+00:00",
                "payload": {
                    "decision_id": "d1",
                    "capability": "dialog.answer",
                    "hypotheses": ["学习者其实想要解题训练"],
                    "plan": {"tiers": [["t1"]]},
                    "api_key": "sk-should-never-appear",
                    "nested": {"reasoning": "隐藏推理"},
                },
            }
        ],
    )
    serialized = json.dumps(projection, ensure_ascii=False)
    assert "sk-should-never-appear" not in serialized
    assert "隐藏推理" not in serialized
    assert "学习者其实想要解题训练" not in serialized
    assert "dialog.answer" in serialized, "safe identity fields still project"
