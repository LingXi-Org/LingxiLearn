"""Execute a planned task by resolving its capability at run time.

This module is the *composition* of the dispatch pipeline — one planned task
flows through five focused owners::

    WorkScheduler (claim/lease)         — runtime/dispatch/scheduler.py
      → binding.resolve (capability → skill → provider) — …/binding.py
      → ExecutionRunner (AgentRun/SkillRun, provider)   — …/runner.py
      → policy (blocked/failed/held/success outcome)    — …/policy.py
      → DispatchProjector (canonical runtime events)    — …/projection.py

The resolution chain is ``capability tag → skill_registry row → provider name
→ registered callable``, computed fresh for each task.  Nothing here consults
what the learner said or what ran last time.

Running a provider is not the end of the task: ``done_when`` is evaluated
afterwards, and a provider that returned without producing the intended change
leaves the task unsatisfied so the loop replans.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ...agents.providers import ProviderError, ProviderResult
from ...agents.providers import get as get_provider
from ...agents.providers import load_all as load_providers
from ...state.evidence import EvidenceRecord
from ...state.session_state import Goal
from ...store.runtime_state import RuntimeStateRepository
from ..completion import CompletionContext, StoreArtifactProbe, evaluate
from ..contracts import PlannedTask, TaskOutcome
from ..guardrails import Budget
from ..run_context import RunContext
from . import policy
from .binding import NoProvider, resolve
from .projection import DispatchProjector
from .runner import ExecutionRunner
from .scheduler import WorkScheduler


@dataclass(slots=True)
class DispatchDeps:
    """Everything dispatch needs that is not part of the plan."""

    runtime_state: RuntimeStateRepository
    learner_id: str
    task_id: str
    goal: Goal
    skills: Sequence[Mapping[str, Any]]
    work_ledger: Any = None
    runtime_repository: Any = None
    model: Any = None
    settings: Any = None
    artifacts: Any = None
    registry: Any = None
    pack: Any = None
    graph_runtime: Any = None
    user_message: Mapping[str, Any] = field(default_factory=dict)
    shared_skills: tuple[str, ...] = ()
    emit: Any = None
    execution_id: str = ""
    """Canonical execution identity host; empty in standalone unit runs."""
    turn_id: str = ""


class Dispatcher:
    """Runs planned tasks and reports whether they actually finished."""

    def __init__(self, deps: DispatchDeps) -> None:
        self._deps = deps
        self._projector = DispatchProjector(lambda: self._deps.emit)
        self._scheduler = WorkScheduler(deps)
        self._runner = ExecutionRunner(deps, self._projector, owner=self)
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
            if not self._deps.user_message and goal.raw_utterance:
                # Initial prompts live on the goal rather than in an
                # interjection.  Conversational providers still need the
                # original learner text in their context.
                self._deps.user_message = {"message": goal.raw_utterance}
        if skills is not None:
            self._deps.skills = list(skills)
        if user_message is not None:
            self._deps.user_message = dict(user_message)

    def bind_runtime(self, runtime: Any, *, emit: Any = None) -> None:
        """Attach the live graph runtime for provider-side streaming events."""

        self._deps.graph_runtime = runtime
        if emit is not None:
            self._deps.emit = emit

    def bind_turn(self, turn_id: str) -> None:
        """Attach the canonical turn identity for AgentRun attribution."""

        if turn_id:
            self._deps.turn_id = turn_id

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
        work_id = str(task.inputs.get("__work_item_id") or "")
        node_id = str(
            task.inputs.get("__runtime_node_id")
            or work_id
            or f"{self._deps.task_id}:{task.inputs.get('__runtime_step') or 0}:{task.id}"
        )

        # -- schedule: claim the WorkItem and hold its lease ----------------
        claimed: dict[str, Any] | None = None
        scheduler = self._scheduler
        if scheduler.tracks(work_id):
            claimed = await scheduler.claim(work_id)
            if claimed is None:
                return policy.blocked_outcome(
                    task,
                    node_id=node_id,
                    detail="work item is not claimable or its dependencies have not succeeded",
                )
            self._projector.work_claimed(
                task,
                work_id=work_id,
                node_id=node_id,
                attempt=int(claimed.get("attempts") or claimed.get("attempt") or 1),
                turn_id=claimed.get("turn_id"),
            )
        heartbeat = (
            scheduler.start_heartbeat(work_id)
            if claimed is not None
            else None
        )

        # -- bind: capability → skill → provider (pure resolution) ----------
        try:
            resolution = resolve(
                task.capability,
                self._deps.skills,
                selected_candidate_id=task.candidate_id,
                knowledge_point_id=task.knowledge_point_id,
                provider_available=self._provider_available,
            )
        except NoProvider as exc:
            await scheduler.stop_heartbeat(heartbeat)
            if claimed is not None:
                await scheduler.finish(
                    work_id,
                    status="failed",
                    result={"safe_summary": str(exc), "error_code": policy.error_code_for(exc)},
                )
            self._projector.no_executor(task, node_id=node_id)
            return policy.blocked_outcome(task, node_id=node_id, detail=str(exc))

        # -- execute: one attempt = one fresh AgentRun/SkillRun identity ----
        prepared = await self._runner.begin(
            task,
            resolution=resolution,
            node_id=node_id,
            work_id=work_id,
            emit_node_events=True,
        )

        provider = get_provider(resolution.provider)
        if provider is None:
            # Binding filtered on availability, so this is the residual race:
            # the registry shrank between resolve() and this lookup.
            await scheduler.stop_heartbeat(heartbeat)
            if claimed is not None:
                await scheduler.finish(
                    work_id,
                    status="failed",
                    result={
                        "safe_summary": "provider is not implemented",
                        "error_code": policy.PROVIDER_MISSING,
                    },
                )
            self._projector.no_executor(task, node_id=node_id)
            await self._runner.finish_identity(
                prepared.run_context.agent_run_id,
                prepared.skill_run_id,
                agent_status="failed",
                skill_status="failed",
            )
            return policy.blocked_outcome(
                task,
                node_id=node_id,
                detail=f"provider is not implemented: {resolution.provider}",
                resolution=resolution,
            )

        try:
            result = await self._runner.invoke(
                provider,
                task,
                prepared,
                profile=profile,
                prior_results=dict(self._results),
            )
        except asyncio.CancelledError:
            raise
        except ProviderError as exc:
            if claimed is not None:
                await scheduler.finish(
                    work_id,
                    status="failed",
                    result={"safe_summary": str(exc), "error_code": policy.error_code_for(exc)},
                )
            self._projector.failure_notice(task, node_id=node_id)
            return policy.failure_outcome(
                task,
                resolution,
                detail=str(exc),
                node_id=node_id,
                duration_ms=self._elapsed_ms(started),
            )
        except Exception as exc:  # noqa: BLE001 - one provider must not end the run
            if claimed is not None:
                await scheduler.finish(
                    work_id,
                    status="failed",
                    result={
                        "safe_summary": f"{type(exc).__name__}: {exc}",
                        "error_code": policy.error_code_for(exc),
                    },
                )
            self._projector.failure_notice(task, node_id=node_id)
            return policy.failure_outcome(
                task,
                resolution,
                detail=f"{type(exc).__name__}: {exc}",
                node_id=node_id,
                duration_ms=self._elapsed_ms(started),
            )
        finally:
            await scheduler.stop_heartbeat(heartbeat)

        # -- apply policy: persist, evaluate done_when, settle the attempt --
        evidence_ids = await self._persist(result)
        satisfied, detail = await self._check_done(task, result, evidence_ids)
        duration_ms = self._elapsed_ms(started)
        if claimed is not None:
            await scheduler.finish(
                work_id,
                status=policy.ledger_status_for(satisfied=satisfied),
                result={
                    "schema_id": str(getattr(result, "schema_id", "")),
                    "safe_summary": result.detail,
                    "artifact_refs": list(result.artifacts),
                    "evidence_refs": list(evidence_ids),
                    "usage": {
                        "tokens": result.tokens_used,
                        "wall_ms": duration_ms,
                        "heavy": 1 if result.artifacts else 0,
                    },
                    "output_payload": {},
                },
            )
            await scheduler.record_fact_snapshot(
                claimed=claimed,
                task=task,
                work_id=work_id,
                satisfied=satisfied,
                result=result,
                evidence_ids=evidence_ids,
            )
        held = policy.is_held(result, satisfied=satisfied)
        if held:
            self._projector.node_held(task, node_id=node_id, resolution=resolution)
        return policy.success_outcome(
            task,
            resolution,
            result,
            node_id=node_id,
            satisfied=satisfied,
            detail=detail,
            evidence_ids=evidence_ids,
            duration_ms=duration_ms,
            held=held,
        )

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.monotonic() - started) * 1000)

    @staticmethod
    def _provider_available(name: str) -> bool:
        """The pure availability predicate injected into binding resolution."""

        return get_provider(name) is not None

    # -- delegation (issue #18 §4.4) ----------------------------------------

    async def run_child(
        self,
        *,
        parent: RunContext,
        capability: str,
        task: PlannedTask,
        profile: Mapping[str, Mapping[str, Any]],
    ) -> ProviderResult:
        """Execute a delegated capability through the dispatcher's resolution.

        Delegation delegates *a capability*, not a provider implementation: it
        runs the same ``capability → enabled skill → provider`` resolution as
        any other unit of work, so the child is bound to a real registry row
        (version/checksum included) and cannot reach a disabled or unregistered
        skill.

        What it deliberately does **not** re-run is the orchestration plane:
        candidate generation, precondition/eligibility gating and the Work
        Ledger entry belong to the parent's planned task, whose lease, budget
        and ``done_when`` the child shares.  A child therefore inherits the
        parent's eligibility rather than proving its own — acceptable while
        delegation is provider-initiated inside one planned task, and the thing
        to revisit before any capability is delegated across guardrail
        boundaries (issue #18 §4.4).
        """

        resolution = resolve(
            capability,
            self._deps.skills,
            knowledge_point_id=task.knowledge_point_id,
        )
        provider = get_provider(resolution.provider)
        if provider is None:
            raise ProviderError(f"provider is not implemented: {resolution.provider}")
        # A Pydantic model: copy rather than dataclasses.replace, and carry the
        # delegated capability so the child's AgentRun/graph node reports what
        # it actually ran — never the parent's capability.
        child_task = (
            task
            if task.capability == capability
            else task.model_copy(update={"capability": capability})
        )
        prepared = await self._runner.begin(
            child_task, resolution=resolution, node_id=f"{task.id}:{capability}", parent=parent
        )
        result = await self._runner.invoke(
            provider,
            child_task,
            prepared,
            profile=profile,
            prior_results=dict(self._results),
        )
        await self._persist(result)
        return result

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
                provider_result=str(result.status or "completed").casefold()
                in {"completed", "success", "succeeded", "ok"},
            ),
        )
        return verdict.satisfied, verdict.detail


__all__ = ["DispatchDeps", "Dispatcher"]
