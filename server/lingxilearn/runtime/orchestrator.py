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
from .candidates import WorldState, deviates, eligible_only, generate
from .contracts import (
    CandidateAction,
    Cost,
    DoneCondition,
    OrchestrationPlan,
    PlannedTask,
)
from .guardrails import Budget

logger = logging.getLogger(__name__)

MAX_MODEL_CANDIDATES = 12
"""How many scored options the model is shown. More is noise, not choice."""

SYSTEM_PROMPT = """你是 LingxiLearn 的学习计划决策器。每一轮重新决策，不要套用固定流程。

你必须在一次响应中完成两个可审计技能：
1. 学习效用评估：为每个候选输出 gain、utility 和中文 reason，utility 要体现 gain / cost；
2. 学习计划编排：根据这些评估选择任务并生成依赖关系。
宿主只提供候选能力和事实成本；不能发明列表之外的动作，不能写 agent 名——只写 capability。

规则：
- 一轮最多 3 个任务。
- 每个任务必须有 done_when，且必须可机器判定；「agent 跑完」不是完成条件。
- 每个任务必须有 rationale，能直接展示给学习者。
- 如果打算做的事和学习者字面要求不同（换了知识点，或忽略了明确请求），
  必须写 negotiation 并置 awaits_user=true。
- 重资产（讲义/课件/可视化）一轮最多一个。
- 候选之间 utility 差距小于 0.05 时可以按连贯性选择；否则跟随打分。

done_when 可用类型：artifact_exists / artifact_valid / evidence_observed /
profile_reaches / user_replied / quiz_graded / always / all_of / any_of。

只输出 JSON：
{"reasoning":"...","hypotheses":["..."],
"scores":[{"capability":"...","knowledge_point_id":"...","gain":0.0,"utility":0.0,"reason":"..."}],
 "tasks":[{"id":"t1","capability":"...","knowledge_point_id":"...",
           "done_when":{"kind":"..."},"rationale":"...","depends_on":[]}],
 "goal_satisfied_when":{"kind":"..."},"awaits_user":false,"negotiation":null}"""

def unavailable_plan(*, candidates: Sequence[CandidateAction]) -> OrchestrationPlan:
    """Fail closed when a control-plane model cannot make a decision.

    A code-selected fallback plan would be fixed routing in disguise.  We keep
    the candidate trace for observability, but ask the learner to retry rather
    than executing a route which the model did not explicitly choose.
    """
    return OrchestrationPlan(
        reasoning="本轮学习计划模型暂时没有给出可验证的决策。",
        awaits_user=True,
        negotiation="学习计划暂时无法确认，请稍后重试或补充你想达到的具体效果。",
        goal_satisfied_when=DoneCondition(kind="always"),
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
        case "dialog.probe":
            return DoneCondition(kind="user_replied")
    return DoneCondition(kind="always")


def _goal_condition(goal: Goal, world: WorldState) -> DoneCondition:
    """When the goal itself is satisfied, if nothing more specific is stated."""

    point = world.target.knowledge_point_id or (
        goal.knowledge_points[0] if goal.knowledge_points else ""
    )
    # A user-facing turn is complete once it has delivered one useful result.
    # Mastery is updated as evidence arrives, but it must not keep a simple
    # answer trapped in an automatic re-planning loop.
    return DoneCondition(kind="always")


def _repair(
    parsed: Mapping[str, Any],
    *,
    goal: Goal,
    world: WorldState,
    candidates: Sequence[CandidateAction],
    interjection_message: str = "",
) -> OrchestrationPlan | None:
    """Turn model output into a valid plan, or ``None`` if it cannot be saved.

    Repairing is preferred over rejecting: a model that picked the right action
    and forgot a ``done_when`` should not cost the learner a round.
    """

    allowed = {item.capability: item for item in eligible_only(candidates)}
    tasks: list[PlannedTask] = []

    for index, raw in enumerate(parsed.get("tasks") or [], start=1):
        capability = str(raw.get("capability") or "").strip()
        candidate = allowed.get(capability)
        if candidate is None:
            # Outside the offered set: the model invented an action.
            logger.info("orchestrator proposed an unavailable capability: %s", capability)
            continue
        try:
            done_when = (
                DoneCondition.model_validate(raw["done_when"])
                if isinstance(raw.get("done_when"), Mapping)
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

    if not tasks and not parsed.get("awaits_user"):
        return None

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

    deviating = any(deviates(goal, allowed[t.capability], world) for t in tasks)
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
            candidates_considered=list(candidates),
            deviates_from_goal=deviating,
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
) -> OrchestrationPlan:
    """Produce this round's plan from the current state."""

    registry_candidates = generate(goal=goal, world=world, skills=skills)
    candidates = eligible_only(registry_candidates)
    if model is None or not candidates:
        return unavailable_plan(candidates=registry_candidates)

    payload = {
        "goal": goal.to_dict(),
        "profile": {
            "target": _view_dict(world.target),
            "prerequisites": [_view_dict(item) for item in world.prerequisites],
        },
        "budget": budget.to_dict(),
        "learner_message": dict(user_message or {}),
        "candidates": [
            {
                "capability": item.capability,
                "knowledge_point_id": item.knowledge_point_id,
                "utility": item.utility,
                "gain": item.gain,
                "cost": item.cost,
                "reason": item.reason,
                "skill_id": item.skill_id,
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
            gain = max(0.0, min(1.0, float(raw.get("gain"))))
            utility = max(0.0, min(1.0, float(raw.get("utility"))))
        except (TypeError, ValueError):
            continue
        judged[key] = candidate.model_copy(update={
            "gain": gain,
            "utility": utility,
            "reason": str(raw.get("reason") or candidate.reason).strip(),
        })
    if not judged:
        return unavailable_plan(candidates=registry_candidates)
    candidates = sorted([
        judged.get((item.capability, item.knowledge_point_id), item.model_copy(update={"gain": 0.0, "utility": 0.0}))
        for item in registry_candidates
    ], key=lambda item: item.utility, reverse=True)
    offered = eligible_only(candidates)[:MAX_MODEL_CANDIDATES]

    repaired = _repair(
        parsed,
        goal=goal,
        world=world,
        candidates=candidates,
        interjection_message=str((user_message or {}).get("message") or "").strip(),
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
