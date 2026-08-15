"""Decide what to do next, every round, from the current state.

This replaces the global router.  The difference is not that a different
component chooses — it is *when*: the router chose once, at the top of a run,
from the learner's words.  The orchestrator chooses every round, from the
learner's profile, and its choice can be overturned by what the last step
produced.

The model's role is deliberately small.  ``candidates`` has already enumerated
what is possible and scored it; the model reorders and justifies within that
list.  If it is unavailable, malformed, or picks something outside the list, the
deterministic ranking stands and the loop keeps moving.
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
    OrchestrationPlan,
    PlannedTask,
)
from .guardrails import Budget

logger = logging.getLogger(__name__)

MAX_MODEL_CANDIDATES = 12
"""How many scored options the model is shown. More is noise, not choice."""

SYSTEM_PROMPT = """你是 LingxiLearn 的编排器。每一轮重新决策，不要套用固定流程。

宿主已经按「学习收益 / 成本」给候选集打好分。你只能从候选集里挑选和排序，
不能发明列表之外的动作，不能写 agent 名——只写 capability。

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
 "tasks":[{"id":"t1","capability":"...","knowledge_point_id":"...",
           "done_when":{"kind":"..."},"rationale":"...","depends_on":[]}],
 "goal_satisfied_when":{"kind":"..."},"awaits_user":false,"negotiation":null}"""


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


FAST_GOAL_TYPES = frozenset({"learn", "ask", "practice", "review", "assess"})


def _can_use_fast_path(goal: Goal, user_message: Mapping[str, Any] | None) -> bool:
    """Common learner turns do not need a model call in the control plane."""

    if goal.goal_type not in FAST_GOAL_TYPES:
        return False
    text = str((user_message or {}).get("message") or goal.raw_utterance or "")
    # Explicit corrections, negotiations and multi-part requests deserve the
    # model fallback; ordinary learning requests use deterministic ranking.
    return not any(marker in text for marker in ("不是", "不对", "改成", "同时", "比较", "还是"))

def _goal_condition(goal: Goal, world: WorldState) -> DoneCondition:
    """When the goal itself is satisfied, if nothing more specific is stated."""

    point = world.target.knowledge_point_id or (
        goal.knowledge_points[0] if goal.knowledge_points else ""
    )
    # A user-facing turn is complete once it has delivered one useful result.
    # Mastery is updated as evidence arrives, but it must not keep a simple
    # answer trapped in an automatic re-planning loop.
    return DoneCondition(kind="always")


def _task_from_candidate(candidate: CandidateAction, index: int) -> PlannedTask:
    return PlannedTask(
        id=f"t{index}",
        capability=candidate.capability,
        knowledge_point_id=candidate.knowledge_point_id,
        done_when=_default_done_condition(candidate),
        rationale=candidate.reason or "按学习收益排序，这一步收益最高",
        expected_learning_gain=candidate.gain,
        estimated_cost=Cost(
            heavy_artifact=info(parse(candidate.capability)).heavy_artifact,
            irreversible=info(parse(candidate.capability)).irreversible,
            parallel_safe=candidate.parallel_safe,
            critical_path=candidate.critical_path,
        ),
    )


def fallback_plan(
    *, goal: Goal, world: WorldState, candidates: Sequence[CandidateAction]
) -> OrchestrationPlan:
    """The deterministic plan: keep a small useful set of ranked actions.

    Used when there is no model, when the model output cannot be parsed, and
    when guardrails reject everything the model proposed. It is a worse plan
    than a good model would write, and it is never a stalled loop.
    """

    top = best(candidates)
    if top is None:
        return OrchestrationPlan(
            reasoning="当前状态下没有可执行且有收益的动作，交还给学习者。",
            awaits_user=True,
            goal_satisfied_when=_goal_condition(goal, world),
            candidates_considered=list(candidates),
            degraded=True,
        )

    eligible = [item for item in candidates if item.eligible]
    selected: list[CandidateAction] = []
    heavy_selected = False
    for candidate in eligible:
        candidate_info = info(parse(candidate.capability))
        if candidate_info.heavy_artifact and heavy_selected:
            continue
        selected.append(candidate)
        heavy_selected = heavy_selected or candidate_info.heavy_artifact
        if len(selected) >= 3:
            break
    if not selected:
        selected = [top]
    tasks = []
    for index, candidate in enumerate(selected, start=1):
        task = _task_from_candidate(candidate, index)
        if index > 1 and selected[index - 2].capability.startswith("content."):
            task = task.model_copy(update={"depends_on": [f"t{index - 1}"]})
        tasks.append(task)
    deviating = deviates(goal, top, world)
    negotiation = None
    if deviating:
        label = top.knowledge_point_id or goal.topic
        negotiation = (
            f"你想学的是{goal.topic}。档案显示「{label}」还没打牢，"
            f"我建议先补这一块再回来——你也可以让我直接讲，我就按你说的来。"
        )
    return OrchestrationPlan(
        reasoning=f"按学习收益排序，当前最值得做的是{top.capability}：{top.reason}",
        tasks=tasks,
        goal_satisfied_when=DoneCondition(kind="any_of", conditions=[task.done_when for task in tasks]),
        awaits_user=bool(deviating),
        negotiation=negotiation,
        candidates_considered=list(candidates),
        deviates_from_goal=deviating,
        degraded=True,
    )


def _repair(
    parsed: Mapping[str, Any],
    *,
    goal: Goal,
    world: WorldState,
    candidates: Sequence[CandidateAction],
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

    candidates = generate(goal=goal, world=world, skills=skills)
    if model is None or _can_use_fast_path(goal, user_message):
        return fallback_plan(goal=goal, world=world, candidates=candidates)

    offered = eligible_only(candidates)[:MAX_MODEL_CANDIDATES]
    if not offered:
        return fallback_plan(goal=goal, world=world, candidates=candidates)

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
            for item in offered
        ],
    }
    try:
        agent = create_agent(
            agent_model(model, "orchestrator"),
            system_prompt=SYSTEM_PROMPT,
            name="orchestrator",
        )
        parsed = extract_json(
            message_text(
                await invoke_agent(
                    agent,
                    HumanMessage(json.dumps(payload, ensure_ascii=False)),
                    runtime,
                    agent_name="orchestrator",
                    recursion_limit=8,
                )
            )
        )
    except Exception:  # noqa: BLE001 - planning must not be able to end a session
        logger.exception("orchestrator planning failed; using the deterministic ranking")
        return fallback_plan(goal=goal, world=world, candidates=candidates)

    if not parsed:
        return fallback_plan(goal=goal, world=world, candidates=candidates)

    repaired = _repair(parsed, goal=goal, world=world, candidates=candidates)
    if repaired is None:
        return fallback_plan(goal=goal, world=world, candidates=candidates)
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


__all__ = ["MAX_MODEL_CANDIDATES", "SYSTEM_PROMPT", "fallback_plan", "plan"]
