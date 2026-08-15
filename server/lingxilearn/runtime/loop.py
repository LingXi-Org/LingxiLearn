"""The constrained autonomous loop.

    START → interpret_goal → orchestrate → dispatch → observe
          → update_state → evaluate_goal
    evaluate_goal ──(runtime_status only)──> orchestrate | await_user | END
    await_user → orchestrate

This is the only graph in the system, and it is the whole reason the routing
tables are gone.  Read the edges: not one of them names an agent, a capability,
or a subject.  They encode the *shape of a loop* — plan, act, observe, learn,
decide whether to go again — and the conditional edge branches on
``runtime_status`` alone.

What runs inside ``dispatch`` is computed at run time from the learner's
profile via ``candidates`` → ``orchestrator`` → ``skill_registry``.  Adding a
capability, a skill, or a subject changes data; it never changes this file.
"""

from __future__ import annotations

import logging
import asyncio
from datetime import UTC, datetime
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Annotated, Any, TypedDict

from lingxigraph import END, START, Runtime, StateGraph, interrupt

from ..state.gain import ProfileView
from ..state.capabilities import info
from ..state.session_state import (
    TERMINAL_STATUSES,
    Goal,
    GoalStack,
    RuntimeStatus,
)
from ..store.runtime_state import RuntimeStateRepository
from . import goal_interpreter, orchestrator
from .candidates import WorldState
from .completion import CompletionContext, StoreArtifactProbe, evaluate
from .contracts import Cost, DoneCondition, OrchestrationPlan, PlannedTask, TaskOutcome
from .dispatch import DispatchDeps, Dispatcher
from .guardrails import Budget, apply_hold_policy, check_plan, check_replan, degrade_message
from .state_updater import StateUpdater
from .trace import DecisionRecord, DecisionTracer, summarise_profile

logger = logging.getLogger(__name__)

GRAPH_NAME = "lingxilearn-runtime-loop"
GRAPH_VERSION = "1.0.0"
DEFAULT_DELIVERY_ORDER = ("lesson-intro", "visual", "lecture-deck", "quiz")


def _append(left: list[Any], right: list[Any]) -> list[Any]:
    return [*left, *right]


class LoopState(TypedDict, total=False):
    """The loop's own bookkeeping. Learner state lives in the four tables."""

    learner_id: str
    task_id: str
    utterance: str
    runtime_status: str
    step: int
    goal: dict[str, Any]
    plan: dict[str, Any]
    budget: dict[str, Any]
    outcomes: Annotated[list[dict[str, Any]], _append]
    messages: Annotated[list[str], _append]
    last_decision_id: str
    replanning: bool
    user_message: dict[str, Any]
    finished_reason: str
    background_pending: bool


class LoopDeps:
    """Everything the loop needs from the service, injected once per run."""

    def __init__(
        self,
        *,
        runtime_state: RuntimeStateRepository,
        learner_id: str,
        task_id: str,
        model: Any = None,
        settings: Any = None,
        artifacts: Any = None,
        registry: Any = None,
        pack: Any = None,
        execution_id: str = "",
        emit: Any = None,
        confirmed_actions: frozenset[str] = frozenset(),
        prior_results: Mapping[str, Any] | None = None,
        prior_artifacts: Sequence[str] = (),
        schedule_background: Any = None,
        board_lock: asyncio.Lock | None = None,
    ) -> None:
        self.runtime_state = runtime_state
        self.learner_id = learner_id
        self.task_id = task_id
        self.model = model
        self.settings = settings
        self.artifacts = artifacts
        self.registry = registry
        self.pack = pack
        self.execution_id = execution_id
        self.emit = emit
        self.confirmed_actions = confirmed_actions
        self.prior_results = dict(prior_results or {})
        self.prior_artifacts = tuple(prior_artifacts)
        self.schedule_background = schedule_background
        self.board_lock = board_lock
        self.updater = StateUpdater(runtime_state)
        self.tracer = DecisionTracer(
            runtime_state,
            learner_id=learner_id,
            task_id=task_id,
            execution_id=execution_id,
            emit=emit,
        )


async def _world(
    deps: LoopDeps, goal: Goal, *, dispatcher: Dispatcher | None
) -> tuple[WorldState, dict[str, Mapping[str, Any]]]:
    """Read the learner's current state into the shape the scorer needs."""

    rows = await deps.runtime_state.profile_for(deps.learner_id)
    by_id = {str(row["knowledge_point_id"]): row for row in rows}

    point = goal.knowledge_points[0] if goal.knowledge_points else ""
    target_row = by_id.get(point)
    target = (
        ProfileView.from_row(_as_view_row(target_row))
        if target_row
        else ProfileView.unseen(point or goal.topic, goal.topic)
    )

    # Prefer what the profile records; fall back to what a prerequisite
    # analysis produced this run but has not been folded into the profile yet.
    prerequisite_ids = list(target.prerequisites)
    if not prerequisite_ids:
        analysed = (deps.prior_results.get("prerequisites") or {}).get("prerequisites") or []
        prerequisite_ids = [str(item.get("id") or "") for item in analysed]
    prerequisites = tuple(
        ProfileView.from_row(_as_view_row(by_id[pid]))
        if pid in by_id
        else ProfileView.unseen(pid)
        for pid in prerequisite_ids
        if pid
    )

    artifacts = frozenset(
        dispatcher.produced_artifacts if dispatcher else deps.prior_artifacts
    )
    results = dispatcher.results if dispatcher else deps.prior_results
    return (
        WorldState(
            target=target,
            prerequisites=prerequisites,
            due_for_review=tuple(
                ProfileView.from_row(_as_view_row(row))
                for row in rows
                if float((row.get("system") or {}).get("review_priority") or 0.0) >= 0.6
            ),
            requested_capabilities=frozenset(),
            artifacts=artifacts,
            has_open_quiz="quiz" in artifacts and "grading" not in results,
            has_ungraded_submission=bool(results.get("pending_submission")),
            open_questions=len(target_row.get("my_questions") or []) if target_row else 0,
            goal_type=goal.goal_type,
            interview_completed="learner_interview" in results,
        ),
        by_id,
    )


def _as_view_row(row: Mapping[str, Any]) -> Any:
    """Adapt the repository's nested dict to the flat shape ``ProfileView`` reads."""

    system = dict(row.get("system") or {})
    return type(
        "Row",
        (),
        {
            "knowledge_point_id": row.get("knowledge_point_id"),
            "knowledge_point": row.get("knowledge_point"),
            "mastery": row.get("mastery"),
            "learning_state": row.get("learning_state"),
            "progress": row.get("progress"),
            "confidence": system.get("confidence"),
            "evidence_count": system.get("evidence_count"),
            "misconceptions": system.get("misconceptions"),
            "prerequisites": system.get("prerequisites"),
            "difficulty": system.get("difficulty"),
            "review_priority": system.get("review_priority"),
            "stability": system.get("stability"),
            "review_due_at": row.get("review_due_at"),
            "last_studied_at": row.get("last_studied_at"),
        },
    )()


def build_loop(deps: LoopDeps, *, checkpointer: Any = None, store: Any = None) -> Any:
    """Compile the runtime loop.

    Every node below is domain-agnostic. ``dispatch`` is the single execution
    node; it resolves capability → skill → provider per task at run time.
    """

    dispatcher = Dispatcher(
        DispatchDeps(
            runtime_state=deps.runtime_state,
            learner_id=deps.learner_id,
            task_id=deps.task_id,
            goal=Goal(goal_type="learn", topic=""),
            skills=[],
            model=deps.model,
            settings=deps.settings,
            artifacts=deps.artifacts,
            registry=deps.registry,
            pack=deps.pack,
            emit=deps.emit,
        )
    )
    dispatcher.seed_results(deps.prior_results)
    dispatcher.seed_artifacts(deps.prior_artifacts)
    # The service supplies one task-scoped lock shared with sidecars and
    # delivery acknowledgements. Unit callers may omit it and get a local
    # lock, preserving the loop's standalone contract.
    board_lock = deps.board_lock or asyncio.Lock()

    async def interpret_goal(state: LoopState, runtime: Runtime[Any]) -> dict[str, Any]:
        if deps.emit is not None:
            deps.emit("agent.status", {"text": "已收到你的学习目标，正在准备学习安排。", "phase": "interpret_goal"})
            # The first learner-facing acknowledgement must not wait for goal
            # interpretation or any artifact provider.  In particular, a
            # lesson/visual/deck provider may take minutes, while the learner
            # should see that the companion is present immediately.
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
                await deps.runtime_state.set_runtime_status(
                    deps.task_id, RuntimeStatus.COMPLETED
                )
                return {
                    "runtime_status": str(RuntimeStatus.COMPLETED),
                    "finished_reason": "没有待处理的学习目标",
                }
            await deps.runtime_state.set_runtime_status(
                deps.task_id, RuntimeStatus.PLANNING
            )
            return {"goal": current.to_dict(), "runtime_status": str(RuntimeStatus.PLANNING)}

        try:
            goal = await goal_interpreter.interpret(
                utterance=utterance,
                model=deps.model,
                profile_rows=rows,
                runtime=runtime,
                current_goal=stack.current(),
            )
        except goal_interpreter.GoalInterpretationUnavailable as exc:
            await deps.runtime_state.set_runtime_status(deps.task_id, RuntimeStatus.FAILED)
            return {
                "runtime_status": str(RuntimeStatus.FAILED),
                "finished_reason": str(exc),
                "messages": ["目标识别失败，本轮没有执行任何学习技能。"],
            }
        operation = goal_interpreter.apply_to_stack(stack, goal)
        await deps.runtime_state.apply_stack_operation(deps.task_id, operation)
        await deps.runtime_state.set_runtime_status(deps.task_id, RuntimeStatus.PLANNING)
        if deps.emit is not None:
            deps.emit(f"goal.{operation.op}ed", {"goal": goal.to_dict(), "op": operation.op})
        return {"goal": goal.to_dict(), "runtime_status": str(RuntimeStatus.PLANNING)}

    async def orchestrate(state: LoopState, runtime: Runtime[Any]) -> dict[str, Any]:
        # The plan list is the user-facing representation of this phase.  Do
        # not expose a generic control-plane "replanning" banner.
        # A replan enters this node in REPLANNING. Persist the explicit
        # REPLANNING -> PLANNING transition before choosing the next action so
        # the table follows the same closed state machine as the checkpoint.
        await deps.runtime_state.set_runtime_status(deps.task_id, RuntimeStatus.PLANNING)
        goal = Goal.from_dict(state.get("goal") or {})
        budget = Budget.from_dict(state.get("budget"))
        interjections = await deps.runtime_state.drain_interjections(deps.task_id)
        latest_message = interjections[-1] if interjections else {}
        if latest_message:
            dispatcher.retarget(user_message=latest_message)
        skills = await deps.runtime_state.list_skills(
            learner_id=deps.learner_id, enabled_only=True
        )
        dispatcher.retarget(goal=goal, skills=skills)

        if state.get("replanning"):
            blocked = check_replan(budget)
            if blocked is not None:
                await deps.runtime_state.save_budget(deps.task_id, budget.to_dict())
                await deps.runtime_state.set_runtime_status(
                    deps.task_id, RuntimeStatus.FAILED
                )
                return {
                    "runtime_status": str(RuntimeStatus.FAILED),
                    "finished_reason": blocked.detail,
                    "messages": [blocked.detail],
                }
            budget.spend_replan()

        world, profile_rows = await _world(deps, goal, dispatcher=dispatcher)
        board = await deps.runtime_state.get_board(deps.task_id)
        board.setdefault("holds", {})
        board.setdefault("delivery", [])
        if not board.get("order"):
            board["order"] = list(DEFAULT_DELIVERY_ORDER)
        board.setdefault("cursor", 0)
        board["produced_order"] = [
            str(item.get("artifact")) for item in board["delivery"] if item.get("artifact")
        ]
        if latest_message:
            requested = set(world.requested_capabilities)
            requested.update(str(item) for item in latest_message.get("requested_capabilities") or [])
            if any(word in str(latest_message.get("message") or "") for word in ("课件", "幻灯片", "讲义")):
                requested.add("content.deck")
            if any(word in str(latest_message.get("message") or "") for word in ("解释", "回答", "为什么")):
                requested.add("dialog.answer")
            world = replace(world, requested_capabilities=frozenset(requested), awaiting_user_reply=True)
        produced = await orchestrator.plan(
            goal=goal,
            world=world,
            skills=skills,
            budget=budget,
            model=deps.model,
            runtime=runtime,
            user_message=latest_message,
            board=board,
        )
        produced.holds = apply_hold_policy(
            produced.holds,
            board,
            budget,
            goal_satisfied=bool(world.target.mastery >= 1.0),
        )
        requested_order = [str(item) for item in produced.delivery_order if str(item) in {"lesson-intro", "visual", "lecture-deck", "quiz"}]
        board["order"] = requested_order + [item for item in board.get("order", []) if item not in requested_order]
        revision_tasks: list[PlannedTask] = []
        for decision in produced.holds:
            if decision.action != "revise":
                continue
            held = board["holds"].get(decision.task_key)
            if not held:
                continue
            revision_number = int(held.get("revisions") or 0) + 1
            capability = str(held.get("capability") or "")
            revision_tasks.append(
                PlannedTask(
                    id=f"revision-{decision.task_key.replace(':', '-')}-{revision_number}",
                    capability=capability,
                    knowledge_point_id=str(held.get("knowledge_point_id") or ""),
                    inputs={
                        "revision": {
                            "instruction": decision.instruction,
                            "artifact": (held.get("artifacts") or [""])[0],
                            "of_task": decision.task_key,
                            "number": revision_number,
                        }
                    },
                    done_when=DoneCondition(
                        kind="artifact_valid",
                        artifact=str((held.get("artifacts") or [""])[0]),
                    ),
                    rationale=decision.instruction,
                    estimated_cost=Cost(
                        heavy_artifact=True,
                        blocking=False,
                        critical_path=False,
                        parallel_safe=True,
                    ),
                    expected_learning_gain=0.0,
                )
            )
        if revision_tasks:
            produced.tasks = revision_tasks + produced.tasks
        for decision in produced.holds:
            if decision.action != "close":
                continue
            held = board["holds"].pop(decision.task_key, None)
            if not held:
                continue
            if deps.emit is not None:
                deps.emit(
                    "node.completed",
                    {
                        "task_id": held.get("task_id") or decision.task_key,
                        "task_key": decision.task_key,
                        "capability": held.get("capability") or "",
                        "provider": held.get("provider") or "",
                        "status": "completed",
                        "satisfied": True,
                        "held": False,
                        "detail": held.get("detail") or "",
                    },
                )
            for artifact in held.get("artifacts") or []:
                artifact = str(artifact)
                if artifact not in board["order"]:
                    board["order"].append(artifact)
                if not any(item.get("artifact") == artifact for item in board["delivery"]):
                    entry = {"artifact": artifact, "task_key": decision.task_key, "title": held.get("detail") or artifact, "sequence": 0, "state": "queued", "closed_at": datetime.now(UTC).isoformat()}
                    target_position = board["order"].index(artifact)
                    position = next(
                        (
                            index
                            for index, item in enumerate(board["delivery"])
                            if str(item.get("artifact")) in board["order"]
                            and board["order"].index(str(item.get("artifact"))) > target_position
                        ),
                        len(board["delivery"]),
                    )
                    board["delivery"].insert(position, entry)
                    for index, item in enumerate(board["delivery"], start=1):
                        item["sequence"] = index
                    if deps.emit is not None:
                        deps.emit("delivery.queued", {"artifact": artifact, "task_key": decision.task_key})
        if produced.holds and not produced.tasks:
            produced.awaits_user = True
        cursor = int(board.get("cursor") or 0)
        if cursor < len(board["delivery"]):
            was_unlocked = board["delivery"][cursor].get("state") == "unlocked"
            board["delivery"][cursor]["state"] = "unlocked"
            if deps.emit is not None and not was_unlocked:
                deps.emit("delivery.unlocked", {"artifact": board["delivery"][cursor].get("artifact"), "cursor": cursor})
        await deps.runtime_state.save_board(deps.task_id, board)
        verdict = check_plan(
            produced,
            goal=goal,
            budget=budget,
            skills=skills,
            requested_capabilities=world.requested_capabilities,
            confirmed_actions=deps.confirmed_actions,
        )
        if verdict.findings:
            deps.tracer.guardrail_triggered(verdict)
            if deps.emit is not None:
                deps.emit("agent.status", {"text": degrade_message(verdict.findings), "phase": "guardrail"})

        step = await deps.tracer.next_step()
        record = DecisionRecord(
            step=step,
            goal=goal,
            candidates=produced.candidates_considered,
            plan=produced,
            guardrails=verdict,
            budget=budget,
            profile_before=summarise_profile(list(profile_rows.values())),
            replan_of=state.get("last_decision_id") if state.get("replanning") else None,
        )
        stored = await deps.tracer.record(record)
        if deps.schedule_background is not None:
            await deps.schedule_background(
                "plan.present",
                {
                    "decision_id": str(stored["id"]),
                    "tasks": [
                        {
                            "id": task.id,
                            "capability": task.capability,
                            "rationale": task.rationale,
                            "depends_on": list(task.depends_on),
                        }
                        for task in produced.tasks
                    ],
                },
            )

        if verdict.fatal:
            message = degrade_message(verdict.findings)
            persisted_plan = {
                **produced.to_dict(),
                "allowed": [task.id for task in verdict.allowed_tasks],
            }
            await deps.runtime_state.save_plan(
                deps.task_id, persisted_plan, budget=budget.to_dict()
            )
            await deps.runtime_state.set_runtime_status(
                deps.task_id, RuntimeStatus.FAILED
            )
            return {
                "runtime_status": str(RuntimeStatus.FAILED),
                "finished_reason": message,
                "messages": [message],
                "budget": budget.to_dict(),
                "last_decision_id": str(stored["id"]),
                "step": step,
            }

        awaiting = produced.awaits_user and not verdict.allowed_tasks
        if produced.negotiation:
            awaiting = True

        status = (
            RuntimeStatus.WAITING_FOR_USER
            if awaiting
            else (
                RuntimeStatus.EXECUTING
                if verdict.allowed_tasks
                else RuntimeStatus.WAITING_FOR_USER
            )
        )
        messages = [produced.negotiation] if produced.negotiation else []
        if not verdict.allowed_tasks and verdict.findings and not awaiting:
            messages.append(degrade_message(verdict.findings))

        persisted_plan = {
            **produced.to_dict(),
            "allowed": [task.id for task in verdict.allowed_tasks],
        }
        await deps.runtime_state.save_plan(
            deps.task_id, persisted_plan, budget=budget.to_dict()
        )
        await deps.runtime_state.set_runtime_status(deps.task_id, status)

        return {
            "runtime_status": str(status),
            "plan": persisted_plan,
            "budget": budget.to_dict(),
            "last_decision_id": str(stored["id"]),
            "step": step,
            "messages": messages,
            "replanning": False,
        }

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
        for tier in produced.tiers():
            ready = [task for task in tier if task.id in allowed]
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
                and (
                    task.estimated_cost.heavy_artifact
                    or not task.estimated_cost.blocking
                )
                and deps.schedule_background is not None
            ]
            if background:
                background_pending = True
            for task in background:
                inputs = dict(task.inputs)
                revision = inputs.get("revision") if isinstance(inputs.get("revision"), Mapping) else {}
                inputs["__runtime"] = {
                    "task_key": str(revision.get("of_task") or f"{int(state.get('step') or 0)}:{task.id}"),
                    "task_id": task.id,
                    "step": int(state.get("step") or 0),
                    "capability": task.capability,
                    "knowledge_point_id": task.knowledge_point_id,
                    "artifacts": [task.done_when.artifact] if task.done_when.artifact else [],
                    "done_when": task.done_when.model_dump(mode="json"),
                }
                await deps.schedule_background(task.capability, inputs)
            ready = [task for task in ready if task not in background]
            safe = [task for task in ready if task.estimated_cost.parallel_safe and bool(getattr(deps.settings, "agent_parallel_dispatch", True))]
            serial = [task for task in ready if task not in safe]
            results = []
            if safe:
                gathered = await asyncio.gather(*(dispatcher.run(task, profile=profile_rows, budget=budget) for task in safe), return_exceptions=True)
                results.extend(item if isinstance(item, TaskOutcome) else TaskOutcome(task_id=safe[index].id, capability=safe[index].capability, status="failed", detail=f"{type(item).__name__}: {item}") for index, item in enumerate(gathered))
            for task in serial:
                results.append(await dispatcher.run(task, profile=profile_rows, budget=budget))
            for outcome in results:
                outcomes.append(outcome)
                budget.spend_step(heavy=outcome.heavy, tokens=outcome.tokens_used, wall_ms=outcome.duration_ms)
                if outcome.held:
                    async with board_lock:
                        board = await deps.runtime_state.get_board(deps.task_id)
                        board.setdefault("holds", {})
                        planned = next(
                            (item for item in produced.tasks if item.id == outcome.task_id),
                            None,
                        )
                        revision = (
                            planned.inputs.get("revision")
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
                        "node.completed" if outcome.status in {"completed", "incomplete"} else "node.failed",
                        {
                            "task_id": outcome.task_id,
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
        await deps.runtime_state.set_runtime_status(
            deps.task_id, RuntimeStatus.OBSERVING
        )

        return {
            "runtime_status": str(RuntimeStatus.OBSERVING),
            "outcomes": [item.to_dict() for item in outcomes],
            "budget": budget.to_dict(),
            "messages": messages,
            "background_pending": background_pending,
        }

    async def observe(state: LoopState, _runtime: Runtime[Any]) -> dict[str, Any]:
        """Evidence was appended by the providers; this is the transition point."""

        if str(state.get("runtime_status")) not in {
            str(RuntimeStatus.OBSERVING),
            str(RuntimeStatus.EXECUTING),
        }:
            return {}
        await deps.runtime_state.set_runtime_status(deps.task_id, RuntimeStatus.UPDATING)
        return {"runtime_status": str(RuntimeStatus.UPDATING)}

    async def update_state(state: LoopState, _runtime: Runtime[Any]) -> dict[str, Any]:
        if deps.emit is not None:
            deps.emit("agent.status", {"text": "正在更新对你的掌握度判断…", "phase": "update_state"})
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

    async def evaluate_goal(state: LoopState, _runtime: Runtime[Any]) -> dict[str, Any]:
        """Did the round achieve the goal, or does the next one differ?"""

        status = str(state.get("runtime_status"))
        if status in {str(RuntimeStatus.FAILED), str(RuntimeStatus.COMPLETED)}:
            return {}
        if status == str(RuntimeStatus.WAITING_FOR_USER):
            return {}

        goal = Goal.from_dict(state.get("goal") or {})
        outcomes = [TaskOutcome.model_validate(item) for item in state.get("outcomes") or []]
        unfinished = [item for item in outcomes if not item.satisfied]

        plan_payload = dict(state.get("plan") or {})
        condition = plan_payload.get("goal_satisfied_when")
        profile_rows = {
            str(row["knowledge_point_id"]): row
            for row in await deps.runtime_state.profile_for(deps.learner_id)
        }
        probe = (
            StoreArtifactProbe(deps.artifacts, deps.task_id)
            if deps.artifacts is not None
            else None
        )
        satisfied = False
        if condition:
            try:
                satisfied = bool(
                    evaluate(
                        DoneCondition.model_validate(condition),
                        CompletionContext(artifacts=probe, profile=profile_rows),
                    )
                )
            except ValueError:
                satisfied = False

        if satisfied:
            stack = await deps.runtime_state.goal_stack(deps.task_id)
            operation = stack.pop(reason="目标达成", goal_id=goal.id)
            await deps.runtime_state.apply_stack_operation(deps.task_id, operation)
            if deps.emit is not None:
                deps.emit("goal.popped", {"goal_id": goal.id})
            remaining = stack.current()
            if remaining is None:
                await deps.runtime_state.set_runtime_status(
                    deps.task_id, RuntimeStatus.COMPLETED
                )
                return {
                    "runtime_status": str(RuntimeStatus.COMPLETED),
                    "finished_reason": "目标已达成",
                }
            await deps.runtime_state.set_runtime_status(
                deps.task_id, RuntimeStatus.REPLANNING
            )
            return {
                "runtime_status": str(RuntimeStatus.REPLANNING),
                "goal": remaining.to_dict(),
                "replanning": True,
            }

        # Background artifact sidecars are deliberately allowed to outlive
        # this graph turn. Keep the task in the learner-facing waiting state
        # until those sidecars settle; ``_sweep_holds`` resumes the graph with
        # a board-driven holds decision instead of treating an empty
        # foreground outcome as a failure.
        if bool(state.get("background_pending")):
            await deps.runtime_state.set_runtime_status(
                deps.task_id, RuntimeStatus.WAITING_FOR_USER
            )
            return {
                "runtime_status": str(RuntimeStatus.WAITING_FOR_USER),
                "messages": [],
            }

        # A failed or empty round has no new evidence to justify another trip
        # through the graph.  Returning a terminal status here prevents a
        # provider outage from becoming an invisible re-planning loop.
        if not outcomes or all(item.status in {"failed", "skipped", "blocked"} for item in outcomes[-3:]):
            message = "本轮没有产生新的学习结果，已暂停自动编排，请换一种说法或继续补充要求。"
            await deps.runtime_state.set_runtime_status(deps.task_id, RuntimeStatus.FAILED)
            return {
                "runtime_status": str(RuntimeStatus.FAILED),
                "finished_reason": message,
                "messages": [message],
            }

        # Either a task did not reach its done_when, or the goal is not yet
        # met: both mean the next round is decided from a state this round
        # changed. That is the replan the acceptance criteria want visible.
        logger.debug(
            "replanning: %d/%d tasks unsatisfied", len(unfinished), len(outcomes)
        )
        await deps.runtime_state.set_runtime_status(
            deps.task_id, RuntimeStatus.REPLANNING
        )
        return {"runtime_status": str(RuntimeStatus.REPLANNING), "replanning": True}

    async def await_user(state: LoopState, _runtime: Runtime[Any]) -> dict[str, Any]:
        if checkpointer is None:
            return {"runtime_status": str(RuntimeStatus.WAITING_FOR_USER)}
        payload = interrupt(
            {
                "kind": "user_message",
                "task_id": deps.task_id,
                "messages": list(state.get("messages") or []),
                "plan": state.get("plan") or {},
            }
        )
        value = payload if isinstance(payload, dict) else {"message": str(payload)}
        dispatcher.retarget(user_message=value)
        # interrupt() resumes here from a persisted WAITING_FOR_USER state.
        await deps.runtime_state.set_runtime_status(deps.task_id, RuntimeStatus.PLANNING)
        return {
            "user_message": value,
            "utterance": str(value.get("message") or ""),
            "runtime_status": str(RuntimeStatus.PLANNING),
        }

    def route(state: LoopState) -> str:
        """The loop's only branch, and it reads one field: the run's own phase.

        No domain concept appears here. What to *do* was decided in
        ``orchestrate``; this decides only whether to go round again, wait, or
        stop.
        """

        status = RuntimeStatus(str(state.get("runtime_status") or RuntimeStatus.PLANNING))
        if status in TERMINAL_STATUSES:
            return "end"
        if status is RuntimeStatus.WAITING_FOR_USER:
            return "await_user"
        return "orchestrate"

    builder = StateGraph(LoopState, name=GRAPH_NAME, version=GRAPH_VERSION)
    builder.add_node("interpret_goal", interpret_goal)
    builder.add_node("orchestrate", orchestrate)
    builder.add_node("dispatch", dispatch)
    builder.add_node("observe", observe)
    builder.add_node("update_state", update_state)
    builder.add_node("evaluate_goal", evaluate_goal)
    builder.add_node("await_user", await_user)

    builder.add_edge(START, "interpret_goal")
    builder.add_edge("interpret_goal", "orchestrate")
    builder.add_edge("orchestrate", "dispatch")
    builder.add_edge("dispatch", "observe")
    builder.add_edge("observe", "update_state")
    builder.add_edge("update_state", "evaluate_goal")
    builder.add_conditional_edges(
        "evaluate_goal",
        route,
        {"orchestrate": "orchestrate", "await_user": "await_user", "end": END},
    )
    # With a checkpointer, await_user raises an interrupt and the run resumes
    # into the next planning round. Without one there is nothing to resume into,
    # so waiting means ending: the service starts a fresh invocation when the
    # learner replies. Falling through to orchestrate here would spin.
    builder.add_edge("await_user", "orchestrate" if checkpointer is not None else END)

    options: dict[str, Any] = {"checkpointer": checkpointer}
    if store is not None:
        options["store"] = store
    return builder.compile(**options)


async def _finalise_trace(
    deps: LoopDeps,
    decision_id: str,
    state: LoopState,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    """Attach the after-profile and the task outcomes to this round's decision."""

    outcomes = [TaskOutcome.model_validate(item) for item in state.get("outcomes") or []]
    await deps.runtime_state.update_decision_outcome(
        decision_id,
        {
            "tasks": [item.to_dict() for item in outcomes],
            "profile_after": summarise_profile(rows),
        },
    )


def initial_state(
    *, learner_id: str, task_id: str, utterance: str, budget: Mapping[str, Any]
) -> LoopState:
    return LoopState(
        learner_id=learner_id,
        task_id=task_id,
        utterance=utterance,
        runtime_status=str(RuntimeStatus.PLANNING),
        step=0,
        goal={},
        plan={},
        budget=dict(budget),
        outcomes=[],
        messages=[],
        last_decision_id="",
        replanning=False,
        user_message={},
        finished_reason="",
    )


__all__ = [
    "GRAPH_NAME",
    "GRAPH_VERSION",
    "GoalStack",
    "LoopDeps",
    "LoopState",
    "build_loop",
    "initial_state",
]
