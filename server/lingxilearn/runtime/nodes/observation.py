"""The ``observe`` and ``update_state`` nodes: evidence → profile.

Business logic extracted from the historical ``loop.py`` monolith; the
nodes are wired into the graph by :func:`lingxilearn.runtime.graph.build_loop`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from lingxigraph import Runtime

from ...state.agent_task_state import RuntimeStatus
from ..contracts import TaskOutcome
from ..trace import summarise_profile

if TYPE_CHECKING:
    from ..graph import LoopDeps, LoopState


def build_observe_node(deps: LoopDeps):
    """Build the ``observe`` graph node bound to *deps*."""

    async def observe(state: LoopState, _runtime: Runtime[Any]) -> dict[str, Any]:
        """Evidence was appended by the providers; this is the transition point."""

        if str(state.get("runtime_status")) not in {
            str(RuntimeStatus.OBSERVING),
            str(RuntimeStatus.EXECUTING),
        }:
            return {}
        return await deps.transition_status(state, RuntimeStatus.UPDATING)

    return observe


def build_update_state_node(deps: LoopDeps):
    """Build the ``update_state`` graph node bound to *deps*."""

    async def update_state(state: LoopState, _runtime: Runtime[Any]) -> dict[str, Any]:
        if deps.emit is not None:
            deps.emit(
                "agent.status", {"text": "正在更新对你的掌握度判断…", "phase": "update_state"}
            )
        if str(state.get("runtime_status")) != str(RuntimeStatus.UPDATING):
            return {}
        changes = await deps.updater.apply(learner_id=deps.learner_id)
        if changes:
            deps.tracer.profile_changed(changes)

        decision_id = str(state.get("last_decision_id") or "")
        if decision_id:
            rows = await deps.runtime_state.profile_for(deps.learner_id)
            await _finalise_trace(deps, decision_id, state, rows)
        return {}

    return update_state


async def _finalise_trace(
    deps: LoopDeps,
    decision_id: str,
    state: LoopState,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    """Attach the after-profile and the task outcomes to this round's decision."""

    raw_round_outcomes = state.get("round_outcomes")
    outcomes = [
        TaskOutcome.model_validate(item)
        for item in (
            raw_round_outcomes if raw_round_outcomes is not None else state.get("outcomes") or []
        )
    ]
    await deps.runtime_state.update_decision_outcome(
        decision_id,
        {
            "tasks": [item.to_dict() for item in outcomes],
            "profile_after": summarise_profile(rows),
        },
    )
