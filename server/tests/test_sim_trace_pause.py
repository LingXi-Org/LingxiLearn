"""Sim Trace pause-duration semantics (issue #32 §3).

Waiting for the learner must never be attributed to Agent/Skill active
execution time: pausing for hours must not make the trace show hours of
active work, and the excluded interval must stay excluded after resume.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from lingxilearn.runtime.sim_trace import SimTraceProjector


def _resolve_primitive(name: str) -> SimpleNamespace:
    return SimpleNamespace(sim_type="agent", category="agent", idempotent=False, label=name)


def test_paused_duration_freezes_active_time_and_excludes_the_wait_after_resume() -> None:
    started = datetime(2026, 1, 1, tzinfo=UTC)
    projector = SimTraceProjector(
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
