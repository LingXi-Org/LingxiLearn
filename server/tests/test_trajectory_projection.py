from datetime import UTC, datetime

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
            "type": "model",
            "startTime": "2026-08-16T00:00:00.350000+00:00",
            "endTime": "2026-08-16T00:00:00.700000+00:00",
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
