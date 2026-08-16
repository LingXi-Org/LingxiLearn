"""Capability providers: the executable side of the capability vocabulary.

The orchestrator plans in capability tags. ``skill_registry`` maps a tag to a
skill and a provider name. This package maps the name to the code. No module
here decides *when* it runs — that is recomputed each round from the learner's
state.
"""

from __future__ import annotations

from .base import (
    AgentDescriptor,
    Provider,
    ProviderContext,
    ProviderError,
    ProviderResult,
    descriptor,
    descriptors,
    get,
    load_all,
    missing_providers,
    names,
    register,
)

__all__ = [
    "AgentDescriptor",
    "Provider",
    "ProviderContext",
    "ProviderError",
    "ProviderResult",
    "descriptor",
    "descriptors",
    "get",
    "load_all",
    "missing_providers",
    "names",
    "register",
]
