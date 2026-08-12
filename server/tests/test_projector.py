"""Event mapping, tested against fabricated events rather than a live run.

This is the payoff of keeping the projector a pure function: the mapping that
drives the whole UI is covered without a graph, a database or a socket — which
is exactly the coverage gap that let four mapping defects survive in the
reference implementation we studied.
"""

from __future__ import annotations

from lingxigraph import Event, EventKind

from lingxilearn.stream.projector import STREAM_CHANNEL, EventProjector, project_all


def make(kind: EventKind, *, seq: int, node: str = "coach", **data) -> Event:
    return Event(kind=kind, run_id="run-1", step=1, node=node, sequence=seq, data=data)


def test_domain_events_keep_their_own_names():
    event = make(
        EventKind.CUSTOM,
        seq=1,
        channel=STREAM_CHANNEL,
        value={"type": "coach.move", "move": {"say": "看第 8 帧"}},
    )
    (emission,) = EventProjector().project(event)
    assert emission.kind == "coach.move"
    assert emission.payload["move"]["say"] == "看第 8 帧"


def test_custom_events_on_other_channels_are_ignored():
    event = make(EventKind.CUSTOM, seq=1, channel="something-else", value={"type": "x"})
    assert EventProjector().project(event) == []


def test_node_completed_reads_the_update_key():
    """The runtime puts the state delta in data["update"], not data["state"]."""
    event = make(EventKind.NODE_COMPLETED, seq=2, update={"phase": "coach", "attempts": 2})
    (emission,) = EventProjector().project(event)
    assert emission.kind == "node.completed"
    assert emission.payload["state"]["phase"] == "coach"


def test_node_completed_summarises_bulky_state():
    event = make(EventKind.NODE_COMPLETED, seq=2, update={"evidence": [1, 2, 3], "phase": "judge"})
    (emission,) = EventProjector().project(event)
    assert emission.payload["state"]["evidence"] == "<3 items>"
    assert emission.payload["state"]["phase"] == "judge"


def test_node_retrying_reads_the_value_key():
    """The retry channel carries the attempt under data["value"]."""
    event = make(EventKind.NODE_RETRYING, seq=3, channel="__retry__", value=2)
    (emission,) = EventProjector().project(event)
    assert emission.kind == "node.retrying"
    assert emission.payload["attempt"] == 2


def test_terminal_failures_are_distinguished():
    kinds = {
        EventKind.RUN_FAILED: "failed",
        EventKind.RUN_CANCELLED: "cancelled",
        EventKind.RUN_TIMED_OUT: "timed_out",
        EventKind.RUN_BUDGET_EXCEEDED: "budget_exceeded",
    }
    for index, (kind, expected) in enumerate(kinds.items(), start=1):
        (emission,) = EventProjector().project(make(kind, seq=index))
        assert emission.kind == "run.failed"
        assert emission.payload["status"] == expected


def test_interrupt_is_projected():
    event = make(EventKind.INTERRUPT_RAISED, seq=4, interrupts=[{"value": {"kind": "probe"}}])
    (emission,) = EventProjector().project(event)
    assert emission.kind == "interrupt.raised"
    assert emission.payload["interrupts"][0]["value"]["kind"] == "probe"


def test_replayed_events_are_deduplicated():
    projector = EventProjector()
    event = make(EventKind.NODE_STARTED, seq=9)
    assert projector.project(event)
    assert projector.project(event) == []  # same (run_id, sequence)


def test_keys_are_namespace_aware():
    """Subgraph nodes must not collide with parent nodes in the UI."""
    parent = Event(
        kind=EventKind.NODE_STARTED, run_id="r", step=1, node="coach", sequence=1, data={}
    )
    child = Event(
        kind=EventKind.NODE_STARTED,
        run_id="r",
        step=1,
        node="coach",
        sequence=2,
        namespace=("team",),
        data={},
    )
    keys = {e.key for e in project_all([parent, child])}
    assert len(keys) == 2


def test_unhandled_kinds_project_to_nothing():
    # NODE_FAILED is declared in the enum but never emitted by the runtime;
    # handling it would be dead code, so it must project to nothing.
    assert EventProjector().project(make(EventKind.NODE_FAILED, seq=1)) == []
    assert EventProjector().project(make(EventKind.CHECKPOINT_SAVED, seq=2)) == []


def test_a_whole_run_projects_in_order():
    events = [
        make(EventKind.RUN_STARTED, seq=1),
        make(EventKind.NODE_STARTED, seq=2, node="investigate"),
        make(
            EventKind.CUSTOM,
            seq=3,
            channel=STREAM_CHANNEL,
            value={"type": "tool.completed", "tool": "course.tool", "ok": True},
        ),
        make(EventKind.NODE_COMPLETED, seq=4, node="investigate", update={"phase": "coach"}),
        make(EventKind.RUN_COMPLETED, seq=5),
    ]
    kinds = [e.kind for e in project_all(events)]
    assert kinds == [
        "run.started",
        "node.started",
        "tool.completed",
        "node.completed",
        "run.ended",
    ]
