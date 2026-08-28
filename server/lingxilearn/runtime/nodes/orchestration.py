"""The ``orchestrate`` node: plan the next round from world state.

Business logic extracted from the historical ``loop.py`` monolith; the
node is wired into the graph by :func:`lingxilearn.runtime.graph.build_loop`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from lingxigraph import Runtime

from ...state.agent_task_state import TERMINAL_STATUSES, Goal, RuntimeStatus
from ...state.gain import ProfileView
from .. import orchestrator
from ..candidates import WorldState, is_direct_question, requests_heavy_artifact
from ..contracts import Cost, DoneCondition, PlannedTask
from ..guardrails import (
    Budget,
    apply_hold_policy,
    check_plan,
    check_replan,
    degrade_message,
)
from ..interactions import InteractionSpec, request_interaction
from ..trace import DecisionRecord, summarise_profile

if TYPE_CHECKING:
    from ..dispatch import Dispatcher
    from ..graph import LoopDeps, LoopState

DEFAULT_DELIVERY_ORDER = ("lesson-intro", "visual", "lecture-deck", "quiz")


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


async def _world(
    deps: LoopDeps, goal: Goal, *, dispatcher: Dispatcher | None
) -> tuple[WorldState, dict[str, Mapping[str, Any]]]:
    """Read the learner's current state into the shape the scorer needs."""

    rows = await deps.runtime_state.profile_for(deps.learner_id)
    by_id: dict[str, Mapping[str, Any]] = {str(row["knowledge_point_id"]): row for row in rows}

    point = goal.knowledge_points[0] if goal.knowledge_points else ""
    target_row = by_id.get(point)
    target = (
        ProfileView.from_row(_as_view_row(target_row))
        if target_row
        else ProfileView.unseen(point or goal.topic, goal.topic)
    )
    target_views = tuple(
        ProfileView.from_row(_as_view_row(by_id[knowledge_point]))
        if knowledge_point in by_id
        else ProfileView.unseen(knowledge_point, knowledge_point)
        for knowledge_point in goal.knowledge_points
        if knowledge_point
    ) or (target,)

    # Prefer what the profile records; fall back to what a prerequisite
    # analysis produced this run but has not been folded into the profile yet.
    prerequisite_ids = list(target.prerequisites)
    if not prerequisite_ids:
        analysed = (deps.prior_results.get("prerequisites") or {}).get("prerequisites") or []
        prerequisite_ids = [str(item.get("id") or "") for item in analysed]
    prerequisites = tuple(
        ProfileView.from_row(_as_view_row(by_id[pid])) if pid in by_id else ProfileView.unseen(pid)
        for pid in prerequisite_ids
        if pid
    )

    artifacts = frozenset(dispatcher.produced_artifacts if dispatcher else deps.prior_artifacts)
    results = dispatcher.results if dispatcher else deps.prior_results
    direct_question = is_direct_question(goal) and not requests_heavy_artifact(goal)
    open_questions = len(target_row.get("my_questions") or []) if target_row else 0
    if direct_question:
        open_questions = max(open_questions, 1)
    return (
        WorldState(
            target=target,
            targets=target_views,
            prerequisites=prerequisites,
            due_for_review=tuple(
                ProfileView.from_row(_as_view_row(row))
                for row in rows
                if float((row.get("system") or {}).get("review_priority") or 0.0) >= 0.6
            ),
            requested_capabilities=(
                frozenset({"dialog.answer"}) if direct_question else frozenset()
            ),
            artifacts=artifacts,
            has_open_quiz="quiz" in artifacts and "grading" not in results,
            has_ungraded_submission=bool(results.get("pending_submission")),
            open_questions=open_questions,
            goal_type=goal.goal_type,
            interview_completed="learner_interview" in results,
            direct_question=direct_question,
            allow_heavy_artifacts=requests_heavy_artifact(goal),
        ),
        by_id,
    )


def build_orchestrate_node(deps: LoopDeps, *, dispatcher: Dispatcher):
    """Build the ``orchestrate`` graph node bound to *deps* and *dispatcher*."""

    async def orchestrate(state: LoopState, runtime: Runtime[Any]) -> dict[str, Any]:
        # The plan list is the user-facing representation of this phase.  Do
        # not expose a generic control-plane "replanning" banner.
        # Terminal turns have no execution edge.  In particular, a failed
        # interpretation must not re-enter planning through graph scheduling.
        current_status = RuntimeStatus(str(state.get("runtime_status") or ""))
        if current_status in TERMINAL_STATUSES:
            return {"runtime_status": str(current_status)}
        # A replan enters this node in REPLANNING. Persist the explicit
        # REPLANNING -> PLANNING transition before choosing the next action so
        # the table follows the same closed state machine as the checkpoint.
        await deps.transition_status(state, RuntimeStatus.PLANNING)
        goal = Goal.from_dict(state.get("goal") or {})
        budget = Budget.from_dict(state.get("budget"))
        steering = runtime.drain_steering()
        applied_command_ids = [
            command_id
            for event in steering
            if (command_id := str(event.payload.get("command_id") or ""))
        ]
        checkpoint_patch = {"applied_command_ids": applied_command_ids}
        latest_message = (
            dict(steering[-1].payload) if steering else dict(state.get("user_message") or {})
        )
        for event in steering:
            if deps.emit is not None:
                consumed_at = datetime.now(UTC)
                deps.emit(
                    "steer.consumed",
                    {
                        "execution_id": deps.execution_id,
                        "turn_id": str(event.metadata.get("turn_id") or deps.turn_id) or None,
                        "steering_event_id": event.id,
                        "sequence": event.sequence,
                        "kind": event.kind,
                        "safe_point": "orchestrate",
                        "queue_latency_seconds": max(
                            0.0, (consumed_at - event.created_at).total_seconds()
                        ),
                    },
                )
        if not latest_message and str(state.get("utterance") or "").strip():
            latest_message = {"message": str(state["utterance"])}
        if latest_message:
            dispatcher.retarget(user_message=latest_message)
        skills = await deps.runtime_state.list_skills(learner_id=deps.learner_id, enabled_only=True)
        dispatcher.retarget(goal=goal, skills=skills)

        # Reserve the stable decision step before invoking the planner.  The
        # lifecycle event therefore covers model planning latency as well as
        # dispatch/evaluation latency.
        step = await deps.tracer.next_step()
        deps.open_round(step)
        turn_id = ""
        if deps.work_ledger is not None:
            current_turn = await deps.work_ledger.latest_turn(deps.task_id)
            turn_id = str(current_turn.get("id") or "") if current_turn else ""
        if deps.emit is not None:
            deps.emit(
                "round.started",
                {
                    "step": step,
                    "turn_id": turn_id or None,
                    "replanning": bool(state.get("replanning")),
                    "previous_decision_id": state.get("last_decision_id") or None,
                },
            )

        if state.get("replanning"):
            blocked = check_replan(budget)
            if blocked is not None:
                await deps.runtime_state.save_budget(deps.task_id, budget.to_dict())
                patch = await deps.transition_status(
                    state,
                    RuntimeStatus.FAILED,
                    finished_reason=blocked.detail,
                    messages=[blocked.detail],
                )
                deps.close_round(step=step, status=str(RuntimeStatus.FAILED), detail=blocked.detail)
                return patch
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
            requested.update(
                str(item) for item in latest_message.get("requested_capabilities") or []
            )
            if any(
                word in str(latest_message.get("message") or "")
                for word in ("课件", "幻灯片", "讲义")
            ):
                requested.add("content.deck")
            if any(
                word in str(latest_message.get("message") or "")
                for word in ("解释", "回答", "为什么")
            ):
                requested.add("dialog.answer")
            world = replace(
                world, requested_capabilities=frozenset(requested), awaiting_user_reply=True
            )
        try:
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
        except Exception as exc:  # lifecycle must close when planning fails
            deps.close_round(
                step=step,
                status=str(RuntimeStatus.FAILED),
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise
        produced.holds = apply_hold_policy(
            produced.holds,
            board,
            budget,
            goal_satisfied=bool(world.target.mastery >= 1.0),
        )
        requested_order = [
            str(item)
            for item in produced.delivery_order
            if str(item) in {"lesson-intro", "visual", "lecture-deck", "quiz"}
        ]
        board["order"] = requested_order + [
            item for item in board.get("order", []) if item not in requested_order
        ]
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
                    entry = {
                        "artifact": artifact,
                        "task_key": decision.task_key,
                        "title": held.get("detail") or artifact,
                        "sequence": 0,
                        "state": "queued",
                        "closed_at": datetime.now(UTC).isoformat(),
                    }
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
                        deps.emit(
                            "delivery.queued", {"artifact": artifact, "task_key": decision.task_key}
                        )
        if produced.holds and not produced.tasks:
            produced.awaits_user = True
        cursor = int(board.get("cursor") or 0)
        if cursor < len(board["delivery"]):
            was_unlocked = board["delivery"][cursor].get("state") == "unlocked"
            board["delivery"][cursor]["state"] = "unlocked"
            if deps.emit is not None and not was_unlocked:
                deps.emit(
                    "delivery.unlocked",
                    {"artifact": board["delivery"][cursor].get("artifact"), "cursor": cursor},
                )
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
                deps.emit(
                    "agent.status",
                    {"text": degrade_message(verdict.findings), "phase": "guardrail"},
                )

        # When running under the service, mirror the validated plan into the
        # durable ledger before any provider starts. Unit callers without a
        # repository retain the standalone graph contract.
        if deps.work_ledger is not None and produced.tasks:
            turn = await deps.work_ledger.latest_turn(deps.task_id)
            if turn is not None:
                dispatcher.bind_turn(str(turn["id"]))
            if turn is not None:
                candidate_by_id = {
                    item.candidate_id: item for item in produced.candidates_considered
                }
                work_rows: list[dict[str, Any]] = []
                work_ids: dict[str, str] = {}
                for task in produced.tasks:
                    work_id = f"work:{turn['id']}:{step}:{task.id}"
                    work_ids[task.id] = work_id
                    candidate = candidate_by_id.get(task.candidate_id)
                    work_status = (
                        "waiting_confirmation"
                        if task.estimated_cost.irreversible
                        and task.capability not in deps.confirmed_actions
                        else "queued"
                    )
                    work_rows.append(
                        {
                            "id": work_id,
                            "work_key": f"{step}:{task.id}",
                            "candidate_id": task.candidate_id,
                            "capability": task.capability,
                            "skill_id": candidate.skill_id if candidate else "",
                            "skill_version": candidate.skill_version if candidate else "",
                            "skill_checksum": candidate.skill_checksum if candidate else "",
                            "provider": candidate.provider if candidate else "",
                            "knowledge_point_id": task.knowledge_point_id,
                            "input_payload": dict(task.inputs),
                            "idempotency_key": f"{turn['id']}:{step}:{task.id}",
                            "status": work_status,
                            "confirmation_digest": (
                                "sha256:"
                                + hashlib.sha256(
                                    json.dumps(
                                        {
                                            "capability": task.capability,
                                            "knowledge_point_id": task.knowledge_point_id,
                                            "inputs": task.inputs,
                                        },
                                        sort_keys=True,
                                        ensure_ascii=False,
                                        default=str,
                                    ).encode("utf-8")
                                ).hexdigest()
                                if work_status == "waiting_confirmation"
                                else None
                            ),
                            # Reservation is conservative and is released
                            # against actual ProviderResult usage on finish.
                            "reserved_tokens": 1_000,
                            "reserved_heavy": 1 if task.estimated_cost.heavy_artifact else 0,
                            "reserved_wall_ms": 120_000,
                        }
                    )
                dependencies = [
                    (work_ids[task.id], work_ids[dependency])
                    for task in produced.tasks
                    for dependency in task.depends_on
                    if dependency in work_ids
                ]
                durable = await deps.work_ledger.create_work_plan(
                    task_id=deps.task_id,
                    turn_id=turn["id"],
                    expected_revision=int(turn.get("revision") or 0),
                    items=work_rows,
                    dependencies=dependencies,
                    budget=budget.to_dict(),
                )
                if durable is not None and durable.get("budget_exceeded"):
                    message = "本轮预计资源需求超过剩余预算，已停止启动新工作。"
                    patch = await deps.transition_status(
                        state,
                        RuntimeStatus.FAILED,
                        finished_reason=message,
                        messages=[message],
                    )
                    deps.close_round(step=step, status=str(RuntimeStatus.FAILED), detail=message)
                    return {
                        **patch,
                        **checkpoint_patch,
                        "budget": budget.to_dict(),
                        "step": step,
                    }
                if durable is not None:
                    produced = produced.model_copy(
                        update={
                            "tasks": [
                                task.model_copy(
                                    update={
                                        "inputs": {
                                            **task.inputs,
                                            "__work_item_id": work_ids[task.id],
                                        }
                                    }
                                )
                                for task in produced.tasks
                            ]
                        }
                    )
        # Logical task ids are intentionally reused across plan revisions.
        # Attach an execution identity before the plan is traced or dispatched
        # so a later ``t1`` can never overwrite an earlier ``t1`` in the graph.
        if produced.tasks:
            runtime_prefix = deps.execution_id or deps.task_id
            produced = produced.model_copy(
                update={
                    "tasks": [
                        task.model_copy(
                            update={
                                "inputs": {
                                    **task.inputs,
                                    "__runtime_node_id": str(
                                        task.inputs.get("__runtime_node_id")
                                        or task.inputs.get("__work_item_id")
                                        or f"{runtime_prefix}:{step}:{task.id}"
                                    ),
                                    "__runtime_step": step,
                                }
                            }
                        )
                        for task in produced.tasks
                    ]
                }
            )
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
            patch = await deps.transition_status(
                state,
                RuntimeStatus.FAILED,
                finished_reason=message,
                messages=[message],
            )
            deps.close_round(
                step=step,
                decision_id=str(stored["id"]),
                status=str(RuntimeStatus.FAILED),
                detail=message,
            )
            return {
                **patch,
                **checkpoint_patch,
                "budget": budget.to_dict(),
                "last_decision_id": str(stored["id"]),
                "step": step,
            }

        awaiting = produced.awaits_user and not verdict.allowed_tasks
        if produced.negotiation:
            awaiting = True

        # A blocking interaction is persisted and announced; the checkpoint
        # stores only its opaque id.
        pending_interaction: dict[str, Any] | None = None
        if awaiting and isinstance(produced.interaction, dict):
            spec = InteractionSpec.model_validate(dict(produced.interaction))
            pending_interaction = await request_interaction(deps, spec)

        status = (
            RuntimeStatus.WAITING_FOR_USER
            if awaiting
            else (
                RuntimeStatus.EXECUTING if verdict.allowed_tasks else RuntimeStatus.WAITING_FOR_USER
            )
        )
        messages = [produced.negotiation] if produced.negotiation else []
        if not verdict.allowed_tasks and verdict.findings and not awaiting:
            messages.append(degrade_message(verdict.findings))

        if awaiting:
            deps.close_round(
                step=step,
                decision_id=str(stored["id"]),
                status=str(RuntimeStatus.WAITING_FOR_USER),
                outcomes=(),
            )

        persisted_plan = {
            **produced.to_dict(),
            "allowed": [task.id for task in verdict.allowed_tasks],
        }
        await deps.runtime_state.save_plan(deps.task_id, persisted_plan, budget=budget.to_dict())
        patch = await deps.transition_status(
            state,
            status,
            messages=messages,
            replanning=False,
            pending_interaction=pending_interaction,
        )
        return {
            **patch,
            **checkpoint_patch,
            "plan": persisted_plan,
            "budget": budget.to_dict(),
            "last_decision_id": str(stored["id"]),
            "step": step,
        }

    return orchestrate
