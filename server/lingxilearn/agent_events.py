"""Canonical Agent Task event vocabulary.

The SSE stream is intentionally open for forward-compatible event kinds, but
all first-party producers must use this registry.  The frontend mirrors this
list and treats unknown values as generic visible events instead of dropping
them.
"""

from __future__ import annotations

from typing import Final

AGENT_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "task.started",
        "task.completed",
        "task.failed",
        "task.cancelled",
        "intent.started",
        "intent.completed",
        "agent.started",
        "agent.completed",
        "agent.failed",
        "reasoning.delta",
        "assistant.delta",
        "tool.call.delta",
        "tool.result",
        "model.started",
        "model.completed",
        "model.usage",
        "node.appeared",
        "node.started",
        "node.completed",
        "node.failed",
        "node.retrying",
        "node.cached",
        "interrupt.raised",
        "artifact.ready",
        "artifact.recovered",
        "sidecar.started",
        "sidecar.completed",
        "sidecar.failed",
        "schedule.proposed",
        "schedule.permission",
        "plan.created",
        "plan.replanned",
        "state.updated",
        "run.started",
        "run.resumed",
        "run.paused",
        "run.ended",
        "run.completed",
        "run.failed",
        "run.cancelled",
        "run.timed_out",
        "run.budget_exceeded",
    }
)

TERMINAL_AGENT_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "task.completed",
        "task.failed",
        "task.cancelled",
        "run.ended",
        "run.completed",
        "run.failed",
        "run.cancelled",
        "run.timed_out",
        "run.budget_exceeded",
    }
)

