"""Canonical runtime-event emission for the dispatch pipeline.

Every ``emit`` call the dispatch path makes goes through
:class:`DispatchProjector`, so the event *vocabulary* — ``work.claimed``,
``node.*``, ``agent.*``, ``skill.*`` — has exactly one owner and one payload
shape per kind.

These are canonical runtime events, not UI payloads: translation into
learner-facing envelopes happens downstream in ``stream/projector.py`` and
``runtime/public_projection.py``.  Nothing here branches on a provider to
hand-build a frontend shape, and the execution runner never emits anything
that bypasses this owner.

The projector reads the emit callable lazily: the dispatcher is constructed
before the compiled graph supplies its per-run runtime, so ``deps.emit`` can
be (re)bound between construction and use.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..contracts import PlannedTask
from ..run_context import RunContext
from .binding import Resolution


class DispatchProjector:
    """Owns the canonical event shape of every dispatch-path emission."""

    def __init__(self, emit: Callable[[], Any]) -> None:
        self._emit = emit

    # -- work scheduling ----------------------------------------------------

    def work_claimed(
        self,
        task: PlannedTask,
        *,
        work_id: str,
        node_id: str,
        attempt: int,
        turn_id: Any,
    ) -> None:
        """Mark the queued → leased boundary for one WorkItem attempt.

        ``node.appeared`` is the queued boundary and ``node.started`` arrives
        after binding; the claim marker makes queue wait and dispatch overhead
        measurable without duplicating work lifecycle events.
        """

        emit = self._emit()
        if emit is None:
            return
        emit(
            "work.claimed",
            {
                "work_item_id": work_id,
                "node_id": node_id,
                "task_id": task.id,
                "logical_task_id": task.id,
                "attempt": attempt,
                "capability": task.capability,
                "turn_id": turn_id,
                "step": int(task.inputs.get("__runtime_step") or 0),
            },
        )

    # -- node lifecycle ------------------------------------------------------

    def node_revising(self, task: PlannedTask, *, node_id: str, resolution: Resolution) -> None:
        emit = self._emit()
        if emit is None:
            return
        emit(
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

    def node_started(self, task: PlannedTask, *, node_id: str, resolution: Resolution) -> None:
        emit = self._emit()
        if emit is None:
            return
        emit(
            "node.started",
            {
                "task_id": task.id,
                "node_id": node_id,
                "capability": task.capability,
                "provider": resolution.provider,
                "skill_id": resolution.skill_id,
            },
        )

    def node_held(self, task: PlannedTask, *, node_id: str, resolution: Resolution) -> None:
        """A satisfied, artifact-producing task is held for delivery."""

        emit = self._emit()
        if emit is None:
            return
        emit(
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

    # -- agent/skill run lifecycle -------------------------------------------

    def agent_started(
        self,
        task: PlannedTask,
        *,
        node_id: str,
        resolution: Resolution,
        run_context: RunContext,
        display_name: str,
        execution_kind: str,
        presentation_role: str,
    ) -> None:
        emit = self._emit()
        if emit is None:
            return
        emit(
            "agent.started",
            {
                "agent": resolution.provider,
                "task_id": task.id,
                "node_id": node_id,
                "capability": task.capability,
                "provider": resolution.provider,
                "skill_id": resolution.skill_id,
                "agent_run_id": run_context.agent_run_id,
                "parent_agent_run_id": run_context.parent_agent_run_id,
                "display_name": display_name,
                "execution_kind": execution_kind,
                "presentation_role": presentation_role,
            },
        )

    def skill_started(
        self,
        task: PlannedTask,
        *,
        node_id: str,
        resolution: Resolution,
        agent_run_id: str,
        skill_run_id: str,
        skill_display_name: str,
    ) -> None:
        emit = self._emit()
        if emit is None:
            return
        emit(
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

    def agent_lifecycle(
        self,
        kind: str,
        task: PlannedTask,
        *,
        node_id: str,
        resolution: Resolution,
        status: str,
        detail: str = "",
        agent_run_id: str = "",
        skill_run_id: str = "",
    ) -> None:
        """Emit ``agent.completed``/``agent.failed`` and its SkillRun pair."""

        emit = self._emit()
        if emit is None:
            return
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
        emit(kind, payload)
        if skill_run_id:
            emit(
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

    # -- learner-safe status lines ---------------------------------------------

    def status_line(
        self,
        task: PlannedTask,
        *,
        node_id: str,
        resolution: Resolution,
        agent_run_id: str,
    ) -> None:
        """The bound skill's own "what I am doing" line."""

        emit = self._emit()
        if emit is None:
            return
        emit(
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

    def no_executor(self, task: PlannedTask, *, node_id: str) -> None:
        """No binding or no implementation: the loop will replan around it."""

        emit = self._emit()
        if emit is None:
            return
        emit(
            "agent.status",
            {
                "task_id": task.id,
                "node_id": node_id,
                "capability": task.capability,
                "text": "这一步没有可用的执行者，我换个方式。",
            },
        )

    def failure_notice(self, task: PlannedTask, *, node_id: str) -> None:
        emit = self._emit()
        if emit is None:
            return
        emit(
            "agent.status",
            {
                "task_id": task.id,
                "node_id": node_id,
                "capability": task.capability,
                "text": "这一步遇到问题，我会保留已完成的部分。",
            },
        )


__all__ = ["DispatchProjector"]
