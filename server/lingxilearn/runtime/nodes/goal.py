"""The ``interpret_goal`` node: utterance → goal-stack operation.

Business logic extracted from the historical ``loop.py`` monolith; the
node is wired into the graph by :func:`lingxilearn.runtime.graph.build_loop`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lingxigraph import Runtime

from ...state.agent_task_state import RuntimeStatus
from .. import goal_interpreter

if TYPE_CHECKING:
    from ..graph import LoopDeps, LoopState


def build_interpret_goal_node(deps: LoopDeps):
    """Build the ``interpret_goal`` graph node bound to *deps*."""

    async def interpret_goal(state: LoopState, runtime: Runtime[Any]) -> dict[str, Any]:
        if deps.emit is not None:
            deps.emit(
                "agent.status",
                {"text": "已收到你的学习目标，正在准备学习安排。", "phase": "interpret_goal"},
            )
            # Keep the learner-facing opening on the normal model-driven graph
            # path; this is only a status acknowledgement, not a routing fast
            # path or a replacement for the companion model.
            deps.emit(
                "agent.output",
                {
                    "agent": "learning_companion",
                    "message": "我先陪你开始：正在快速了解你的目标，稍后把最先能学的内容送到你面前。",
                    "stream_id": f"{deps.task_id}:opening-companion",
                },
            )
        rows = await deps.runtime_state.profile_for(deps.learner_id)
        stack = await deps.runtime_state.goal_stack(deps.task_id)
        utterance = str(state.get("utterance") or "").strip()

        if not utterance:
            current = stack.current()
            if current is None:
                return await deps.transition_status(
                    state, RuntimeStatus.COMPLETED, finished_reason="没有待处理的学习目标"
                )
            patch = await deps.transition_status(state, RuntimeStatus.PLANNING)
            return {**patch, "goal": current.to_dict()}

        try:
            goal = await goal_interpreter.interpret(
                utterance=utterance,
                model=deps.model,
                profile_rows=rows,
                runtime=runtime,
                current_goal=stack.current(),
            )
        except goal_interpreter.GoalInterpretationUnavailable as exc:
            return await deps.transition_status(
                state,
                RuntimeStatus.FAILED,
                finished_reason=str(exc),
                messages=["目标识别失败，本轮没有执行任何学习技能。"],
            )
        operation = goal_interpreter.apply_to_stack(stack, goal)
        await deps.runtime_state.apply_stack_operation(deps.task_id, operation)
        patch = await deps.transition_status(state, RuntimeStatus.PLANNING)
        if deps.emit is not None:
            deps.emit(f"goal.{operation.op}ed", {"goal": goal.to_dict(), "op": operation.op})
        return {**patch, "goal": goal.to_dict()}

    return interpret_goal
