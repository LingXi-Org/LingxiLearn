"""Pure evaluation policy for the runtime loop.

Contains the decision logic that determines what happens after a round of
execution: complete, replan, wait for user, or fail.  All functions in this
module are **pure** — they take data and return a decision without
touching any database or graph checkpoint.

This makes the policy independently testable without constructing a full
graph or injecting service dependencies.  Side effects (goal-stack pops,
follow-up Interaction requests, round events, status persistence) stay in
the ``evaluate_goal`` node (:mod:`lingxilearn.runtime.nodes.evaluation`),
which applies the decision through the single-owner paths
(:meth:`LoopDeps.transition_status`, :func:`interactions.request_interaction`).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from ..state.agent_task_state import RuntimeStatus
from ..state.capabilities import info
from .completion import CompletionContext, StoreArtifactProbe, evaluate
from .contracts import DoneCondition, TaskOutcome

logger = logging.getLogger(__name__)


class PhaseDecision:
    """The result of evaluating a completed round.

    ``status`` is the canonical next runtime phase.  Extra graph-patch
    fields (e.g. ``finished_reason``, ``replanning``) are carried in
    ``extra_patch`` and merged into the checkpoint update by the caller.
    """

    __slots__ = ("status", "extra_patch", "result_tag")

    def __init__(
        self,
        status: RuntimeStatus,
        *,
        extra_patch: dict[str, Any] | None = None,
        result_tag: str = "",
    ) -> None:
        self.status = status
        self.extra_patch = extra_patch or {}
        self.result_tag = result_tag


def decide_next_phase(
    outcomes: Sequence[TaskOutcome],
    *,
    goal_satisfied: bool,
    has_remaining_goals: bool = True,
    background_pending: bool = False,
) -> PhaseDecision:
    """Decide the next runtime phase based on round outcomes.

    This is the pure policy function — it does not perform any I/O.
    The calling node is responsible for persisting the decision and
    executing side-effects (goal-stack mutations, follow-up Interaction
    requests, event emission, etc.).

    The policy priority order is:

    1. Goal satisfied + no remaining goals → COMPLETED
    2. Goal satisfied + remaining goals → REPLANNING
    3. Turn-complete outcome → WAITING_FOR_USER (follow-up candidate)
    4. Background work pending → WAITING_FOR_USER
    5. No progress (empty / all-failed outcomes) → FAILED
    6. Otherwise → REPLANNING
    """

    # --- goal satisfied ---------------------------------------------------
    if goal_satisfied:
        if not has_remaining_goals:
            return PhaseDecision(
                RuntimeStatus.COMPLETED,
                extra_patch={"finished_reason": "目标已达成"},
                result_tag="goal_satisfied",
            )
        return PhaseDecision(
            RuntimeStatus.REPLANNING,
            extra_patch={"replanning": True},
            result_tag="goal_satisfied",
        )

    # --- turn-complete (conversational) -----------------------------------
    if any(item.satisfied and info(item.capability).turn_complete for item in outcomes):
        return PhaseDecision(
            RuntimeStatus.WAITING_FOR_USER,
            extra_patch={"messages": [], "replanning": False},
            result_tag="turn_complete",
        )

    # --- detached background work still pending ---------------------------
    if background_pending:
        return PhaseDecision(
            RuntimeStatus.WAITING_FOR_USER,
            extra_patch={"messages": []},
            result_tag="background_pending",
        )

    # --- no-progress guard ------------------------------------------------
    if not outcomes or all(
        item.status in {"failed", "skipped", "blocked"} for item in outcomes[-3:]
    ):
        message = "本轮没有产生新的学习结果，已暂停自动编排，请换一种说法或继续补充要求。"
        return PhaseDecision(
            RuntimeStatus.FAILED,
            extra_patch={"finished_reason": message, "messages": [message]},
            result_tag="no_progress",
        )

    # --- default: replan --------------------------------------------------
    unfinished = [item for item in outcomes if not item.satisfied]
    logger.debug("replanning: %d/%d tasks unsatisfied", len(unfinished), len(outcomes))
    return PhaseDecision(
        RuntimeStatus.REPLANNING,
        extra_patch={"replanning": True},
        result_tag="replan",
    )


def check_goal_satisfied(
    plan_payload: Mapping[str, Any],
    profile_rows: Mapping[str, Mapping[str, Any]],
    *,
    artifacts: Any = None,
    task_id: str = "",
) -> bool:
    """Return whether the done-condition in *plan_payload* is met.

    Wraps :func:`completion.evaluate` with safe defaults for missing or
    invalid conditions.
    """

    condition_raw = plan_payload.get("goal_satisfied_when")
    if not condition_raw:
        return False
    probe = StoreArtifactProbe(artifacts, task_id) if artifacts is not None else None
    try:
        return bool(
            evaluate(
                DoneCondition.model_validate(condition_raw),
                CompletionContext(artifacts=probe, profile=profile_rows),
            )
        )
    except ValueError:
        return False


__all__ = [
    "PhaseDecision",
    "check_goal_satisfied",
    "decide_next_phase",
]
