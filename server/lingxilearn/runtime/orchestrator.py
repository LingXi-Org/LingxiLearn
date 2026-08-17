"""Decide what to do next, every round, from the current state.

This replaces the global router.  The difference is not that a different
component chooses — it is *when*: the router chose once, at the top of a run,
from the learner's words.  The orchestrator chooses every round, from the
learner's profile, and its choice can be overturned by what the last step
produced.

The model evaluates every registry-eligible candidate and produces the plan.
The host only enforces capability availability and schema safety. If the model
is unavailable or malformed, the round fails closed; it never selects a local
fallback route.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from lingxigraph import HumanMessage, create_agent

from ..agents.contracts import extract_json
from ..agents.model_runtime import agent_model, invoke_agent, message_text
from ..state.capabilities import UnknownCapability, info, parse
from ..state.session_state import Goal
from .candidates import WorldState, best, deviates, eligible_only, generate
from .contracts import (
    CandidateAction,
    Cost,
    DoneCondition,
    HoldDecision,
    OrchestrationPlan,
    PlannedTask,
)
from .guardrails import Budget
from .interactions import InteractionSpec

logger = logging.getLogger(__name__)

MAX_MODEL_CANDIDATES = 12
"""How many scored options the model is shown. More is noise, not choice."""

SYSTEM_PROMPT = """你是 LingxiLearn 的学习计划决策器。每一轮重新决策，不要套用固定流程。

你必须在一次响应中完成两个可审计技能：
1. 学习效用评估：为每个候选输出 gain、utility 和中文 reason，utility 要体现 gain / cost；
2. 学习计划编排：根据这些评估选择任务并生成依赖关系。
宿主只提供候选能力和事实成本；不能发明列表之外的动作，不能写 agent 名。
每个任务必须提交候选的 candidate_id；candidate_id 已绑定 skill、provider、版本和知识点，不能只写 capability。

规则：
- 一轮最多 3 个任务。
- 每个任务必须有 done_when，且必须可机器判定；「agent 跑完」不是完成条件。
- 每个任务必须有 rationale，能直接展示给学习者，单条不超过 60 字。
- 如果打算做的事和学习者字面要求不同（换了知识点，或忽略了明确请求），
  或者目标范围/知识点/路径存在会改变实际执行的不确定性，必须置 awaits_user=true，
  并优先输出结构化 interaction（而不是 negotiation 文本）。
- interaction.questions 每题 2–4 个选项，选项 id 用 o1/o2…，题 id 用 q1/q2…；
  reason_code 用稳定英文码（如 goal_ambiguous / knowledge_point_unclear / path_choice / confirm_artifact_scope）。
- 同一知识点的相关产物应在同一轮一起下发；彼此无真实数据依赖时 depends_on 必须为空。
- 输出 holds（对已有产物 revise 或 close）和 delivery_order（学生学习顺序，不是生成顺序）。
- 候选之间 utility 差距小于 0.05 时可以按连贯性选择；否则跟随打分。

done_when 可用类型：artifact_exists / artifact_valid / evidence_observed / provider_result /
profile_reaches / user_replied / quiz_graded / always / all_of / any_of。

reasoning 不超过 80 字，hypotheses 最多 2 条，scores.reason 不超过 24 字；不要复述候选详情。
只输出 JSON：
{"reasoning":"...","hypotheses":["..."],
"scores":[{"capability":"...","knowledge_point_id":"...","gain":0.0,"utility":0.0,"reason":"..."}],
 "tasks":[{"id":"t1","candidate_id":"candidate_...","capability":"...","knowledge_point_id":"...",
           "done_when":{"kind":"..."},"rationale":"...","depends_on":[]}],
 "goal_satisfied_when":{"kind":"..."},"awaits_user":false,"negotiation":null,
 "interaction":null,
 "holds":[{"task_key":"step:task-id","action":"revise|close","instruction":"..."}],
 "delivery_order":["lesson-intro","visual","lecture-deck","quiz"]}

awaits_user=true 且需要学习者澄清时，interaction 使用：
{"purpose":"clarification","presentation":"question","blocking":true,"title":"...",
 "prompt":"...","questions":[{"id":"q1","type":"single_select","prompt":"...",
   "options":[{"id":"o1","label":"..."},{"id":"o2","label":"..."}],"allow_free_text":false}],
 "reason_code":"goal_ambiguous","dismissible":false}"""


def unavailable_plan(*, candidates: Sequence[CandidateAction]) -> OrchestrationPlan:
    """Fail closed when a control-plane model cannot make a decision.

    A code-selected fallback plan would be fixed routing in disguise.  We keep
    the candidate trace for observability, but ask the learner to retry rather
    than executing a route which the model did not explicitly choose.
    """
    selected = best(candidates)
    if selected is not None:
        capability_info = info(parse(selected.capability))
        task = PlannedTask(
            id=f"fallback-{selected.candidate_id or selected.skill_id}",
            candidate_id=selected.candidate_id,
            capability=selected.capability,
            knowledge_point_id=selected.knowledge_point_id,
            done_when=_default_done_condition(selected),
            rationale=selected.reason or "先完成当前最有帮助的一步，再根据结果继续安排。",
            expected_learning_gain=selected.gain,
            estimated_cost=Cost(
                heavy_artifact=capability_info.heavy_artifact,
                irreversible=capability_info.irreversible,
                parallel_safe=selected.parallel_safe,
                critical_path=selected.critical_path,
            ),
        )
        return OrchestrationPlan(
            reasoning="计划模型暂不可用，已执行一项可逆且满足前置条件的安全降级动作。",
            tasks=[task],
            goal_satisfied_when=task.done_when,
            candidates_considered=list(candidates),
            degraded=True,
        )
    return OrchestrationPlan(
        reasoning="本轮学习计划模型暂时没有给出可验证的决策。",
        awaits_user=True,
        negotiation="学习计划暂时无法确认，请稍后重试或补充你想达到的具体效果。",
        goal_satisfied_when=DoneCondition(kind="user_replied"),
        candidates_considered=list(candidates),
        degraded=True,
    )


def _default_done_condition(candidate: CandidateAction) -> DoneCondition:
    """A machine-checkable completion condition for a capability.

    Used for the fallback plan and to repair a model task that omitted one.
    Defaulting to ``always`` everywhere would quietly restore "the agent ran, so
    we are done", which is the behaviour this refactor exists to remove.
    """

    capability = parse(candidate.capability)
    match capability.value:
        case "content.lesson_intro":
            return DoneCondition(kind="artifact_valid", artifact="lesson-intro")
        case "content.deck":
            return DoneCondition(kind="artifact_valid", artifact="lecture-deck")
        case "content.visual":
            return DoneCondition(kind="artifact_valid", artifact="visual")
        case "assess.generate":
            return DoneCondition(kind="artifact_exists", artifact="quiz")
        case "assess.grade":
            return DoneCondition(kind="quiz_graded")
        case "assess.interpret":
            return DoneCondition(
                kind="evidence_observed",
                signal="error_pattern",
                knowledge_point_id=candidate.knowledge_point_id,
            )
        case "dialog.answer":
            return DoneCondition(
                kind="evidence_observed",
                signal="self_report",
                knowledge_point_id=candidate.knowledge_point_id,
            )
        case "dialog.converse":
            return DoneCondition(kind="evidence_observed", signal="self_report")
        case "dialog.interview":
            return DoneCondition(kind="evidence_observed", signal="self_report")
        case "dialog.probe":
            return DoneCondition(kind="user_replied")
    return DoneCondition(kind="provider_result")


def _goal_condition(goal: Goal, world: WorldState) -> DoneCondition:
    """When the goal itself is satisfied, if nothing more specific is stated."""

    point_ids = tuple(point for point in goal.knowledge_points if str(point).strip())
    goal_type = goal.goal_type.casefold()
    if goal.satisfied_when:
        try:
            candidate_condition = DoneCondition.model_validate(goal.satisfied_when)
            if candidate_condition.kind != "always":
                return candidate_condition
        except ValueError:
            pass
    if goal_type in {"assess", "quiz", "evaluate", "assessment"}:
        return DoneCondition(kind="quiz_graded")
    if goal_type in {"report", "content", "artifact"}:
        return DoneCondition(kind="artifact_valid", artifact="lesson-intro")
    if goal_type in {"learn", "study", "review", "practice"} and not point_ids:
        return DoneCondition(kind="evidence_observed", signal="goal_clarified")
    if point_ids:
        return DoneCondition(
            kind="all_of",
            conditions=[
                DoneCondition(
                    kind="all_of",
                    conditions=[
                        DoneCondition(
                            kind="profile_reaches",
                            knowledge_point_id=point,
                            mastery=0.75,
                        ),
                        DoneCondition(
                            kind="evidence_observed",
                            knowledge_point_id=point,
                            signal="correct",
                            min_count=2,
                        ),
                    ],
                )
                for point in point_ids
            ],
        )
    return DoneCondition(kind="user_replied")


def _repair(
    parsed: Mapping[str, Any],
    *,
    goal: Goal,
    world: WorldState,
    candidates: Sequence[CandidateAction],
    interjection_message: str = "",
    board: Mapping[str, Any] | None = None,
) -> OrchestrationPlan | None:
    """Turn model output into a valid plan, or ``None`` if it cannot be saved.

    Repairing is preferred over rejecting: a model that picked the right action
    and forgot a ``done_when`` should not cost the learner a round.
    """

    eligible = eligible_only(candidates)
    by_id = {item.candidate_id: item for item in eligible if item.candidate_id}
    by_capability: dict[str, list[CandidateAction]] = {}
    for item in eligible:
        by_capability.setdefault(item.capability, []).append(item)
    tasks: list[PlannedTask] = []

    for index, raw in enumerate(parsed.get("tasks") or [], start=1):
        capability = str(raw.get("capability") or "").strip()
        selected_id = str(raw.get("candidate_id") or "").strip()
        candidate = by_id.get(selected_id) if selected_id else None
        # Compatibility for old planners: only accept capability-only output
        # when it is unambiguous.  A collision must never be resolved again at
        # dispatch time.
        if candidate is None:
            matches = by_capability.get(capability, [])
            candidate = matches[0] if len(matches) == 1 else None
        if candidate is None:
            # Outside the offered set: the model invented an action.
            logger.info("orchestrator proposed an unavailable capability: %s", capability)
            continue
        try:
            raw_done = raw.get("done_when")
            if (
                isinstance(raw_done, Mapping)
                and str(raw_done.get("kind")) == "evidence_observed"
                and str(raw_done.get("signal")) == "provider_result"
            ):
                # Older planner prompts encoded a successful provider result as
                # learning evidence. It is a host execution fact, so normalize
                # it before validation instead of creating an impossible signal.
                raw_done = {"kind": "provider_result"}
            if isinstance(raw_done, Mapping) and str(raw_done.get("kind")) == "always":
                # ``always`` is an internal strategy fallback only; accepting
                # it from a model would let a provider forge completion.
                raw_done = None
            done_when = (
                DoneCondition.model_validate(raw_done)
                if isinstance(raw_done, Mapping)
                else _default_done_condition(candidate)
            )
        except ValueError:
            done_when = _default_done_condition(candidate)

        rationale = str(raw.get("rationale") or "").strip() or candidate.reason
        if not rationale:
            continue
        try:
            capability_info = info(parse(capability))
        except UnknownCapability:
            continue

        tasks.append(
            PlannedTask(
                id=str(raw.get("id") or f"t{index}"),
                candidate_id=candidate.candidate_id,
                capability=capability,
                knowledge_point_id=str(
                    raw.get("knowledge_point_id") or candidate.knowledge_point_id
                ),
                inputs=dict(raw.get("inputs") or {}),
                depends_on=[str(item) for item in (raw.get("depends_on") or [])],
                done_when=done_when,
                rationale=rationale,
                expected_learning_gain=candidate.gain,
                estimated_cost=Cost(
                    heavy_artifact=capability_info.heavy_artifact,
                    irreversible=capability_info.irreversible,
                    parallel_safe=candidate.parallel_safe,
                    critical_path=candidate.critical_path,
                ),
            )
        )

    if interjection_message and any(task.capability == "dialog.converse" for task in tasks):
        tasks = [task for task in tasks if task.capability != "dialog.probe"]
    elif any(task.capability == "dialog.probe" for task in tasks):
        tasks = [task for task in tasks if task.capability != "dialog.converse"]

    board = board or {}
    known_holds = set((board.get("holds") or {}).keys())
    holds: list[HoldDecision] = []
    for raw_hold in parsed.get("holds") or []:
        if not isinstance(raw_hold, Mapping):
            continue
        task_key = str(raw_hold.get("task_key") or "")
        if task_key not in known_holds:
            continue
        action = str(raw_hold.get("action") or "close")
        if action not in {"revise", "close"}:
            action = "close"
        instruction = str(raw_hold.get("instruction") or "").strip()
        if action == "revise" and not instruction:
            action = "close"
        holds.append(
            HoldDecision(
                task_key=task_key,
                action="revise" if action == "revise" else "close",
                instruction=instruction,
            )
        )

    # A new learner has no evidence from which to personalize the first
    # explanation.  Keep the dedicated opening conversation agent present in
    # that state even if the model spends its one call selecting artifacts;
    # this is derived from candidate metadata and profile evidence, never from
    # the learner's wording or a goal/intent route.
    opening_candidate = next(
        (
            item
            for item in candidates
            if item.eligible and info(item.capability).opening_conversation
        ),
        None,
    )
    if (
        opening_candidate is not None
        and not world.interview_completed
        and not any(info(task.capability).opening_conversation for task in tasks)
        and not any(
            info(task.capability).turn_complete and not info(task.capability).opening_conversation
            for task in tasks
        )
    ):
        tasks.insert(
            0,
            PlannedTask(
                id=f"opening-{opening_candidate.skill_id}",
                capability=opening_candidate.capability,
                knowledge_point_id=opening_candidate.knowledge_point_id,
                done_when=_default_done_condition(opening_candidate),
                rationale=opening_candidate.reason or "先了解你的基础，再安排最合适的学习路径。",
                expected_learning_gain=opening_candidate.gain,
                estimated_cost=Cost(
                    parallel_safe=opening_candidate.parallel_safe,
                    critical_path=opening_candidate.critical_path,
                ),
            ),
        )
    # A control-plane round may contain only hold decisions.  This is valid
    # even when every artifact candidate is currently precondition-blocked:
    # closing or revising an existing hold is driven by the board, not by a
    # freshly generated candidate.  Do not discard that state-only decision.
    if not tasks and not parsed.get("awaits_user") and not holds:
        return None

    known_artifacts = {"lesson-intro", "visual", "lecture-deck", "quiz"}
    delivery_order: list[str] = []
    for raw_delivery in parsed.get("delivery_order") or []:
        delivery_item = str(raw_delivery)
        if delivery_item in known_artifacts and delivery_item not in delivery_order:
            delivery_order.append(delivery_item)
    produced_order = list(board.get("produced_order") or [])
    produced_order.extend(
        str(artifact)
        for row in (board.get("holds") or {}).values()
        if isinstance(row, Mapping)
        for artifact in (row.get("artifacts") or [])
    )
    produced_order.extend(
        str(item.get("artifact"))
        for item in (board.get("delivery") or [])
        if isinstance(item, Mapping) and item.get("artifact")
    )
    for raw_artifact in produced_order:
        artifact_name = str(raw_artifact)
        if artifact_name in known_artifacts and artifact_name not in delivery_order:
            delivery_order.append(artifact_name)
    try:
        goal_when = (
            DoneCondition.model_validate(parsed["goal_satisfied_when"])
            if isinstance(parsed.get("goal_satisfied_when"), Mapping)
            else (
                DoneCondition(
                    kind="any_of",
                    conditions=[task.done_when for task in tasks],
                )
                if tasks
                else _goal_condition(goal, world)
            )
        )
    except ValueError:
        goal_when = _goal_condition(goal, world)

    candidate_by_id = {item.candidate_id: item for item in candidates}
    deviating = any(
        deviates(goal, candidate_by_id[t.candidate_id], world)
        for t in tasks
        if t.candidate_id in candidate_by_id
    )
    # A structured interaction beats prose negotiation when the model emits
    # one; malformed specs fall back to the legacy text path (issue #18 §10.2).
    interaction_spec: dict[str, Any] | None = None
    if isinstance(parsed.get("interaction"), Mapping):
        try:
            validated = InteractionSpec.model_validate(dict(parsed["interaction"]))
            interaction_spec = validated.model_dump(mode="json", by_alias=True)
        except Exception:  # noqa: BLE001 - model output; degrade, don't crash
            logger.info("orchestrator emitted an invalid interaction; ignoring")
    try:
        return OrchestrationPlan(
            reasoning=str(parsed.get("reasoning") or ""),
            hypotheses=[str(item) for item in (parsed.get("hypotheses") or [])],
            tasks=tasks,
            goal_satisfied_when=goal_when,
            awaits_user=bool(parsed.get("awaits_user")) or deviating,
            negotiation=(str(parsed.get("negotiation")).strip() or None)
            if parsed.get("negotiation")
            else None,
            interaction=interaction_spec,
            candidates_considered=list(candidates),
            deviates_from_goal=deviating,
            holds=holds,
            delivery_order=delivery_order,
        )
    except ValueError:
        logger.info("orchestrator plan failed validation", exc_info=True)
        return None


async def plan(
    *,
    goal: Goal,
    world: WorldState,
    skills: Sequence[Mapping[str, Any]],
    budget: Budget,
    model: Any | None = None,
    runtime: Any = None,
    user_message: Mapping[str, Any] | None = None,
    board: Mapping[str, Any] | None = None,
) -> OrchestrationPlan:
    """Produce this round's plan from the current state."""

    registry_candidates = generate(goal=goal, world=world, skills=skills)
    candidates = eligible_only(registry_candidates)
    board_holds = (board or {}).get("holds") or {}
    if model is None or (not candidates and not board_holds):
        return unavailable_plan(candidates=registry_candidates)

    payload = {
        "goal": goal.to_dict(),
        "profile": {
            "target": _view_dict(world.target),
            "prerequisites": [_view_dict(item) for item in world.prerequisites],
        },
        "budget": budget.to_dict(),
        "held": [
            {
                "task_key": key,
                "capability": value.get("capability", ""),
                "artifacts": list(value.get("artifacts") or []),
                "revisions": int(value.get("revisions") or 0),
                "detail": value.get("detail", ""),
            }
            for key, value in ((board or {}).get("holds") or {}).items()
        ],
        "delivery": {
            "order": list((board or {}).get("order") or []),
            "queued": list((board or {}).get("delivery") or []),
            "cursor": int((board or {}).get("cursor") or 0),
        },
        "learner_message": dict(user_message or {}),
        "candidates": [
            {
                "capability": item.capability,
                "knowledge_point_id": item.knowledge_point_id,
                "utility": item.utility,
                "gain": item.gain,
                "cost": item.cost,
                "reason": item.reason[:96],
                "skill_id": item.skill_id,
                "candidate_id": item.candidate_id,
            }
            for item in candidates
        ],
    }
    try:
        agent = create_agent(
            agent_model(model, "learning_plan_decision"),
            system_prompt=SYSTEM_PROMPT,
            name="learning-plan-decision",
        )
        parsed = extract_json(
            message_text(
                await invoke_agent(
                    agent,
                    HumanMessage(json.dumps(payload, ensure_ascii=False)),
                    runtime,
                    agent_name="learning_plan_decision",
                    recursion_limit=4,
                )
            )
        )
    except Exception:  # noqa: BLE001 - planning must not be able to end a session
        logger.exception("orchestrator planning failed; no route will be selected locally")
        return unavailable_plan(candidates=registry_candidates)

    if not parsed:
        return unavailable_plan(candidates=registry_candidates)

    scores = parsed.get("scores") if isinstance(parsed, Mapping) else None
    if not isinstance(scores, list):
        if board_holds and parsed.get("holds"):
            scores = []
        else:
            return unavailable_plan(candidates=registry_candidates)
    by_key = {(item.capability, item.knowledge_point_id): item for item in candidates}
    judged: dict[tuple[str, str], CandidateAction] = {}
    for raw in scores:
        if not isinstance(raw, Mapping):
            continue
        key = (str(raw.get("capability") or ""), str(raw.get("knowledge_point_id") or ""))
        candidate = by_key.get(key)
        if candidate is None:
            continue
        try:
            gain = max(0.0, min(1.0, float(raw.get("gain") or 0.0)))
            utility = max(0.0, min(1.0, float(raw.get("utility") or 0.0)))
        except (TypeError, ValueError):
            continue
        judged[key] = candidate.model_copy(
            update={
                "gain": gain,
                "utility": utility,
                "reason": str(raw.get("reason") or candidate.reason).strip(),
            }
        )
    # When the board is the only actionable source of work, the model may
    # quite correctly return no candidate scores and only holds/delivery.  In
    # that case preserve the state decision instead of replacing it with the
    # empty fallback plan.
    if not judged and not ((board or {}).get("holds") and parsed.get("holds")):
        return unavailable_plan(candidates=registry_candidates)
    candidates = sorted(
        [
            judged.get(
                (item.capability, item.knowledge_point_id),
                item.model_copy(update={"gain": 0.0, "utility": 0.0}),
            )
            for item in registry_candidates
        ],
        key=lambda item: item.utility,
        reverse=True,
    )
    repaired = _repair(
        parsed,
        goal=goal,
        world=world,
        candidates=candidates,
        interjection_message=str((user_message or {}).get("message") or "").strip(),
        board=board,
    )
    if repaired is None:
        return unavailable_plan(candidates=candidates)
    return repaired


def _view_dict(view: Any) -> dict[str, Any]:
    return {
        "id": view.knowledge_point_id,
        "label": view.knowledge_point,
        "mastery": round(view.mastery, 4),
        "learning_state": view.learning_state,
        "evidence_count": view.evidence_count,
        "misconceptions": list(view.misconceptions),
        "review_priority": view.review_priority,
    }


__all__ = ["MAX_MODEL_CANDIDATES", "SYSTEM_PROMPT", "plan"]
