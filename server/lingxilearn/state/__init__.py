"""The state layer: the four tables that are the system's only source of truth.

Agents communicate through these tables and nowhere else — no agent hands
another agent a paragraph of natural language.

* ``learning_profile`` — one row per learner × knowledge point. Everyone reads
  it; only :mod:`.profile_writer` writes it.
* ``learning_evidence`` — append-only structured observations. The only thing an
  agent may produce about a learner (:mod:`.evidence`).
* ``session_state`` — goal stack plus run state machine (:mod:`.session_state`).
* ``skill_registry`` — capability tags, IO contracts, preconditions and cost
  (:mod:`.skill_catalog`).
"""

from __future__ import annotations

from .capabilities import Capability, CapabilityInfo, UnknownCapability, info, parse
from .evidence import EvidenceRecord, InvalidEvidence, Signal
from .gain import GainEstimate, ProfileView, estimate
from .profile_writer import (
    ProfileChange,
    ProfileDelta,
    ProfileWriter,
    UnsourcedProfileWrite,
    profile_id,
)
from .session_state import (
    DEFAULT_BUDGET,
    Goal,
    GoalKind,
    GoalStack,
    GoalStatus,
    IllegalTransition,
    RuntimeStatus,
    StackOperation,
    new_budget,
    transition,
)

__all__ = [
    "DEFAULT_BUDGET",
    "Capability",
    "CapabilityInfo",
    "EvidenceRecord",
    "GainEstimate",
    "Goal",
    "GoalKind",
    "GoalStack",
    "GoalStatus",
    "IllegalTransition",
    "InvalidEvidence",
    "ProfileChange",
    "ProfileDelta",
    "ProfileView",
    "ProfileWriter",
    "RuntimeStatus",
    "Signal",
    "StackOperation",
    "UnknownCapability",
    "UnsourcedProfileWrite",
    "estimate",
    "info",
    "new_budget",
    "parse",
    "profile_id",
    "transition",
]
