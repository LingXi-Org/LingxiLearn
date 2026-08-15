"""Execute a planned task by resolving its capability at run time.

This is the only place the runtime turns an intention into a call, and it is
where the old fixed topology used to live.  The resolution chain is
``capability tag → skill_registry row → provider name → registered callable``,
computed fresh for each task.  Nothing here consults what the learner said or
what ran last time.

Running a provider is not the end of the task: ``done_when`` is evaluated
afterwards, and a provider that returned without producing the intended change
leaves the task unsatisfied so the loop replans.
"""

from __future__ import annotations

import logging
import asyncio
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..agents.providers import ProviderContext, ProviderError, ProviderResult
from ..agents.providers import get as get_provider
from ..agents.providers import load_all as load_providers
from ..state.evidence import EvidenceRecord
from ..state.session_state import Goal
from ..store.runtime_state import RuntimeStateRepository
from .completion import CompletionContext, StoreArtifactProbe, evaluate
from .contracts import PlannedTask, TaskOutcome
from .guardrails import Budget

logger = logging.getLogger(__name__)


class NoProvider(LookupError):
    """No enabled skill provides the capability the plan asked for."""


@dataclass(slots=True)
class Resolution:
    """Which skill and provider will serve one capability, decided just now."""

    capability: str
    skill_id: str
    provider: str
    cost: dict[str, Any] = field(default_factory=dict)
    status_line: str = ""


def resolve(capability: str, skills: Sequence[Mapping[str, Any]]) -> Resolution:
    """Pick the cheapest enabled skill that provides ``capability``.

    Ties break on skill id so the same state always resolves the same way; a
    resolution that varies run to run would make the trace unreproducible.
    """

    matches = [
        row
        for row in skills
        if row.get("enabled", True)
        and row.get("provider")
        and capability in (row.get("capabilities") or ())
    ]
    if not matches:
        raise NoProvider(f"no enabled skill provides {capability}")
    matches.sort(
        key=lambda row: (
            float((row.get("cost") or {}).get("latency_weight") or 1.0),
            str(row.get("skill_id")),
        )
    )
    chosen = matches[0]
    return Resolution(
        capability=capability,
        skill_id=str(chosen["skill_id"]),
        provider=str(chosen["provider"]),
        cost=dict(chosen.get("cost") or {}),
        status_line=str((chosen.get("metadata") or {}).get("status_line") or "正在处理这一步…"),
    )


@dataclass(slots=True)
class DispatchDeps:
    """Everything dispatch needs that is not part of the plan."""

    runtime_state: RuntimeStateRepository
    learner_id: str
    task_id: str
    goal: Goal
    skills: Sequence[Mapping[str, Any]]
    model: Any = None
    settings: Any = None
    artifacts: Any = None
    registry: Any = None
    pack: Any = None
    graph_runtime: Any = None
    user_message: Mapping[str, Any] = field(default_factory=dict)
    shared_skills: tuple[str, ...] = ()
    emit: Any = None


class Dispatcher:
    """Runs planned tasks and reports whether they actually finished."""

    def __init__(self, deps: DispatchDeps) -> None:
        self._deps = deps
        self._results: dict[str, Any] = {}
        self._validations: dict[str, bool] = {}
        self._artifacts: set[str] = set()
        self._state_lock = asyncio.Lock()
        load_providers()

    @property
    def produced_artifacts(self) -> frozenset[str]:
        return frozenset(self._artifacts)

    @property
    def results(self) -> Mapping[str, Any]:
        """Provider outputs so far, keyed by ``persist_as``."""

        return dict(self._results)

    def retarget(
        self,
        *,
        goal: Goal | None = None,
        skills: Sequence[Mapping[str, Any]] | None = None,
        user_message: Mapping[str, Any] | None = None,
    ) -> None:
        """Point the dispatcher at the current goal, registry view and reply.

        The loop reuses one dispatcher across rounds so provider results
        accumulate, but each round may work on a different goal and a freshly
        read registry.
        """

        if goal is not None:
            self._deps.goal = goal
        if skills is not None:
            self._deps.skills = list(skills)
        if user_message is not None:
            self._deps.user_message = dict(user_message)

    def bind_runtime(self, runtime: Any, *, emit: Any = None) -> None:
        """Attach the live graph runtime for provider-side streaming events."""

        self._deps.graph_runtime = runtime
        if emit is not None:
            self._deps.emit = emit

    def seed_results(self, results: Mapping[str, Any]) -> None:
        """Prime with results persisted by earlier rounds of the same task."""

        self._results.update(results)

    def seed_artifacts(self, artifacts: Sequence[str]) -> None:
        self._artifacts.update(str(item) for item in artifacts)

    async def run(
        self,
        task: PlannedTask,
        *,
        profile: Mapping[str, Mapping[str, Any]],
        budget: Budget,
    ) -> TaskOutcome:
        """Execute one task, then check whether it is actually done."""

        started = time.monotonic()
        try:
            resolution = resolve(task.capability, self._deps.skills)
        except NoProvider as exc:
            if self._deps.emit is not None:
                self._deps.emit("agent.status", {"task_id": task.id, "capability": task.capability, "text": "这一步没有可用的执行者，我换个方式。"})
            return TaskOutcome(
                task_id=task.id,
                capability=task.capability,
                status="blocked",
                detail=str(exc),
            )

        if self._deps.emit is not None:
            self._deps.emit(
                "node.started",
                {
                    "task_id": task.id,
                    "capability": task.capability,
                    "provider": resolution.provider,
                    "skill_id": resolution.skill_id,
                },
            )
            self._deps.emit(
                "agent.status",
                {
                    "task_id": task.id,
                    "capability": task.capability,
                    "provider": resolution.provider,
                    "skill_id": resolution.skill_id,
                    "text": resolution.status_line,
                },
            )

        provider = get_provider(resolution.provider)
        if provider is None:
            if self._deps.emit is not None:
                self._deps.emit("agent.status", {"task_id": task.id, "capability": task.capability, "text": "这一步没有可用的执行者，我换个方式。"})
            return TaskOutcome(
                task_id=task.id,
                capability=task.capability,
                skill_id=resolution.skill_id,
                provider=resolution.provider,
                status="blocked",
                detail=f"provider is not implemented: {resolution.provider}",
            )

        context = ProviderContext(
            goal=self._deps.goal,
            task=task,
            learner_id=self._deps.learner_id,
            task_id=self._deps.task_id,
            model=self._deps.model,
            settings=self._deps.settings,
            artifacts=self._deps.artifacts,
            runtime=self._deps.graph_runtime,
            profile=profile,
            prior_results=dict(self._results),
            user_message=dict(self._deps.user_message),
            skill_id=resolution.skill_id,
            shared_skills=self._deps.shared_skills,
            registry=self._deps.registry,
            pack=self._deps.pack,
        )

        try:
            result = await provider(context)
        except ProviderError as exc:
            logger.info("provider %s declined: %s", resolution.provider, exc)
            return self._failed(task, resolution, str(exc), started)
        except Exception as exc:  # noqa: BLE001 - one provider must not end the run
            logger.exception("provider %s failed", resolution.provider)
            return self._failed(task, resolution, f"{type(exc).__name__}: {exc}", started)

        evidence_ids = await self._persist(result)
        satisfied, detail = await self._check_done(task, result, evidence_ids)
        return TaskOutcome(
            task_id=task.id,
            capability=task.capability,
            provider=resolution.provider,
            skill_id=resolution.skill_id,
            status=result.status if satisfied else "incomplete",
            satisfied=satisfied,
            detail=detail or result.detail,
            evidence_ids=evidence_ids,
            artifacts=list(result.artifacts),
            learner_message=result.learner_message,
            tokens_used=result.tokens_used,
            duration_ms=int((time.monotonic() - started) * 1000),
            heavy=bool(task.estimated_cost.heavy_artifact),
        )

    # -- internals -----------------------------------------------------------

    def _failed(
        self, task: PlannedTask, resolution: Resolution, detail: str, started: float
    ) -> TaskOutcome:
        if self._deps.emit is not None:
            self._deps.emit("agent.status", {"task_id": task.id, "capability": task.capability, "text": "这一步遇到问题，我会保留已完成的部分。"})
        return TaskOutcome(
            task_id=task.id,
            capability=task.capability,
            provider=resolution.provider,
            skill_id=resolution.skill_id,
            status="failed",
            satisfied=False,
            detail=detail,
            duration_ms=int((time.monotonic() - started) * 1000),
            heavy=bool(task.estimated_cost.heavy_artifact),
        )

    async def _persist(self, result: ProviderResult) -> list[str]:
        """Append the provider's evidence and remember its outputs."""

        async with self._state_lock:
            if result.persist_as:
                self._results[result.persist_as] = dict(result.data)
            self._artifacts.update(result.artifacts)
            self._validations.update(result.validations)

        records: list[EvidenceRecord] = list(result.evidence)
        if not records:
            return []
        appended = await self._deps.runtime_state.append_evidence(records)
        return [str(row.get("evidence_id") or "") for row in appended]

    async def _check_done(
        self, task: PlannedTask, result: ProviderResult, evidence_ids: Sequence[str]
    ) -> tuple[bool, str]:
        """Evaluate ``done_when`` against what is true now.

        This is the line between "the provider returned" and "the task is
        finished". Everything the predicate reads is state, not the provider's
        own claim of success.
        """

        evidence = await self._deps.runtime_state.evidence_for_task(self._deps.task_id)
        fresh = [row for row in evidence if str(row.get("evidence_id")) in set(evidence_ids)]
        profile_rows = {
            row["knowledge_point_id"]: row
            for row in await self._deps.runtime_state.profile_for(self._deps.learner_id)
        }
        probe = (
            StoreArtifactProbe(
                self._deps.artifacts, self._deps.task_id, validations=self._validations
            )
            if self._deps.artifacts is not None
            else None
        )
        verdict = evaluate(
            task.done_when,
            CompletionContext(
                artifacts=probe,
                evidence=fresh,
                profile=profile_rows,
                user_replied=bool(self._deps.user_message.get("message")),
                quiz_graded="grading" in self._results,
            ),
        )
        return verdict.satisfied, verdict.detail


__all__ = ["DispatchDeps", "Dispatcher", "NoProvider", "Resolution", "resolve"]
