"""Input boundary between application use-cases and the graph runtime.

Application services never drive the graph directly; they submit turn inputs
through this port.  The current implementation is
:class:`~lingxilearn.application.runtime_adapter.LingxiGraphRuntimeAdapter`.
A future steering runtime (#91) can replace or extend the adapter behind this
port without splitting the application services again.

Only capabilities that exist today are declared here — no speculative API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RuntimeInputPort(Protocol):
    """How application services submit work to the runtime."""

    @property
    def model_configured(self) -> bool:
        """Whether the runtime has a usable agent model configuration."""
        ...

    def start_turn(
        self,
        task_id: str,
        learner_id: str,
        prompt: str,
        *,
        schedule_id: str | None = None,
        scheduled_for: datetime | None = None,
        command_id: str | None = None,
        turn_id: str | None = None,
    ) -> None:
        """Queue a brand-new turn on a task thread (fire-and-forget)."""
        ...

    def resume_turn(
        self,
        task_id: str,
        learner_id: str,
        resume: dict[str, Any],
        *,
        command_id: str | None = None,
        turn_id: str | None = None,
    ) -> None:
        """Resume the paused checkpoint of the current turn (fire-and-forget)."""
        ...

    def enqueue_conversation_input(
        self, task_id: str, learner_id: str, item: dict[str, Any]
    ) -> None:
        """Queue a learner message for the conversation drainer to pick up."""
        ...

    async def submit_running_input(
        self, task_id: str, learner_id: str, item: dict[str, Any]
    ) -> None:
        """Submit input to the currently running turn without starting another turn."""
        ...

    def schedule_interaction_drain(self, task_id: str, learner_id: str) -> None:
        """Schedule a drain of answered-but-unresumed interactions."""
        ...

    async def cancel_run(self, task_id: str) -> None:
        """Cancel any in-flight runner for the task and wait for it."""
        ...

    async def recover_pending(self) -> None:
        """Replay durable queued work after a process restart."""
        ...
