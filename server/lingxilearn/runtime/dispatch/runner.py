"""Execution ownership: canonical identity, provider invocation, closure.

The runner owns the only code in the dispatch path that *runs* a provider:

* mint the canonical AgentRun/SkillRun identity (issue #18) and persist the
  durable rows when a runtime repository is present;
* assemble the :class:`ProviderContext`, including the identity-stamping
  :class:`_ProviderRuntime` proxy that is also the single delegation door;
* invoke the provider callable exactly once per attempt;
* close the identity — lifecycle events and durable rows — on every outcome:
  success, declared provider error, unexpected exception, or cancellation.

The runner decides nothing about *what an outcome means*: retry, held and
terminal status are dispatch :mod:`policy`, and every event it emits goes
through the canonical :class:`~.projection.DispatchProjector` — it never
formats a UI-specific payload.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Protocol

from ...agents.model_runtime import EVENT_CHANNEL
from ...agents.providers import ProviderContext, ProviderError, ProviderResult
from ...agents.providers import descriptor as provider_descriptor
from ...state.capabilities import info as capability_info
from ..contracts import PlannedTask
from ..run_context import RunContext, new_agent_run_id, new_skill_run_id, presentation_role_for
from .binding import Resolution
from .projection import DispatchProjector

logger = logging.getLogger(__name__)


class _RunChildOwner(Protocol):
    """What the runner needs from its owner to serve ``runtime.delegate``."""

    async def run_child(
        self,
        *,
        parent: RunContext,
        capability: str,
        task: PlannedTask,
        profile: Mapping[str, Mapping[str, Any]],
    ) -> ProviderResult: ...


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
        owner: _RunChildOwner | None = None,
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


@dataclass(slots=True)
class PreparedExecution:
    """One opened execution: identity, durable rows and its runtime proxy."""

    resolution: Resolution
    run_context: RunContext
    skill_run_id: str
    runtime: Any
    node_id: str


class ExecutionRunner:
    """Owns AgentRun/SkillRun lifecycle and provider invocation."""

    def __init__(self, deps: Any, projector: DispatchProjector, owner: _RunChildOwner) -> None:
        self._deps = deps
        self._projector = projector
        self._owner = owner

    async def begin(
        self,
        task: PlannedTask,
        *,
        resolution: Resolution,
        node_id: str,
        work_id: str = "",
        parent: RunContext | None = None,
        emit_node_events: bool = False,
    ) -> PreparedExecution:
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
        if self._deps.runtime_repository is not None:
            for persist in (
                lambda: self._deps.runtime_repository.create_agent_run(
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
                lambda: self._deps.runtime_repository.create_skill_run(
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
                owner=self._owner,
            )
            if self._deps.graph_runtime is not None
            else None
        )

        if emit_node_events:
            # Runtime-lane bookkeeping belongs to the planned task; a
            # delegated child is an actor inside it, not a second node.
            if task.inputs.get("revision"):
                self._projector.node_revising(task, node_id=node_id, resolution=resolution)
            self._projector.node_started(task, node_id=node_id, resolution=resolution)
        self._projector.agent_started(
            task,
            node_id=node_id,
            resolution=resolution,
            run_context=run_context,
            display_name=display_name,
            execution_kind=execution_kind,
            presentation_role=role,
        )
        self._projector.skill_started(
            task,
            node_id=node_id,
            resolution=resolution,
            agent_run_id=agent_run_id,
            skill_run_id=skill_run_id,
            skill_display_name=skill_display_name,
        )
        self._projector.status_line(
            task, node_id=node_id, resolution=resolution, agent_run_id=agent_run_id
        )
        return PreparedExecution(
            resolution=resolution,
            run_context=run_context,
            skill_run_id=skill_run_id,
            runtime=runtime,
            node_id=node_id,
        )

    def provider_context(
        self,
        task: PlannedTask,
        prepared: PreparedExecution,
        *,
        profile: Mapping[str, Mapping[str, Any]],
        prior_results: Mapping[str, Any],
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
            prior_results=dict(prior_results),
            user_message=dict(self._deps.user_message),
            skill_id=prepared.resolution.skill_id,
            shared_skills=self._deps.shared_skills,
            registry=self._deps.registry,
            pack=self._deps.pack,
            run_context=prepared.run_context.with_skill_run(prepared.skill_run_id),
        )

    async def invoke(
        self,
        provider: Any,
        task: PlannedTask,
        prepared: PreparedExecution,
        *,
        profile: Mapping[str, Mapping[str, Any]],
        prior_results: Mapping[str, Any],
    ) -> ProviderResult:
        """Call one provider and close its identity, whatever the outcome.

        Callers keep their own bookkeeping (work ledger, task outcome); this
        owns the lifecycle events and the durable AgentRun/SkillRun closure so
        the two can never disagree.
        """

        resolution = prepared.resolution
        agent_run_id = prepared.run_context.agent_run_id
        skill_run_id = prepared.skill_run_id
        context = self.provider_context(
            task, prepared, profile=profile, prior_results=prior_results
        )
        try:
            result = await provider(context)
        except asyncio.CancelledError:
            self._projector.agent_lifecycle(
                "agent.failed",
                task,
                node_id=prepared.node_id,
                resolution=resolution,
                status="cancelled",
                detail="provider task cancelled",
                agent_run_id=agent_run_id,
                skill_run_id=skill_run_id,
            )
            # Stop must close the durable rows too: an AgentRun/SkillRun left
            # at ``running`` would contradict the cancelled event stream after
            # a refresh (issue #18 §4.4).  Shielded so the in-flight
            # cancellation cannot abort the finalisation itself.
            await self.finish_identity(
                agent_run_id,
                skill_run_id,
                agent_status="cancelled",
                skill_status="cancelled",
                shielded=True,
            )
            raise
        except ProviderError as exc:
            logger.info("provider %s declined: %s", resolution.provider, exc)
            self._projector.agent_lifecycle(
                "agent.failed",
                task,
                node_id=prepared.node_id,
                resolution=resolution,
                status="failed",
                detail=str(exc),
                agent_run_id=agent_run_id,
                skill_run_id=skill_run_id,
            )
            await self.finish_identity(
                agent_run_id, skill_run_id, agent_status="failed", skill_status="failed"
            )
            raise
        except Exception as exc:  # noqa: BLE001 - one provider must not end the run
            logger.exception("provider %s failed", resolution.provider)
            self._projector.agent_lifecycle(
                "agent.failed",
                task,
                node_id=prepared.node_id,
                resolution=resolution,
                status="failed",
                detail=f"{type(exc).__name__}: {exc}",
                agent_run_id=agent_run_id,
                skill_run_id=skill_run_id,
            )
            await self.finish_identity(
                agent_run_id, skill_run_id, agent_status="failed", skill_status="failed"
            )
            raise
        self._projector.agent_lifecycle(
            "agent.completed",
            task,
            node_id=prepared.node_id,
            resolution=resolution,
            status="completed",
            agent_run_id=agent_run_id,
            skill_run_id=skill_run_id,
        )
        await self.finish_identity(
            agent_run_id, skill_run_id, agent_status="completed", skill_status="completed"
        )
        return result

    async def finish_identity(
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

        if self._deps.runtime_repository is None:
            return

        async def finalise() -> None:
            await self._deps.runtime_repository.update_agent_run(
                agent_run_id, status=agent_status, ended=True
            )
            await self._deps.runtime_repository.update_skill_run(skill_run_id, status=skill_status)

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


__all__ = ["ExecutionRunner", "PreparedExecution"]
