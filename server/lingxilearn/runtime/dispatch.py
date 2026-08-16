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

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field, replace
from typing import Any

from ..agents.model_runtime import EVENT_CHANNEL
from ..agents.providers import ProviderContext, ProviderError, ProviderResult
from ..agents.providers import descriptor as provider_descriptor
from ..agents.providers import get as get_provider
from ..agents.providers import load_all as load_providers
from ..state.capabilities import info as capability_info
from ..state.evidence import EvidenceRecord
from ..state.session_state import Goal
from ..store.runtime_state import RuntimeStateRepository
from .candidates import RegisteredSkill, candidate_id
from .completion import CompletionContext, StoreArtifactProbe, evaluate
from .contracts import PlannedTask, TaskOutcome
from .guardrails import Budget
from .run_context import RunContext, new_agent_run_id, new_skill_run_id, presentation_role_for

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
    candidate_id: str = ""
    display_name: str = ""
    skill_version: str = ""
    skill_checksum: str = ""


def resolve(
    capability: str,
    skills: Sequence[Mapping[str, Any]],
    *,
    selected_candidate_id: str = "",
    knowledge_point_id: str = "",
) -> Resolution:
    """Pick the cheapest enabled skill that provides ``capability``.

    Ties break on skill id so the same state always resolves the same way; a
    resolution that varies run to run would make the trace unreproducible.
    """

    matches = []
    for row in skills:
        skill = RegisteredSkill.from_row(row)
        if not skill.enabled or not skill.provider or capability not in skill.capabilities:
            continue
        if (
            selected_candidate_id
            and candidate_id(skill, capability, knowledge_point_id) == selected_candidate_id
        ):
            matches.append(row)
        elif not selected_candidate_id:
            matches.append(row)
    if not matches:
        suffix = f" bound candidate {selected_candidate_id}" if selected_candidate_id else ""
        raise NoProvider(f"no enabled skill provides {capability}{suffix}")
    if selected_candidate_id and len(matches) != 1:
        raise NoProvider(f"candidate binding is ambiguous: {selected_candidate_id}")
    matches.sort(
        key=lambda row: (
            float((row.get("cost") or {}).get("latency_weight") or 1.0),
            str(row.get("skill_id")),
        )
    )
    chosen = matches[0]
    metadata = chosen.get("metadata") or {}
    return Resolution(
        capability=capability,
        skill_id=str(chosen["skill_id"]),
        provider=str(chosen["provider"]),
        cost=dict(chosen.get("cost") or {}),
        status_line=str(metadata.get("status_line") or "正在处理这一步…"),
        candidate_id=selected_candidate_id,
        display_name=str(chosen.get("display_name") or ""),
        skill_version=str(chosen.get("version") or ""),
        skill_checksum=str(chosen.get("checksum") or ""),
    )


@dataclass(slots=True)
class DispatchDeps:
    """Everything dispatch needs that is not part of the plan."""

    runtime_state: RuntimeStateRepository
    learner_id: str
    task_id: str
    goal: Goal
    skills: Sequence[Mapping[str, Any]]
    repository: Any = None
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


class _ProviderRuntime:
    """Add execution identity to provider-side trace events.

    Providers share the graph runtime with the dispatcher and historically
    emitted only their logical task id (``t1``/``t2``).  Those ids repeat after
    a replan, so the projector could attach a later model span to an older
    agent.  This transparent proxy keeps the provider API unchanged while
    carrying the unique runtime node id — and now the canonical
    ``agent_run_id``/``skill_run_id`` — on every event.
    """

    def __init__(
        self,
        runtime: Any,
        *,
        task_id: str,
        node_id: str,
        step: int,
        run_context: RunContext | None = None,
        owner: Dispatcher | None = None,
    ) -> None:
        self._runtime = runtime
        self._task_id = task_id
        self._node_id = node_id
        self._step = step
        self._run_context = run_context
        self._owner = owner

    @property
    def run_context(self) -> RunContext | None:
        """The canonical identity every event from this proxy carries."""

        return self._run_context

    def emit(self, channel: str, value: Any) -> Any:
        if isinstance(value, Mapping):
            payload = dict(value)
            payload.setdefault("task_id", self._task_id)
            payload.setdefault("node_id", self._node_id)
            payload.setdefault("step", self._step)
            context = self._run_context
            if context is not None:
                if context.agent_run_id:
                    payload.setdefault("agent_run_id", context.agent_run_id)
                if context.skill_run_id:
                    payload.setdefault("skill_run_id", context.skill_run_id)
                if context.execution_id:
                    payload.setdefault("execution_id", context.execution_id)
            value = payload
        return self._runtime.emit(channel, value)

    def narrate(self, text: str, *, code: str = "") -> Any:
        """Emit a learner-safe status line; identity is attached automatically.

        Providers use this instead of hand-building status events so every
        narration is scoped to the canonical agent/skill run (issue #18 §8.2).
        """

        return self.emit(
            EVENT_CHANNEL,
            {"type": "agent.status", "text": text, **({"code": code} if code else {})},
        )

    @asynccontextmanager
    async def delegate(
        self,
        provider_id: str,
        *,
        display_name: str = "",
        capability: str = "",
        execution_kind: str = "model",
    ) -> AsyncIterator[_ProviderRuntime]:
        """Run a real child actor under this AgentRun.

        A provider that hands part of its work to a second, distinct agent
        wraps that call in this context manager.  The child gets its own
        durable AgentRun carrying ``parent_agent_run_id``, so the nested
        AgentGroup on the left and the delegation edge on the right come from
        the same fact rather than from a name lookup (issue #18 §4.4).
        """

        parent = self._run_context
        if parent is None or self._owner is None:
            # Standalone unit runs without dispatcher identity: keep the
            # provider working, but never invent a child identity.
            yield self
            return
        child = parent.delegate(provider_id=provider_id, capability=capability)
        runtime = _ProviderRuntime(
            self._runtime,
            task_id=self._task_id,
            node_id=self._node_id,
            step=self._step,
            run_context=child,
            owner=self._owner,
        )
        await self._owner.open_delegate(
            child, display_name=display_name or provider_id, execution_kind=execution_kind
        )
        status = "completed"
        try:
            yield runtime
        except asyncio.CancelledError:
            status = "cancelled"
            await self._owner.close_delegate(child, status=status, shielded=True)
            raise
        except BaseException:
            status = "failed"
            await self._owner.close_delegate(child, status=status)
            raise
        else:
            await self._owner.close_delegate(child, status=status)

    async def delegate_to(
        self,
        provider_id: str,
        context: ProviderContext,
        *,
        capability: str = "",
        task: PlannedTask | None = None,
    ) -> ProviderResult:
        """Run a second real provider as a child of this AgentRun.

        This is the execution entry point behind :meth:`delegate`: the child
        provider is resolved from the same registry the dispatcher uses, runs
        under its own canonical identity, and its events are stamped with the
        child ``agent_run_id`` — so a nested AgentGroup and a delegation edge
        describe an execution that really happened (issue #18 §4.4).

        No shipped provider delegates today; this is the supported way for one
        to start, and the identity it produces is already durable.
        """

        if self._owner is None or self._run_context is None:
            raise ProviderError("delegation requires a dispatcher-owned run context")
        provider = get_provider(provider_id)
        if provider is None:
            raise ProviderError(f"provider is not implemented: {provider_id}")
        descriptor = provider_descriptor(provider_id)
        async with self.delegate(
            provider_id,
            display_name=descriptor.display_name if descriptor else provider_id,
            capability=capability,
            execution_kind=descriptor.execution_kind if descriptor else "model",
        ) as child_runtime:
            child_context = replace(
                context,
                task=task or context.task,
                runtime=child_runtime,
                run_context=child_runtime.run_context,
            )
            return await provider(child_context)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._runtime, name)


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
        claimed: dict[str, Any] | None = None
        if work_id and self._deps.repository is not None:
            claimed = await self._deps.repository.claim_work_item(
                work_id=work_id,
                owner=f"dispatcher:{self._deps.task_id}",
            )
            if claimed is None:
                return TaskOutcome(
                    task_id=task.id,
                    capability=task.capability,
                    node_id=node_id,
                    status="blocked",
                    detail="work item is not claimable or its dependencies have not succeeded",
                )
            if self._deps.emit is not None:
                # ``node.appeared`` is the queued boundary and ``node.started``
                # is emitted below after capability/provider resolution.  The
                # claim marker makes queue wait and dispatch overhead
                # measurable without introducing duplicate work lifecycle
                # events.
                self._deps.emit(
                    "work.claimed",
                    {
                        "work_item_id": work_id,
                        "node_id": node_id,
                        "task_id": task.id,
                        "logical_task_id": task.id,
                        "attempt": int(claimed.get("attempts") or claimed.get("attempt") or 1),
                        "capability": task.capability,
                        "turn_id": claimed.get("turn_id"),
                        "step": int(task.inputs.get("__runtime_step") or 0),
                    },
                )
        owner = f"dispatcher:{self._deps.task_id}"
        heartbeat: asyncio.Task[None] | None = None
        if work_id and self._deps.repository is not None:

            async def keep_lease() -> None:
                while True:
                    await asyncio.sleep(20)
                    if not await self._deps.repository.heartbeat_work(work_id=work_id, owner=owner):
                        return

            heartbeat = asyncio.create_task(keep_lease())
        try:
            resolution = resolve(
                task.capability,
                self._deps.skills,
                selected_candidate_id=task.candidate_id,
                knowledge_point_id=task.knowledge_point_id,
            )
        except NoProvider as exc:
            if heartbeat is not None:
                await self._stop_heartbeat(heartbeat)
            if work_id and self._deps.repository is not None:
                await self._deps.repository.finish_work(
                    work_id=work_id,
                    owner=owner,
                    status="failed",
                    result={"safe_summary": str(exc), "error_code": "no_provider"},
                )
            if self._deps.emit is not None:
                self._deps.emit(
                    "agent.status",
                    {
                        "task_id": task.id,
                        "node_id": node_id,
                        "capability": task.capability,
                        "text": "这一步没有可用的执行者，我换个方式。",
                    },
                )
            return TaskOutcome(
                task_id=task.id,
                capability=task.capability,
                node_id=node_id,
                status="blocked",
                detail=str(exc),
            )

        # -- canonical AgentRun identity (issue #18) ---------------------------
        # The dispatcher — not the provider — owns the agent lifecycle.  Each
        # real invocation attempt gets a fresh agent_run_id, so a WorkItem
        # retry can never reuse a previous attempt's identity.
        provider_desc = provider_descriptor(resolution.provider)
        role = presentation_role_for(
            capability=task.capability,
            capability_info=capability_info(task.capability),
            critical_path=task.estimated_cost.critical_path,
        )
        agent_run_id = new_agent_run_id()
        display_name = provider_desc.display_name if provider_desc else resolution.provider
        execution_kind = provider_desc.execution_kind if provider_desc else "model"
        run_context = RunContext(
            task_id=self._deps.task_id,
            execution_id=self._deps.execution_id,
            turn_id=self._deps.turn_id,
            agent_run_id=agent_run_id,
            provider_id=resolution.provider,
            capability=task.capability,
            presentation_role=role,
            stream_id=f"{self._deps.task_id}:{self._deps.turn_id or 'turn'}",
        )
        skill_run_id = new_skill_run_id()
        skill_display_name = resolution.display_name or resolution.skill_id
        if self._deps.repository is not None:
            for persist in (
                lambda: self._deps.repository.create_agent_run(
                    agent_run_id=agent_run_id,
                    task_id=self._deps.task_id,
                    execution_id=self._deps.execution_id or self._deps.task_id,
                    turn_id=self._deps.turn_id or None,
                    work_item_id=work_id or None,
                    provider_id=resolution.provider,
                    agent_display_name=display_name,
                    execution_kind=execution_kind,
                    capability=task.capability,
                    presentation_role=role,
                    started=True,
                    safe_metadata={"skill_id": resolution.skill_id},
                ),
                lambda: self._deps.repository.create_skill_run(
                    skill_run_id=skill_run_id,
                    agent_run_id=agent_run_id,
                    task_id=self._deps.task_id,
                    execution_id=self._deps.execution_id or self._deps.task_id,
                    turn_id=self._deps.turn_id or None,
                    skill_id=resolution.skill_id,
                    display_name=skill_display_name,
                    version=resolution.skill_version,
                    checksum=resolution.skill_checksum,
                ),
            ):
                try:
                    await persist()
                except Exception:  # noqa: BLE001 - identity rows must not fail the run
                    logger.exception("failed to persist execution identity")

        runtime = (
            _ProviderRuntime(
                self._deps.graph_runtime,
                task_id=task.id,
                node_id=node_id,
                step=int(task.inputs.get("__runtime_step") or 0),
                run_context=run_context,
                owner=self,
            )
            if self._deps.graph_runtime is not None
            else None
        )

        if self._deps.emit is not None:
            if task.inputs.get("revision"):
                self._deps.emit(
                    "node.revising",
                    {
                        "task_id": task.id,
                        "node_id": node_id,
                        "capability": task.capability,
                        "provider": resolution.provider,
                        "skill_id": resolution.skill_id,
                        "revising": True,
                    },
                )
            self._deps.emit(
                "node.started",
                {
                    "task_id": task.id,
                    "node_id": node_id,
                    "capability": task.capability,
                    "provider": resolution.provider,
                    "skill_id": resolution.skill_id,
                },
            )
            self._deps.emit(
                "agent.started",
                {
                    "agent": resolution.provider,
                    "task_id": task.id,
                    "node_id": node_id,
                    "capability": task.capability,
                    "provider": resolution.provider,
                    "skill_id": resolution.skill_id,
                    "agent_run_id": agent_run_id,
                    "display_name": display_name,
                    "execution_kind": execution_kind,
                    "presentation_role": role,
                },
            )
            self._deps.emit(
                "skill.started",
                {
                    "agent": resolution.provider,
                    "task_id": task.id,
                    "node_id": node_id,
                    "agent_run_id": agent_run_id,
                    "skill_run_id": skill_run_id,
                    "skill_id": resolution.skill_id,
                    "display_name": skill_display_name,
                    "version": resolution.skill_version,
                    "checksum": resolution.skill_checksum,
                },
            )
            self._deps.emit(
                "agent.status",
                {
                    "task_id": task.id,
                    "node_id": node_id,
                    "capability": task.capability,
                    "provider": resolution.provider,
                    "skill_id": resolution.skill_id,
                    "agent_run_id": agent_run_id,
                    "text": resolution.status_line,
                },
            )

        provider = get_provider(resolution.provider)
        if provider is None:
            if heartbeat is not None:
                await self._stop_heartbeat(heartbeat)
            if work_id and self._deps.repository is not None:
                await self._deps.repository.finish_work(
                    work_id=work_id,
                    owner=owner,
                    status="failed",
                    result={
                        "safe_summary": "provider is not implemented",
                        "error_code": "provider_missing",
                    },
                )
            if self._deps.emit is not None:
                self._deps.emit(
                    "agent.status",
                    {
                        "task_id": task.id,
                        "node_id": node_id,
                        "capability": task.capability,
                        "text": "这一步没有可用的执行者，我换个方式。",
                    },
                )
            await self._finish_identity(
                agent_run_id, skill_run_id, agent_status="failed", skill_status="failed"
            )
            return TaskOutcome(
                task_id=task.id,
                capability=task.capability,
                node_id=node_id,
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
            runtime=runtime,
            profile=profile,
            prior_results=dict(self._results),
            user_message=dict(self._deps.user_message),
            skill_id=resolution.skill_id,
            shared_skills=self._deps.shared_skills,
            registry=self._deps.registry,
            pack=self._deps.pack,
            run_context=run_context.with_skill_run(skill_run_id),
        )

        try:
            result = await provider(context)
            self._emit_agent_lifecycle(
                "agent.completed",
                task=task,
                resolution=resolution,
                node_id=node_id,
                status="completed",
                agent_run_id=agent_run_id,
                skill_run_id=skill_run_id,
            )
        except asyncio.CancelledError:
            self._emit_agent_lifecycle(
                "agent.failed",
                task=task,
                resolution=resolution,
                node_id=node_id,
                status="cancelled",
                detail="provider task cancelled",
                agent_run_id=agent_run_id,
                skill_run_id=skill_run_id,
            )
            # Stop must close the durable rows too: an AgentRun/SkillRun left
            # at ``running`` would contradict the cancelled event stream after
            # a refresh (issue #18 §4.4).  Shielded so the in-flight
            # cancellation cannot abort the finalisation itself.
            await self._finish_identity(
                agent_run_id,
                skill_run_id,
                agent_status="cancelled",
                skill_status="cancelled",
                shielded=True,
            )
            raise
        except ProviderError as exc:
            logger.info("provider %s declined: %s", resolution.provider, exc)
            self._emit_agent_lifecycle(
                "agent.failed",
                task=task,
                resolution=resolution,
                node_id=node_id,
                status="failed",
                detail=str(exc),
                agent_run_id=agent_run_id,
                skill_run_id=skill_run_id,
            )
            if work_id and self._deps.repository is not None:
                await self._deps.repository.finish_work(
                    work_id=work_id,
                    owner=owner,
                    status="failed",
                    result={"safe_summary": str(exc), "error_code": "provider_error"},
                )
            await self._finish_identity(
                agent_run_id, skill_run_id, agent_status="failed", skill_status="failed"
            )
            return self._failed(task, resolution, str(exc), started, node_id=node_id)
        except Exception as exc:  # noqa: BLE001 - one provider must not end the run
            logger.exception("provider %s failed", resolution.provider)
            self._emit_agent_lifecycle(
                "agent.failed",
                task=task,
                resolution=resolution,
                node_id=node_id,
                status="failed",
                detail=f"{type(exc).__name__}: {exc}",
                agent_run_id=agent_run_id,
                skill_run_id=skill_run_id,
            )
            if work_id and self._deps.repository is not None:
                await self._deps.repository.finish_work(
                    work_id=work_id,
                    owner=owner,
                    status="failed",
                    result={
                        "safe_summary": f"{type(exc).__name__}: {exc}",
                        "error_code": "provider_failed",
                    },
                )
            await self._finish_identity(
                agent_run_id, skill_run_id, agent_status="failed", skill_status="failed"
            )
            return self._failed(
                task,
                resolution,
                f"{type(exc).__name__}: {exc}",
                started,
                node_id=node_id,
            )
        finally:
            if heartbeat is not None:
                await self._stop_heartbeat(heartbeat)

        await self._finish_identity(
            agent_run_id, skill_run_id, agent_status="completed", skill_status="completed"
        )
        evidence_ids = await self._persist(result)
        satisfied, detail = await self._check_done(task, result, evidence_ids)
        if work_id and self._deps.repository is not None:
            await self._deps.repository.finish_work(
                work_id=work_id,
                owner=owner,
                status="succeeded" if satisfied else "incomplete",
                result={
                    "schema_id": str(getattr(result, "schema_id", "")),
                    "safe_summary": result.detail,
                    "artifact_refs": list(result.artifacts),
                    "evidence_refs": list(evidence_ids),
                    "usage": {
                        "tokens": result.tokens_used,
                        "wall_ms": int((time.monotonic() - started) * 1000),
                        "heavy": 1 if result.artifacts else 0,
                    },
                    "output_payload": {},
                },
            )
            if claimed is not None:
                await self._deps.repository.save_fact_snapshot(
                    task_id=self._deps.task_id,
                    turn_id=str(claimed.get("turn_id") or ""),
                    plan_revision=int(claimed.get("plan_revision") or 0),
                    facts={
                        "work_id": work_id,
                        "task_id": task.id,
                        "capability": task.capability,
                        "status": "succeeded" if satisfied else "incomplete",
                        "satisfied": bool(satisfied),
                        "schema_id": str(getattr(result, "schema_id", "")),
                    },
                    evidence_refs=list(evidence_ids),
                    artifact_refs=list(result.artifacts),
                )
        held = bool(result.artifacts) and satisfied
        revision = int((task.inputs.get("revision") or {}).get("number") or 0)
        if held and self._deps.emit is not None:
            self._deps.emit(
                "node.held",
                {
                    "task_id": task.id,
                    "node_id": node_id,
                    "capability": task.capability,
                    "provider": resolution.provider,
                    "skill_id": resolution.skill_id,
                    "status": "completed",
                    "satisfied": True,
                    "held": True,
                },
            )
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
            duration_ms=int((time.monotonic() - started) * 1000),
            heavy=bool(task.estimated_cost.heavy_artifact),
            held=held,
            revision=revision,
        )

    # -- internals -----------------------------------------------------------

    @staticmethod
    async def _stop_heartbeat(heartbeat: asyncio.Task[None]) -> None:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat

    def _emit_agent_lifecycle(
        self,
        kind: str,
        *,
        task: PlannedTask,
        resolution: Resolution,
        node_id: str,
        status: str,
        detail: str = "",
        agent_run_id: str = "",
        skill_run_id: str = "",
    ) -> None:
        if self._deps.emit is not None:
            payload: dict[str, Any] = {
                "agent": resolution.provider,
                "task_id": task.id,
                "node_id": node_id,
                "capability": task.capability,
                "provider": resolution.provider,
                "skill_id": resolution.skill_id,
                "status": status,
            }
            if agent_run_id:
                payload["agent_run_id"] = agent_run_id
            if detail:
                payload["detail"] = detail
            self._deps.emit(kind, payload)
            if skill_run_id:
                self._deps.emit(
                    "skill.completed" if status == "completed" else "skill.failed",
                    {
                        "agent": resolution.provider,
                        "task_id": task.id,
                        "node_id": node_id,
                        "agent_run_id": agent_run_id,
                        "skill_run_id": skill_run_id,
                        "skill_id": resolution.skill_id,
                        "status": status,
                    },
                )

    # -- delegation (issue #18 §4.4) ----------------------------------------

    async def open_delegate(
        self, child: RunContext, *, display_name: str, execution_kind: str
    ) -> None:
        """Persist and announce a child AgentRun the parent delegates to."""

        if self._deps.repository is not None:
            try:
                await self._deps.repository.create_agent_run(
                    agent_run_id=child.agent_run_id,
                    task_id=self._deps.task_id,
                    execution_id=child.execution_id or self._deps.task_id,
                    turn_id=child.turn_id or None,
                    parent_agent_run_id=child.parent_agent_run_id or None,
                    provider_id=child.provider_id,
                    agent_display_name=display_name,
                    execution_kind=execution_kind,
                    capability=child.capability,
                    presentation_role=child.presentation_role,
                    started=True,
                )
            except Exception:  # noqa: BLE001 - identity rows must not fail the run
                logger.exception("failed to persist delegated agent run")
        if self._deps.emit is not None:
            self._deps.emit(
                "agent.started",
                {
                    "agent": child.provider_id,
                    "provider": child.provider_id,
                    "capability": child.capability,
                    "agent_run_id": child.agent_run_id,
                    "parent_agent_run_id": child.parent_agent_run_id,
                    "display_name": display_name,
                    "execution_kind": execution_kind,
                    "presentation_role": child.presentation_role,
                },
            )

    async def close_delegate(
        self, child: RunContext, *, status: str, shielded: bool = False
    ) -> None:
        if self._deps.emit is not None:
            self._deps.emit(
                "agent.completed" if status == "completed" else "agent.failed",
                {
                    "agent": child.provider_id,
                    "provider": child.provider_id,
                    "capability": child.capability,
                    "agent_run_id": child.agent_run_id,
                    "parent_agent_run_id": child.parent_agent_run_id,
                    "status": status,
                },
            )
        if self._deps.repository is None:
            return

        async def finalise() -> None:
            await self._deps.repository.update_agent_run(
                child.agent_run_id, status=status, ended=True
            )

        try:
            if shielded:
                await asyncio.shield(asyncio.ensure_future(finalise()))
            else:
                await finalise()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("failed to finalise delegated agent run")

    async def _finish_identity(
        self,
        agent_run_id: str,
        skill_run_id: str,
        *,
        agent_status: str,
        skill_status: str,
        shielded: bool = False,
    ) -> None:
        """Close the durable identity rows; projection must never fail the run.

        ``shielded`` is used on the cancellation path, where the enclosing task
        is already being cancelled and a bare ``await`` would be interrupted
        before the rows are written.
        """

        if self._deps.repository is None:
            return

        async def finalise() -> None:
            await self._deps.repository.update_agent_run(
                agent_run_id, status=agent_status, ended=True
            )
            await self._deps.repository.update_skill_run(skill_run_id, status=skill_status)

        try:
            if shielded:
                await asyncio.shield(asyncio.ensure_future(finalise()))
            else:
                await finalise()
        except asyncio.CancelledError:
            # The shield itself was cancelled; the inner write keeps running to
            # completion in its own task.  Never swallow the cancellation.
            raise
        except Exception:  # noqa: BLE001
            logger.exception("failed to finalise execution identity")

    def _failed(
        self,
        task: PlannedTask,
        resolution: Resolution,
        detail: str,
        started: float,
        *,
        node_id: str,
    ) -> TaskOutcome:
        if self._deps.emit is not None:
            self._deps.emit(
                "agent.status",
                {
                    "task_id": task.id,
                    "node_id": node_id,
                    "capability": task.capability,
                    "text": "这一步遇到问题，我会保留已完成的部分。",
                },
            )
        return TaskOutcome(
            task_id=task.id,
            capability=task.capability,
            node_id=node_id,
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
