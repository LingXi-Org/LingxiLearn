"""The ``evaluate_goal`` node: decide the next phase after a round.

The decision itself is the pure policy in
:mod:`lingxilearn.runtime.evaluation`; this node owns the side effects —
goal-stack pops, the post-answer follow-up Interaction, round events, and
persisting the transition through the single lifecycle write path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lingxigraph import Runtime

from ...state.agent_task_state import Goal, RuntimeStatus
from ...state.capabilities import info
from ..contracts import TaskOutcome
from ..evaluation import check_goal_satisfied, decide_next_phase
from ..interactions import build_followup_interaction, request_interaction

if TYPE_CHECKING:
    from ..graph import LoopDeps, LoopState


def build_evaluate_goal_node(deps: LoopDeps):
    """Build the ``evaluate_goal`` graph node bound to *deps*."""

    async def evaluate_goal(state: LoopState, _runtime: Runtime[Any]) -> dict[str, Any]:
        """Did the round achieve the goal, or does the next one differ?"""

        status = str(state.get("runtime_status"))
        round_step = int(state.get("step") or 0)
        decision_id = str(state.get("last_decision_id") or "")
        if status in {str(RuntimeStatus.FAILED), str(RuntimeStatus.COMPLETED)}:
            deps.close_round(step=round_step, decision_id=decision_id, status=status)
            return {}
        if status == str(RuntimeStatus.WAITING_FOR_USER):
            deps.close_round(step=round_step, decision_id=decision_id, status=status)
            return {}

        goal = Goal.from_dict(state.get("goal") or {})
        raw_round_outcomes = state.get("round_outcomes")
        outcomes = [
            TaskOutcome.model_validate(item)
            for item in (
                raw_round_outcomes
                if raw_round_outcomes is not None
                else state.get("outcomes") or []
            )
        ]

        plan_payload = dict(state.get("plan") or {})
        profile_rows = {
            str(row["knowledge_point_id"]): row
            for row in await deps.runtime_state.profile_for(deps.learner_id)
        }
        satisfied = check_goal_satisfied(
            plan_payload, profile_rows, artifacts=deps.artifacts, task_id=deps.task_id
        )

        # A satisfied goal pops the stack before the decision is taken, so the
        # pure policy only has to say whether another goal remains.
        remaining = None
        if satisfied:
            stack = await deps.runtime_state.goal_stack(deps.task_id)
            operation = stack.pop(reason="目标达成", goal_id=goal.id)
            await deps.runtime_state.apply_stack_operation(deps.task_id, operation)
            if deps.emit is not None:
                deps.emit("goal.popped", {"goal_id": goal.id})
            remaining = stack.current()

        decision = decide_next_phase(
            outcomes,
            goal_satisfied=satisfied,
            has_remaining_goals=remaining is not None if satisfied else True,
            background_pending=bool(state.get("background_pending")),
        )

        if decision.result_tag == "goal_satisfied":
            patch = await deps.transition_status(state, decision.status, **decision.extra_patch)
            if remaining is not None:
                patch = {**patch, "goal": remaining.to_dict()}
            deps.close_round(
                step=round_step,
                decision_id=decision_id,
                status=str(decision.status),
                outcomes=[item.to_dict() for item in outcomes],
                result="goal_satisfied",
            )
            return patch

        if decision.result_tag == "turn_complete":
            # A completed answer/explanation must not fall silently into
            # WAITING_FOR_USER (issue #32 §2): offer a structured follow-up
            # through the same Interaction protocol pre-execution HITL uses,
            # so the frontend renders a card and the learner's choice becomes
            # an Orchestrator input on the next round rather than a dead end.
            # A round that already produced its own blocking interaction (the
            # pre-execution HITL path in ``orchestrate``) never reaches here
            # with tasks executed, but the check stays defensive against a
            # future round shape that does both in one pass.
            patch = await deps.transition_status(state, decision.status, **decision.extra_patch)
            existing_pending_interaction = state.get("pending_interaction")
            if not existing_pending_interaction:
                turn_completing = next(
                    (
                        item
                        for item in outcomes
                        if item.satisfied and info(item.capability).turn_complete
                    ),
                    None,
                )
                if turn_completing is not None:
                    followup = build_followup_interaction(
                        capability=turn_completing.capability,
                        knowledge_point_id=(
                            goal.knowledge_points[0] if goal.knowledge_points else ""
                        ),
                        topic=goal.topic,
                    )
                    if followup is not None:
                        # Only touch the checkpoint field when we actually create a
                        # new follow-up interaction. Unconditionally writing this
                        # key (even as None) would clobber an existing pending
                        # interaction from state, undoing the anti-double-card
                        # guard above.
                        patch["pending_interaction"] = await request_interaction(deps, followup)
            deps.close_round(
                step=round_step,
                decision_id=decision_id,
                status=str(decision.status),
                outcomes=[item.to_dict() for item in outcomes],
                result="turn_complete",
            )
            return patch

        # background_pending, no_progress and replan share the plain shape:
        # persist the decided phase with its patch, then close the round.
        patch = await deps.transition_status(state, decision.status, **decision.extra_patch)
        deps.close_round(
            step=round_step,
            decision_id=decision_id,
            status=str(decision.status),
            outcomes=[item.to_dict() for item in outcomes],
            result=decision.result_tag,
        )
        return patch

    return evaluate_goal
