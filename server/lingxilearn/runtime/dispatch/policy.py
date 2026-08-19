"""The single owner of dispatch outcome policy.

One WorkItem attempt ends in exactly one way — blocked, failed, incomplete,
or completed (optionally held for delivery) — and this module is the only
place that decides which.  The scheduler never re-derives a ledger status and
the runner never invents a retry condition: they report facts, and the policy
maps those facts to a :class:`TaskOutcome` plus the ledger status and error
code the attempt is recorded under.

Retry identity rule (issue #18): a retry is a *new* WorkItem attempt executed
under a fresh AgentRun/SkillRun.  Nothing here mutates a previous attempt's
recorded outcome; each decision builds the outcome of the attempt that just
ran, so WorkItem logical identity and per-attempt run identity never blur.

No cache decision exists in the live dispatch path today (``node.cached``
belongs to the simulation vocabulary).  If one is added, it is added here —
never inside the scheduler or the runner.
"""

from __future__ import annotations

from ...agents.providers import ProviderError, ProviderResult
from ..contracts import PlannedTask, TaskOutcome
from .binding import NoProvider, Resolution

NO_PROVIDER = "no_provider"
"""The capability has no enabled skill/provider to bind to."""

PROVIDER_MISSING = "provider_missing"
"""The bound provider is not implemented (registry shrank after binding)."""

PROVIDER_ERROR = "provider_error"
"""The provider declined the work with a declared error."""

PROVIDER_FAILED = "provider_failed"
"""The provider crashed with an unexpected exception."""


def error_code_for(exc: BaseException) -> str:
    """The ledger error code for one failed attempt — the only mapping."""

    if isinstance(exc, NoProvider):
        return NO_PROVIDER
    if isinstance(exc, ProviderError):
        return PROVIDER_ERROR
    return PROVIDER_FAILED


def ledger_status_for(*, satisfied: bool) -> str:
    """The WorkItem terminal status for an attempt that ran to completion."""

    return "succeeded" if satisfied else "incomplete"


def is_held(result: ProviderResult, *, satisfied: bool) -> bool:
    """A satisfied task that produced artifacts waits for learner delivery."""

    return bool(result.artifacts) and satisfied


def blocked_outcome(
    task: PlannedTask,
    *,
    node_id: str,
    detail: str,
    resolution: Resolution | None = None,
) -> TaskOutcome:
    """The attempt could not start: unclaimable work or no executable binding."""

    return TaskOutcome(
        task_id=task.id,
        capability=task.capability,
        node_id=node_id,
        provider=resolution.provider if resolution is not None else "",
        skill_id=resolution.skill_id if resolution is not None else "",
        status="blocked",
        detail=detail,
    )


def failure_outcome(
    task: PlannedTask,
    resolution: Resolution,
    *,
    detail: str,
    node_id: str,
    duration_ms: int,
) -> TaskOutcome:
    """The attempt ran and failed; the WorkItem records a failed status."""

    return TaskOutcome(
        task_id=task.id,
        capability=task.capability,
        node_id=node_id,
        provider=resolution.provider,
        skill_id=resolution.skill_id,
        status="failed",
        satisfied=False,
        detail=detail,
        duration_ms=duration_ms,
        heavy=bool(task.estimated_cost.heavy_artifact),
    )


def success_outcome(
    task: PlannedTask,
    resolution: Resolution,
    result: ProviderResult,
    *,
    node_id: str,
    satisfied: bool,
    detail: str,
    evidence_ids: list[str],
    duration_ms: int,
    held: bool,
) -> TaskOutcome:
    """The attempt ran to completion; ``done_when`` decides the final word."""

    return TaskOutcome(
        task_id=task.id,
        capability=task.capability,
        node_id=node_id,
        provider=resolution.provider,
        skill_id=resolution.skill_id,
        status="completed" if satisfied else "incomplete",
        satisfied=satisfied,
        detail=detail or result.detail,
        evidence_ids=evidence_ids,
        artifacts=list(result.artifacts),
        learner_message=result.learner_message,
        tokens_used=result.tokens_used,
        duration_ms=duration_ms,
        heavy=bool(task.estimated_cost.heavy_artifact),
        held=held,
        revision=int((task.inputs.get("revision") or {}).get("number") or 0),
    )


__all__ = [
    "NO_PROVIDER",
    "PROVIDER_ERROR",
    "PROVIDER_FAILED",
    "PROVIDER_MISSING",
    "blocked_outcome",
    "error_code_for",
    "failure_outcome",
    "is_held",
    "ledger_status_for",
    "success_outcome",
]
