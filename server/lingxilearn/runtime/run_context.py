"""Canonical execution identity for one provider attempt (issue #18).

The fact model is::

    AgentTask (thread) → AgentTurn → AgentExecution → AgentRun → SkillRun

Only the dispatcher creates these identities.  Providers receive a frozen
:class:`RunContext` through ``ProviderContext.run_context`` and never invent
their own execution ids, so refresh/replay/resume cannot change who ran what.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

AGENT_RUN_ID_PREFIX = "ar"
SKILL_RUN_ID_PREFIX = "sr"
INTERACTION_ID_PREFIX = "it"


def new_agent_run_id() -> str:
    return f"{AGENT_RUN_ID_PREFIX}_{uuid4().hex}"


def new_skill_run_id() -> str:
    return f"{SKILL_RUN_ID_PREFIX}_{uuid4().hex}"


def new_interaction_id() -> str:
    return f"{INTERACTION_ID_PREFIX}_{uuid4().hex}"


@dataclass(frozen=True, slots=True)
class RunContext:
    """The identity one provider attempt runs under.

    ``task_id`` is the LingxiGraph ``thread_id``; ``execution_id`` identifies
    one graph invocation; ``agent_run_id`` identifies one real execution actor
    inside that invocation (a WorkItem retry gets a fresh one).
    """

    task_id: str
    execution_id: str = ""
    turn_id: str = ""
    agent_run_id: str = ""
    parent_agent_run_id: str = ""
    """Set only on a delegated child run (issue #18 §14.3 delegation edges)."""
    skill_run_id: str = ""
    provider_id: str = ""
    capability: str = ""
    presentation_role: str = "supporting"
    stream_id: str = ""
    """Per-turn chat stream id, used to group assistant text."""

    def with_agent_run(
        self,
        agent_run_id: str,
        *,
        provider_id: str = "",
        capability: str = "",
        presentation_role: str = "",
    ) -> RunContext:
        return replace(
            self,
            agent_run_id=agent_run_id,
            provider_id=provider_id or self.provider_id,
            capability=capability or self.capability,
            presentation_role=presentation_role or self.presentation_role,
        )

    def with_skill_run(self, skill_run_id: str) -> RunContext:
        return replace(self, skill_run_id=skill_run_id)

    def delegate(
        self,
        *,
        provider_id: str,
        capability: str = "",
        presentation_role: str = "supporting",
    ) -> RunContext:
        """Identity for a child actor this run delegates real work to.

        The child is a first-class AgentRun with its own id whose
        ``parent_agent_run_id`` points back here, so the chat renders a nested
        AgentGroup and the runtime graph draws a delegation edge from the same
        fact (issue #18 §4.4/§14.3).
        """

        return replace(
            self,
            agent_run_id=new_agent_run_id(),
            parent_agent_run_id=self.agent_run_id,
            skill_run_id="",
            provider_id=provider_id,
            capability=capability or self.capability,
            presentation_role=presentation_role,
        )

    def identity_fields(self) -> dict[str, Any]:
        """The identity every emitted event must carry."""

        fields: dict[str, Any] = {
            "task_id": self.task_id,
            "execution_id": self.execution_id,
        }
        if self.turn_id:
            fields["turn_id"] = self.turn_id
        if self.agent_run_id:
            fields["agent_run_id"] = self.agent_run_id
        if self.skill_run_id:
            fields["skill_run_id"] = self.skill_run_id
        return fields


class RunContextRegistry:
    """Tracks the AgentRun currently bound to each provider-runtime proxy.

    The dispatcher stamps events with identity at emit time; this registry is
    how ``_ProviderRuntime`` finds the context without threading it through
    every provider signature.
    """

    def __init__(self) -> None:
        self._contexts: dict[int, RunContext] = {}

    def bind(self, key: Any, context: RunContext) -> None:
        self._contexts[id(key)] = context

    def unbind(self, key: Any) -> None:
        self._contexts.pop(id(key), None)

    def context_for(self, key: Any) -> RunContext | None:
        return self._contexts.get(id(key))


def presentation_role_for(
    *, capability: str, capability_info: Any, critical_path: bool = True
) -> str:
    """Decide how one AgentRun participates in the learner's turn.

    Primary: a turn-completing conversational capability (``dialog.answer``,
    ``dialog.converse``, ``teach.explain`` …) — the agent that may own the
    top-level ChatContent.  Supporting: everything else the learner should see
    working.  Background: real product work detached from the critical path
    (e.g. non-blocking heavy artifacts) — still visible in the execution graph,
    never a primary speaker.
    """

    try:
        if getattr(capability_info, "turn_complete", False):
            return "primary"
    except Exception:  # noqa: BLE001 - defensive; capability_info is a plain dataclass
        pass
    return "supporting" if critical_path else "background"


__all__ = [
    "INTERACTION_ID_PREFIX",
    "AGENT_RUN_ID_PREFIX",
    "RunContext",
    "RunContextRegistry",
    "SKILL_RUN_ID_PREFIX",
    "new_agent_run_id",
    "new_interaction_id",
    "new_skill_run_id",
    "presentation_role_for",
]
