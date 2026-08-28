"""The ``dispatch`` node: execute the validated plan, tier by tier.

Business logic extracted from the historical ``loop.py`` monolith; the
node is wired into the graph by :func:`lingxilearn.runtime.graph.build_loop`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from lingxigraph import Runtime

from ...state.agent_task_state import Goal, RuntimeStatus
from ...state.capabilities import info
from ..contracts import OrchestrationPlan, PlannedTask, TaskOutcome
from ..guardrails import Budget

if TYPE_CHECKING:
    from ..graph import LoopDeps, LoopState


def build_dispatch_node(deps: LoopDeps, *, dispatcher: Any, board_lock: asyncio.Lock):
    """Build the ``dispatch`` graph node bound to *deps* and *dispatcher*."""

    async def dispatch(state: LoopState, runtime: Runtime[Any]) -> dict[str, Any]:
        if str(state.get("runtime_status")) != str(RuntimeStatus.EXECUTING):
            return {}

        goal = Goal.from_dict(state.get("goal") or {})
        budget = Budget.from_dict(state.get("budget"))
        plan_payload = dict(state.get("plan") or {})
        allowed = set(plan_payload.get("allowed") or [])
        produced = OrchestrationPlan.model_validate(plan_payload)

        profile_rows = {
            str(row["knowledge_point_id"]): row
            for row in await deps.runtime_state.profile_for(deps.learner_id)
        }
        dispatcher.retarget(goal=goal)
        # Providers emit learner-facing output through ProviderContext.runtime.
        # Binding it here is essential: the dispatcher is created before the
        # compiled graph supplies its per-run runtime object.
        dispatcher.bind_runtime(runtime, emit=deps.emit)

        outcomes: list[TaskOutcome] = []
        messages: list[str] = []
        background_pending = False

        # Artifact tasks often depend on a conversational teaching step for
        # planning purposes, but their providers only need the goal and the
        # learner profile.  Queue independent heavy artifacts immediately so
        # a slow/failed explanation cannot leave the actual deliverables in
        # ``queued`` forever.  Heavy-on-heavy dependencies remain ordered and
        # are picked up by the normal tier loop after their prerequisite.
        queued_background_ids: set[str] = set()
        heavy_ids = {
            task.id
            for task in produced.tasks
            if task.id in allowed
            and task.estimated_cost.heavy_artifact
            and not task.estimated_cost.critical_path
        }

        async def queue_background(task: PlannedTask) -> None:
            nonlocal background_pending
            if task.id in queued_background_ids:
                return
            inputs = dict(task.inputs)
            revision: Mapping[str, Any] = (
                inputs["revision"] if isinstance(inputs.get("revision"), Mapping) else {}
            )
            inputs["__runtime"] = {
                "task_key": str(
                    revision.get("of_task") or f"{int(state.get('step') or 0)}:{task.id}"
                ),
                "task_id": task.id,
                "step": int(state.get("step") or 0),
                "capability": task.capability,
                "knowledge_point_id": task.knowledge_point_id,
                "artifacts": [task.done_when.artifact] if task.done_when.artifact else [],
                "done_when": task.done_when.model_dump(mode="json"),
            }
            await deps.schedule_background(task.capability, inputs)
            queued_background_ids.add(task.id)
            background_pending = True

        for task in produced.tasks:
            if (
                task.id in heavy_ids
                and not any(dep in heavy_ids for dep in task.depends_on)
                and deps.schedule_background is not None
                and deps.work_ledger is None
            ):
                await queue_background(task)

        for tier in produced.tiers():
            ready = [
                task for task in tier if task.id in allowed and task.id not in queued_background_ids
            ]
            if budget.exhausted() is not None:
                break
            # Heavy artifacts are deliberately detached from the learner's
            # turn even when their provider declares itself blocking.  The
            # latter describes provider semantics, not whether the chat must
            # wait for it.  Waiting here made a single visual/deck generation
            # hold the whole conversation for several minutes.
            background = [
                task
                for task in ready
                if not task.estimated_cost.critical_path
                and (task.estimated_cost.heavy_artifact or not task.estimated_cost.blocking)
                and deps.schedule_background is not None
                and deps.work_ledger is None
            ]
            if background:
                background_pending = True
            for task in background:
                await queue_background(task)
            ready = [task for task in ready if task not in background]
            safe = [
                task
                for task in ready
                if task.estimated_cost.parallel_safe
                and bool(getattr(deps.settings, "agent_parallel_dispatch", True))
            ]
            serial = [task for task in ready if task not in safe]
            results: list[TaskOutcome] = []
            # Start independent safe work immediately, but never await that
            # whole batch before the learner-facing serial critical path starts.
            safe_future = (
                asyncio.gather(
                    *(dispatcher.run(task, profile=profile_rows, budget=budget) for task in safe),
                    return_exceptions=True,
                )
                if safe
                else None
            )
            try:
                for task in serial:
                    results.append(await dispatcher.run(task, profile=profile_rows, budget=budget))
            finally:
                # Same-tier tasks have no dependency edges between them. Join
                # before the next tier so dependency semantics remain intact.
                if safe_future is not None:
                    gathered = await safe_future
                    results.extend(
                        item
                        if isinstance(item, TaskOutcome)
                        else TaskOutcome(
                            task_id=safe[index].id,
                            capability=safe[index].capability,
                            status="failed",
                            detail=f"{type(item).__name__}: {item}",
                        )
                        for index, item in enumerate(gathered)
                    )
            for outcome in results:
                outcomes.append(outcome)
                budget.spend_step(
                    heavy=outcome.heavy, tokens=outcome.tokens_used, wall_ms=outcome.duration_ms
                )
                if outcome.held:
                    async with board_lock:
                        board = await deps.runtime_state.get_board(deps.task_id)
                        board.setdefault("holds", {})
                        planned = next(
                            (item for item in produced.tasks if item.id == outcome.task_id),
                            None,
                        )
                        revision: Mapping[str, Any] = (
                            planned.inputs["revision"]
                            if planned and isinstance(planned.inputs.get("revision"), Mapping)
                            else {}
                        )
                        task_key = str(
                            revision.get("of_task")
                            or f"{int(state.get('step') or 0)}:{outcome.task_id}"
                        )
                        previous = dict(board["holds"].get(task_key) or {})
                        board["holds"][task_key] = {
                            "task_id": previous.get("task_id") or outcome.task_id,
                            "capability": outcome.capability,
                            "provider": outcome.provider,
                            "skill_id": outcome.skill_id,
                            "knowledge_point_id": planned.knowledge_point_id if planned else "",
                            "artifacts": list(outcome.artifacts),
                            "revisions": outcome.revision or int(previous.get("revisions") or 0),
                            "step": int(state.get("step") or 0),
                            "detail": outcome.detail,
                            "opened_at": datetime.now(UTC).isoformat(),
                        }
                        await deps.runtime_state.save_board(deps.task_id, board)
                if deps.emit is not None and not outcome.held:
                    deps.emit(
                        "node.completed"
                        if outcome.status in {"completed", "incomplete"}
                        else "node.failed",
                        {
                            "task_id": outcome.task_id,
                            "node_id": outcome.node_id
                            or next(
                                (
                                    str(item.inputs.get("__runtime_node_id") or "")
                                    for item in produced.tasks
                                    if item.id == outcome.task_id
                                ),
                                "",
                            ),
                            "capability": outcome.capability,
                            "provider": outcome.provider,
                            "status": outcome.status,
                            "satisfied": outcome.satisfied,
                            "detail": outcome.detail,
                            "step": int(state.get("step") or 0),
                        },
                    )
                # Only capabilities explicitly marked conversational may
                # enter the learner-facing message channel. Other writers
                # return reusable teaching content for the exclusive dialog
                # agent instead of speaking in parallel.
                if outcome.learner_message and info(outcome.capability).conversational:
                    messages.append(outcome.learner_message)

        await deps.runtime_state.save_budget(deps.task_id, budget.to_dict())
        return await deps.transition_status(
            state,
            RuntimeStatus.OBSERVING,
            outcomes=[item.to_dict() for item in outcomes],
            round_outcomes=[item.to_dict() for item in outcomes],
            budget=budget.to_dict(),
            messages=messages,
            background_pending=background_pending,
        )

    return dispatch
