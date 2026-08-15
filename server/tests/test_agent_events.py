from lingxilearn.agent_events import AGENT_EVENT_KINDS, TERMINAL_AGENT_EVENT_KINDS


def test_agent_event_vocabulary_contains_runtime_lifecycle() -> None:
    required = {
        "task.started",
        "task.completed",
        "task.failed",
        "task.cancelled",
        "run.started",
        "run.resumed",
        "run.paused",
        "run.ended",
        "run.timed_out",
        "run.budget_exceeded",
        "plan.created",
        "plan.replanned",
        "node.appeared",
        "node.retrying",
    }
    assert required <= AGENT_EVENT_KINDS
    assert TERMINAL_AGENT_EVENT_KINDS <= AGENT_EVENT_KINDS

