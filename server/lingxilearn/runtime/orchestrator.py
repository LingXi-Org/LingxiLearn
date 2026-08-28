"""Decide what to do next, every round, from the current state.

This replaces the global router.  The difference is not that a different
component chooses — it is *when*: the router chose once, at the top of a run,
from the learner's words.  The orchestrator chooses every round, from the
learner's profile, and its choice can be overturned by what the last step
produced.

The model evaluates every registry-eligible candidate and produces the plan.
The host only enforces capability availability and schema safety. If the model
is unavailable or malformed, the round fails closed and selects no route.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from lingxigraph import HumanMessage, create_agent

from ..agents.contracts import extract_json
from ..agents.model_runtime import agent_model, invoke_agent, message_text
from ..state.agent_task_state import Goal
from ..state.capabilities import UnknownCapability, info, parse
from .candidates import WorldState, deviates, eligible_only, generate
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
    """Fail closed when the control-plane model cannot make a decision."""

    raise RuntimeError(
        f"learning plan unavailable: model did not select from {len(candidates)} candidates"
    )


def _validate_plan_output(
    parsed: Mapping[str, Any],
    *,
    goal: Goal,
    world: WorldState,
    candidates: Sequence[CandidateAction],
    interjection_message: str = "",
    board: Mapping[str, Any] | None = None,
) -> OrchestrationPlan | None:
    """Validate one model decision against the exact offered candidates."""

    eligible = eligible_only(candidates)
    by_id = {item.candidate_id: item for item in eligible if item.candidate_id}
    tasks: list[PlannedTask] = []

    for raw in parsed.get("tasks") or []:
        if not isinstance(raw, Mapping):
            return None
        capability = str(raw.get("capability") or "").strip()
        selected_id = str(raw.get("candidate_id") or "").strip()
        candidate = by_id.get(selected_id)
        if candidate is None or capability != candidate.capability:
            logger.info("orchestrator proposed an unavailable capability: %s", capability)
            return None
        try:
            raw_done = raw.get("done_when")
            if not isinstance(raw_done, Mapping) or str(raw_done.get("kind")) == "always":
                return None
            done_when = DoneCondition.model_validate(raw_done)
        except ValueError:
            return None

        task_id = str(raw.get("id") or "").strip()
        rationale = str(raw.get("rationale") or "").strip()
        if not task_id or not rationale:
            return None
        try:
            capability_info = info(parse(capability))
        except UnknownCapability:
            continue

        tasks.append(
            PlannedTask(
                id=task_id,
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
    raw_goal_when = parsed.get("goal_satisfied_when")
    if not isinstance(raw_goal_when, Mapping):
        return None
    try:
        goal_when = DoneCondition.model_validate(raw_goal_when)
    except ValueError:
        return None
    if goal_when.kind == "always":
        return None

    candidate_by_id = {item.candidate_id: item for item in candidates}
    deviating = any(
        deviates(goal, candidate_by_id[t.candidate_id], world)
        for t in tasks
        if t.candidate_id in candidate_by_id
    )
    interaction_spec: dict[str, Any] | None = None
    if isinstance(parsed.get("interaction"), Mapping):
        try:
            validated = InteractionSpec.model_validate(dict(parsed["interaction"]))
            interaction_spec = validated.model_dump(mode="json", by_alias=True)
        except ValueError:
            return None
    awaits_user = bool(parsed.get("awaits_user")) or deviating
    if awaits_user and interaction_spec is None:
        return None
    try:
        return OrchestrationPlan(
            reasoning=str(parsed.get("reasoning") or ""),
            hypotheses=[str(item) for item in (parsed.get("hypotheses") or [])],
            tasks=tasks,
            goal_satisfied_when=goal_when,
            awaits_user=awaits_user,
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
    except Exception:  # noqa: BLE001 - provider failures become explicit task failures
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
    # A hold-only board decision legitimately has no new candidate score.
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
    validated = _validate_plan_output(
        parsed,
        goal=goal,
        world=world,
        candidates=candidates,
        interjection_message=str((user_message or {}).get("message") or "").strip(),
        board=board,
    )
    if validated is None:
        return unavailable_plan(candidates=candidates)
    return validated


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
