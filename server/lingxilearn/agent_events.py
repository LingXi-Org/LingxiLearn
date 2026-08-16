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
        "agent.status",
        "agent.output",
        "agent.output.delta",
        "assistant.delta",
        # Canonical skill-run lifecycle emitted by the dispatcher (issue #18).
        "skill.started",
        "skill.completed",
        "skill.failed",
        # Internal adapters may observe these, but the persistence/SSE
        # boundary strips them before publication.
        "reasoning.delta",
        "tool.call.delta",
        "tool.result",
        "model.started",
        "model.completed",
        "model.failed",
        "model.usage",
        "node.appeared",
        "node.started",
        "node.completed",
        "node.held",
        "node.revising",
        "node.failed",
        "node.retrying",
        "node.cached",
        "interrupt.raised",
        # Structured HITL lifecycle (issue #18 §5.6).
        "interaction.requested",
        "interaction.resolved",
        "artifact.ready",
        "artifact.recovered",
        "delivery.queued",
        "delivery.unlocked",
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
