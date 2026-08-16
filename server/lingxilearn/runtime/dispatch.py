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
from collections.abc import Mapping, Sequence
from contextlib import suppress
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
class _PreparedExecution:
    """One opened execution: identity, durable rows and its runtime proxy."""

    resolution: Resolution
    run_context: RunContext
    skill_run_id: str
    runtime: Any
    node_id: str


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

    async def delegate(
        self,
        capability: str,
        context: ProviderContext,
        *,
        task: PlannedTask | None = None,
    ) -> ProviderResult:
        """Delegate a capability to a second agent under this AgentRun.

        This is the only delegation door, and it runs the same
        ``capability → enabled skill → provider`` chain as every other unit of
        work — never a direct call into a provider implementation.  The child
        therefore gets its own AgentRun *and* SkillRun (bound to the resolved
        skill's version and checksum), its own narration, and the Skill
        ToolCallItem lifecycle on the public stream, nested under this run via
        ``parent_agent_run_id`` (issue #18 §4.4/§4.6).
        """

        if self._owner is None or self._run_context is None:
            raise ProviderError("delegation requires a dispatcher-owned run context")
        return await self._owner.run_child(
            parent=self._run_context,
            capability=capability,
            task=task or context.task,
            profile=context.profile,
        )

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
        prepared = await self._begin_execution(
            task,
            resolution=resolution,
            node_id=node_id,
            work_id=work_id,
            emit_node_events=True,
        )
        agent_run_id = prepared.run_context.agent_run_id
        skill_run_id = prepared.skill_run_id
        run_context = prepared.run_context
        runtime = prepared.runtime

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

        try:
            result = await self._invoke_provider(provider, task, prepared, profile=profile)
        except asyncio.CancelledError:
            raise
        except ProviderError as exc:
            if work_id and self._deps.repository is not None:
                await self._deps.repository.finish_work(
                    work_id=work_id,
                    owner=owner,
                    status="failed",
                    result={"safe_summary": str(exc), "error_code": "provider_error"},
                )
            return self._failed(task, resolution, str(exc), started, node_id=node_id)
        except Exception as exc:  # noqa: BLE001 - one provider must not end the run
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

    # -- the shared execution primitive (issue #18 §4.4/§4.6) ----------------

    async def _begin_execution(
        self,
        task: PlannedTask,
        *,
        resolution: Resolution,
        node_id: str,
        work_id: str = "",
        parent: RunContext | None = None,
        emit_node_events: bool = False,
    ) -> _PreparedExecution:
        """Open one execution: canonical identity, durable rows, lifecycle events.

        Both a planned task and a delegated child come through here, so a child
        is not a second, thinner code path: it gets its own AgentRun *and*
        SkillRun bound to the resolved skill's version/checksum, the same
        narration, and the same ToolCallItem lifecycle on the public stream.
        ``parent`` is what makes the child nested; everything else is identical.
        """

        provider_desc = provider_descriptor(resolution.provider)
        role = presentation_role_for(
            capability=task.capability,
            capability_info=capability_info(task.capability),
            critical_path=task.estimated_cost.critical_path,
        )
        display_name = provider_desc.display_name if provider_desc else resolution.provider
        execution_kind = provider_desc.execution_kind if provider_desc else "model"
        base = RunContext(
            task_id=self._deps.task_id,
            execution_id=self._deps.execution_id,
            turn_id=self._deps.turn_id,
            agent_run_id=new_agent_run_id(),
            provider_id=resolution.provider,
            capability=task.capability,
            presentation_role=role,
            stream_id=f"{self._deps.task_id}:{self._deps.turn_id or 'turn'}",
        )
        run_context = (
            replace(base, parent_agent_run_id=parent.agent_run_id) if parent is not None else base
        )
        agent_run_id = run_context.agent_run_id
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
                    parent_agent_run_id=run_context.parent_agent_run_id or None,
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
            if emit_node_events:
                # Runtime-lane bookkeeping belongs to the planned task; a
                # delegated child is an actor inside it, not a second node.
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
                    "parent_agent_run_id": run_context.parent_agent_run_id,
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
        return _PreparedExecution(
            resolution=resolution,
            run_context=run_context,
            skill_run_id=skill_run_id,
            runtime=runtime,
            node_id=node_id,
        )

    def _provider_context(
        self, task: PlannedTask, prepared: _PreparedExecution, *, profile: Mapping[str, Mapping[str, Any]]
    ) -> ProviderContext:
        return ProviderContext(
            goal=self._deps.goal,
            task=task,
            learner_id=self._deps.learner_id,
            task_id=self._deps.task_id,
            model=self._deps.model,
            settings=self._deps.settings,
            artifacts=self._deps.artifacts,
            runtime=prepared.runtime,
            profile=profile,
            prior_results=dict(self._results),
            user_message=dict(self._deps.user_message),
            skill_id=prepared.resolution.skill_id,
            shared_skills=self._deps.shared_skills,
            registry=self._deps.registry,
            pack=self._deps.pack,
            run_context=prepared.run_context.with_skill_run(prepared.skill_run_id),
        )

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
        prepared = await self._begin_execution(
            child_task, resolution=resolution, node_id=f"{task.id}:{capability}", parent=parent
        )
        result = await self._invoke_provider(
            provider, child_task, prepared, profile=profile
        )
        await self._persist(result)
        return result

    async def _invoke_provider(
        self,
        provider: Any,
        task: PlannedTask,
        prepared: _PreparedExecution,
        *,
        profile: Mapping[str, Mapping[str, Any]],
    ) -> ProviderResult:
        """Call one provider and close its identity, whatever the outcome.

        Callers keep their own bookkeeping (work ledger, task outcome); this
        owns the lifecycle events and the durable AgentRun/SkillRun closure so
        the two can never disagree.
        """

        resolution = prepared.resolution
        agent_run_id = prepared.run_context.agent_run_id
        skill_run_id = prepared.skill_run_id
        context = self._provider_context(task, prepared, profile=profile)
        try:
            result = await provider(context)
        except asyncio.CancelledError:
            self._emit_agent_lifecycle(
                "agent.failed",
                task=task,
                resolution=resolution,
                node_id=prepared.node_id,
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
                node_id=prepared.node_id,
                status="failed",
                detail=str(exc),
                agent_run_id=agent_run_id,
                skill_run_id=skill_run_id,
            )
            await self._finish_identity(
                agent_run_id, skill_run_id, agent_status="failed", skill_status="failed"
            )
            raise
        except Exception as exc:  # noqa: BLE001 - one provider must not end the run
            logger.exception("provider %s failed", resolution.provider)
            self._emit_agent_lifecycle(
                "agent.failed",
                task=task,
                resolution=resolution,
                node_id=prepared.node_id,
                status="failed",
                detail=f"{type(exc).__name__}: {exc}",
                agent_run_id=agent_run_id,
                skill_run_id=skill_run_id,
            )
            await self._finish_identity(
                agent_run_id, skill_run_id, agent_status="failed", skill_status="failed"
            )
            raise
        self._emit_agent_lifecycle(
            "agent.completed",
            task=task,
            resolution=resolution,
            node_id=prepared.node_id,
            status="completed",
            agent_run_id=agent_run_id,
            skill_run_id=skill_run_id,
        )
        await self._finish_identity(
            agent_run_id, skill_run_id, agent_status="completed", skill_status="completed"
        )
        return result

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
