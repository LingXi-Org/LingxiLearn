"""Execution timeline pause-duration semantics (issue #32 §3).

Waiting for the learner must never be attributed to Agent/Skill active
execution time: pausing for hours must not make the trace show hours of
active work, and the excluded interval must stay excluded after resume.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from lingxigraph import EventKind

from lingxilearn.runtime.timeline import ExecutionTimelineProjector


def _resolve_primitive(name: str) -> SimpleNamespace:
    return SimpleNamespace(display_kind="agent", category="agent", idempotent=False, label=name)


def test_paused_duration_freezes_active_time_and_excludes_the_wait_after_resume() -> None:
    started = datetime(2026, 1, 1, tzinfo=UTC)
    projector = ExecutionTimelineProjector(
        execution_id="exec-1",
        task_id="task-1",
        graph_version="test@1",
        resolve_primitive=_resolve_primitive,
        started_at=started,
    )

    projector.consume_event("run.started", {}, agent="coordinator", timestamp=started)
    work_started = started + timedelta(seconds=5)
    projector.consume_event(
        "agent.started",
        {"task_id": "t1", "capability": "dialog.answer", "provider": "fake_teacher"},
        agent="fake_teacher",
        timestamp=work_started,
    )
    work_done = started + timedelta(seconds=95)
    projector.consume_event(
        "agent.completed",
        {"task_id": "t1", "status": "completed"},
        agent="fake_teacher",
        timestamp=work_done,
    )

    pause_started = started + timedelta(seconds=100)
    projector.consume_event("run.paused", {}, agent="coordinator", timestamp=pause_started)

    snapshot_before_wait = projector.snapshot(status="awaiting_user", ended_at=pause_started)
    root_before = snapshot_before_wait[0]
    active_at_pause = root_before["activeDurationMs"]
    assert active_at_pause == 100_000

    # The learner sits on WAITING_FOR_USER for six hours. Repeated polling
    # snapshots during that wait must not keep inflating active duration.
    six_hours_later = pause_started + timedelta(hours=6)
    root_after_wait = projector.snapshot(status="awaiting_user", ended_at=six_hours_later)[0]
    assert root_after_wait["activeDurationMs"] == active_at_pause, (
        "active execution time must stop growing while paused"
    )
    assert root_after_wait["waitingForUserMs"] == 6 * 60 * 60 * 1000
    assert root_after_wait["wallDurationMs"] == active_at_pause + 6 * 60 * 60 * 1000
    # Backward-compatible field mirrors active time, not multi-hour wall time.
    assert root_after_wait["durationMs"] == active_at_pause

    # A second poll a few seconds later still must not move active duration.
    still_paused = six_hours_later + timedelta(seconds=30)
    root_still_paused = projector.snapshot(status="awaiting_user", ended_at=still_paused)[0]
    assert root_still_paused["activeDurationMs"] == active_at_pause

    resume_time = still_paused + timedelta(seconds=5)
    projector.consume_event("run.resumed", {}, agent="coordinator", timestamp=resume_time)
    completed_time = resume_time + timedelta(seconds=10)
    projector.consume_event("run.completed", {}, agent="coordinator", timestamp=completed_time)

    final = projector.snapshot(status="completed", ended_at=completed_time)[0]
    expected_waiting_ms = int((resume_time - pause_started).total_seconds() * 1000)
    assert final["waitingForUserMs"] == expected_waiting_ms
    assert final["activeDurationMs"] == active_at_pause + 10_000
    assert final["durationMs"] == final["activeDurationMs"]


def test_a_native_span_open_across_pause_and_resume_excludes_the_wait_from_its_own_duration() -> (
    None
):
    """A node-level span (e.g. ``await_user``) must not inherit the wait either.

    The root's ``activeDurationMs`` freezing alone is not enough: if a native
    node span is still ``running`` when ``run.paused`` fires and only reaches
    ``node.completed`` after ``run.resumed``, its own ``durationMs`` must also
    exclude the paused wall-clock interval, not just the root's.
    """

    started = datetime(2026, 1, 1, tzinfo=UTC)
    projector = ExecutionTimelineProjector(
        execution_id="exec-2",
        task_id="task-2",
        graph_version="test@1",
        resolve_primitive=_resolve_primitive,
        started_at=started,
    )

    projector.consume_event("run.started", {}, agent="coordinator", timestamp=started)

    # A native node span (the await_user primitive) starts, then the run
    # pauses while it is still open.
    node_started = started + timedelta(seconds=2)
    node_event = SimpleNamespace(
        kind=EventKind.NODE_STARTED,
        run_id="run-1",
        step=1,
        node="await_user",
        task_id="task-2",
        namespace=(),
        checkpoint_id=None,
        span_id="await-user-span",
        timestamp=node_started,
        data={},
    )
    projector.consume_native(node_event)

    pause_started = started + timedelta(seconds=5)
    projector.consume_event("run.paused", {}, agent="coordinator", timestamp=pause_started)

    # The learner sits on WAITING_FOR_USER for six hours.
    six_hours_later = pause_started + timedelta(hours=6)
    projector.snapshot(status="awaiting_user", ended_at=six_hours_later)

    resume_time = six_hours_later + timedelta(seconds=5)
    projector.consume_event("run.resumed", {}, agent="coordinator", timestamp=resume_time)

    # The still-open native span only finishes now, after resume.
    node_completed_time = resume_time + timedelta(seconds=3)
    node_completed_event = SimpleNamespace(
        kind=EventKind.NODE_COMPLETED,
        run_id="run-1",
        step=1,
        node="await_user",
        task_id="task-2",
        namespace=(),
        checkpoint_id=None,
        span_id="await-user-span",
        timestamp=node_completed_time,
        data={},
    )
    projector.consume_native(node_completed_event)

    completed_time = node_completed_time + timedelta(seconds=1)
    projector.consume_event("run.completed", {}, agent="coordinator", timestamp=completed_time)

    final = projector.snapshot(status="completed", ended_at=completed_time)[0]
    await_user_span = next(
        span for span in final["children"] if span.get("primitive") == "await_user"
    )
    # Real active time: (pause_started - node_started) + (node_completed_time - resume_time)
    # = 3s + 3s = 6s. The six-hour wait must not leak into this span's own duration.
    expected_active_ms = 3_000 + 3_000
    assert await_user_span["durationMs"] == expected_active_ms, (
        "a native span open across pause/resume must exclude the paused wall-clock gap"
    )
    assert await_user_span["durationMs"] < 60 * 60 * 1000
