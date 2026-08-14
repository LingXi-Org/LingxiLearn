"""What a capability provider is, and how one is found.

A provider is the executable side of a capability.  The orchestrator plans in
capability tags; ``skill_registry`` says which skill provides a tag and which
provider name runs that skill; this module turns the name into a callable.

That last hop is a plugin table — provider *name* to *implementation* — and it
is the only name-keyed lookup in the runtime.  It is not intent routing: nothing
here consults what the learner said, what workflow to run, or what should happen
next.  Providers are interchangeable behind their capability, which is what lets
the difference between two agents be the skills they load rather than a branch
in the coordinator.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ...runtime.contracts import PlannedTask
from ...state.evidence import EvidenceRecord
from ...state.session_state import Goal
from ..artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    """A provider could not produce its result. The loop degrades, not crashes."""


@dataclass(slots=True)
class ProviderContext:
    """Everything a provider may read, and the only channels it may write to.

    Note what is absent: no database session and no profile writer.  A provider
    reads the profile and emits evidence; it cannot change what the system
    believes about a learner, because that authority belongs to state_updater.
    """

    goal: Goal
    task: PlannedTask
    learner_id: str
    task_id: str
    model: Any | None = None
    settings: Any = None
    artifacts: ArtifactStore | None = None
    runtime: Any = None
    profile: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    """Current profile rows keyed by knowledge_point_id — read-only."""
    prior_results: Mapping[str, Any] = field(default_factory=dict)
    """Results other providers persisted for this task, keyed by provider name."""
    user_message: Mapping[str, Any] = field(default_factory=dict)
    skill_id: str = ""
    shared_skills: tuple[str, ...] = ()
    """Cross-cutting skills composed into this provider for the turn."""
    registry: Any = None
    """Tool registry, for providers that run deterministic course-pack tools."""
    pack: Any = None

    @property
    def knowledge_point_id(self) -> str:
        return self.task.knowledge_point_id or (
            self.goal.knowledge_points[0] if self.goal.knowledge_points else ""
        )

    def profile_of(self, knowledge_point_id: str = "") -> Mapping[str, Any]:
        return self.profile.get(knowledge_point_id or self.knowledge_point_id, {})

    def result_of(self, provider: str) -> Mapping[str, Any]:
        value = self.prior_results.get(provider)
        return value if isinstance(value, Mapping) else {}


@dataclass(slots=True)
class ProviderResult:
    """What a provider produced. Whether that *completes* the task is decided
    by :mod:`lingxilearn.runtime.completion`, not here."""

    status: str = "completed"
    learner_message: str = ""
    """Text to show the learner, if this provider is learner-facing."""
    evidence: list[EvidenceRecord] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    validations: dict[str, bool] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    persist_as: str = ""
    """Key under which ``data`` is stored on the task, for later providers."""
    detail: str = ""
    tokens_used: int = 0
    warnings: list[str] = field(default_factory=list)


Provider = Callable[[ProviderContext], Awaitable[ProviderResult]]

_PROVIDERS: dict[str, Provider] = {}


def register(name: str) -> Callable[[Provider], Provider]:
    """Register a provider implementation under the name skills refer to."""

    def decorate(func: Provider) -> Provider:
        if name in _PROVIDERS:
            raise ValueError(f"provider already registered: {name}")
        _PROVIDERS[name] = func
        return func

    return decorate


def get(name: str) -> Provider | None:
    return _PROVIDERS.get(name)


def names() -> tuple[str, ...]:
    return tuple(sorted(_PROVIDERS))


def load_all() -> dict[str, Provider]:
    """Import the provider modules so their registrations run."""

    from . import (  # noqa: F401  (import side effect: registration)
        assessment,
        content,
        knowledge,
        meta,
        pack,
        teaching,
    )

    return dict(_PROVIDERS)


def missing_providers(skills: Sequence[Mapping[str, Any]]) -> list[str]:
    """Registry rows naming a provider that does not exist.

    Called at startup: a skill pointing at a provider nobody implements is a
    capability the orchestrator would plan for and then fail to run.
    """

    load_all()
    gaps: list[str] = []
    for row in skills:
        provider = str(row.get("provider") or "")
        if provider and provider not in _PROVIDERS:
            gaps.append(f"{row.get('skill_id')}→{provider}")
    return sorted(gaps)


__all__ = [
    "Provider",
    "ProviderContext",
    "ProviderError",
    "ProviderResult",
    "get",
    "load_all",
    "missing_providers",
    "names",
    "register",
]
