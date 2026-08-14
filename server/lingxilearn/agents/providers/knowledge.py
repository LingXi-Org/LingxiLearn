"""Providers that model the learner and the subject, rather than teach.

None of these are learner-facing. They produce structure — prerequisites,
graph patches, review order, state proposals — that changes what the
orchestrator will rank highest next round.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from lingxigraph import FilesystemSkillSource, HumanMessage, SkillRegistry, create_agent

from ...config import REPO_ROOT
from ...state.evidence import EvidenceRecord, Signal
from ...state.scheduling import review_priority
from ..contracts import extract_json
from ..model_runtime import agent_model, emit, invoke_agent, message_text
from ..skill_runtime import progressive_skill_prompt, skill_constraints
from .base import ProviderContext, ProviderError, ProviderResult, register

logger = logging.getLogger(__name__)

PREREQ_PROMPT = """你是前置依赖分析 Agent。

只列出真正的推导依赖：每个前置点必须能指出它在目标推导的哪一步被用到。
最多两层，找不到可靠依赖就返回空列表。
判定：mastery>=0.6 且 evidence_count>=2 才算 met；evidence_count<2 标 unverified；
带未消解误区的标 blocked。

只输出 JSON：
{"prerequisites":[{"id":"...","label":"...","status":"met|unverified|blocked",
"used_for":"...","mastery":0.0}],
"verdict":"teach_target|teach_prerequisite_first|verify_prerequisite_first",
"blocking_prerequisite":"...","rationale":"..."}"""

REFLECTOR_RESOURCES = (
    "references/learner-state-reflector-task.schema.json",
    "references/learner-state-reflector-result.schema.json",
    "references/runtime-contract.md",
)

REFLECTOR_PROMPT = progressive_skill_prompt(
    "learner-state-reflector",
    "learner-state-reflector-result.v1",
    referenced_resources=REFLECTOR_RESOURCES,
    artifact_instructions=(
        "这是后台学习状态反思 Agent。只返回 proposal JSON，不写数据库，不输出教学回复。"
        "保留原始 evidence ID，避免从单次行为推断永久掌握。"
    ),
    stage_artifacts=False,
)


def _registry(name: str) -> SkillRegistry:
    return SkillRegistry((FilesystemSkillSource(REPO_ROOT / "skills" / name),))


@register("prerequisite_analyzer")
async def prerequisite_analyzer(context: ProviderContext) -> ProviderResult:
    """Work out what the target rests on and what is missing (``graph.prerequisite``).

    Writes its findings to the profile as evidence rather than as prose, so the
    next round's candidate scoring can act on them without re-asking a model.
    """

    point = context.knowledge_point_id
    profile = context.profile_of()
    payload = {
        "target": {
            "id": point,
            "label": profile.get("knowledge_point") or point,
            "mastery": profile.get("mastery"),
            "evidence_count": (profile.get("system") or {}).get("evidence_count"),
        },
        "topic": context.goal.topic,
        "known_points": [
            {
                "id": row.get("knowledge_point_id"),
                "label": row.get("knowledge_point"),
                "mastery": row.get("mastery"),
                "evidence_count": (row.get("system") or {}).get("evidence_count"),
            }
            for row in context.profile.values()
        ][:40],
    }

    if context.model is None:
        # No model: report that we could not map dependencies rather than
        # inventing one, and let the orchestrator proceed on the target.
        return ProviderResult(
            status="incomplete",
            data={"prerequisites": [], "verdict": "teach_target",
                  "rationale": "无可用模型，未能分析依赖"},
            persist_as="prerequisites",
            detail="未能分析前置依赖（无模型）",
        )

    emit(
        context.runtime,
        "agent.started",
        agent="prerequisite_analyzer",
        skill="prerequisite-analyzer",
    )
    agent = create_agent(
        agent_model(context.model, "prerequisite_analyzer"),
        system_prompt=PREREQ_PROMPT,
        name="prerequisite-analyzer",
    )
    parsed = extract_json(
        message_text(
            await invoke_agent(
                agent,
                HumanMessage(json.dumps(payload, ensure_ascii=False)),
                context.runtime,
                agent_name="prerequisite_analyzer",
                recursion_limit=8,
            )
        )
    ) or {}

    prerequisites = [
        {
            "id": str(item.get("id") or "").strip(),
            "label": str(item.get("label") or ""),
            "status": str(item.get("status") or "unverified"),
            "used_for": str(item.get("used_for") or ""),
        }
        for item in (parsed.get("prerequisites") or [])
        if str(item.get("id") or "").strip()
    ]
    verdict = str(parsed.get("verdict") or "teach_target")
    blocking = str(parsed.get("blocking_prerequisite") or "")

    emit(
        context.runtime,
        "agent.output",
        agent="prerequisite_analyzer",
        message=f"识别到 {len(prerequisites)} 个前置依赖，判定：{verdict}",
    )
    return ProviderResult(
        data={
            "target": point,
            "prerequisites": prerequisites,
            "verdict": verdict,
            "blocking_prerequisite": blocking,
            "rationale": str(parsed.get("rationale") or ""),
        },
        persist_as="prerequisites",
        detail=str(parsed.get("rationale") or f"判定：{verdict}"),
    )


@register("review_scheduler")
async def review_scheduler(context: ProviderContext) -> ProviderResult:
    """Rank what is due for retrieval practice (``review.schedule``).

    Deterministic: the priority formula already lives in
    :mod:`lingxilearn.state.scheduling`, and re-deriving it in a model would
    make the same ranking non-reproducible for no gain.
    """

    now = datetime.now(UTC)
    due: list[dict[str, Any]] = []
    for row in context.profile.values():
        system = dict(row.get("system") or {})
        raw_due = row.get("review_due_at")
        due_at_value = None
        if isinstance(raw_due, str) and raw_due:
            try:
                due_at_value = datetime.fromisoformat(raw_due)
            except ValueError:
                due_at_value = None

        priority = review_priority(
            mastery=float(row.get("mastery") or 0.0),
            review_due_at=due_at_value,
            now=now,
            evidence_count=int(system.get("evidence_count") or 0),
            has_misconceptions=bool(system.get("misconceptions")),
        )
        if priority < 0.3:
            continue
        overdue_days = (
            round((now - due_at_value).total_seconds() / 86_400.0, 2)
            if due_at_value and due_at_value < now
            else 0.0
        )
        due.append(
            {
                "knowledge_point_id": row.get("knowledge_point_id"),
                "knowledge_point": row.get("knowledge_point"),
                "priority": priority,
                "overdue_days": overdue_days,
                "mastery": row.get("mastery"),
                "evidence_count": system.get("evidence_count"),
                "form": _review_form(row, system),
                "reason": _review_reason(overdue_days, row, system),
            }
        )

    due.sort(key=lambda item: (-item["priority"], str(item["knowledge_point_id"])))
    top = due[:3]
    message = (
        "现在最值得复习的是：" + "、".join(str(item["knowledge_point"]) for item in top)
        if top
        else "暂时没有到期的复习点。"
    )
    return ProviderResult(
        learner_message=message,
        data={"due": top, "considered": len(context.profile)},
        persist_as="review_schedule",
        detail=f"{len(top)} 个复习点待处理",
    )


def _review_form(row: dict[str, Any], system: dict[str, Any]) -> str:
    if system.get("misconceptions"):
        return "discriminate"
    return "transfer" if float(row.get("mastery") or 0.0) >= 0.75 else "retrieval"


def _review_reason(overdue_days: float, row: dict[str, Any], system: dict[str, Any]) -> str:
    parts: list[str] = []
    if overdue_days > 0:
        parts.append(f"逾期 {overdue_days:g} 天")
    parts.append(f"掌握度 {float(row.get('mastery') or 0.0):.2f}")
    if system.get("misconceptions"):
        parts.append(f"仍有误区「{system['misconceptions'][0]}」")
    return "，".join(parts)


@register("curriculum_graph")
async def curriculum_graph(context: ProviderContext) -> ProviderResult:
    """Propose a knowledge-graph patch (``graph.build``).

    Irreversible: it writes learner-owned graph structure, so guardrails require
    confirmation before this ever runs.
    """

    from ..curriculum_graph import build_curriculum_graph_proposal

    if context.model is None:
        raise ProviderError("curriculum-graph-builder requires a model")

    task_payload = {
        "id": context.task_id,
        "prompt": context.goal.raw_utterance,
        "intent": {"topic": context.goal.topic},
        "user_messages": [context.user_message] if context.user_message else [],
        "lecture_result": dict(context.result_of("lecture_hook")),
        "deck_result": dict(context.result_of("interactive_lecture_deck")),
        "quiz_result": dict(context.result_of("quiz_generator")),
    }
    proposal = await build_curriculum_graph_proposal(
        model=context.model,
        task=task_payload,
        existing_graphs=list(context.task.inputs.get("existing_graphs") or []),
        runtime=context.runtime,
    )
    return ProviderResult(
        data=proposal,
        persist_as="knowledge_graph",
        detail=f"图谱提案：{proposal.get('decision', {}).get('action', 'unknown')}",
    )


@register("learner_reflector")
async def learner_reflector(context: ProviderContext) -> ProviderResult:
    """Compress recent events into a cautious state proposal (``model.reflect``).

    Proposal-only by design: it can suggest, but the profile still changes only
    through evidence and state_updater.
    """

    if context.model is None:
        raise ProviderError("learner-state-reflector requires a model")

    request = {
        "events": list(context.task.inputs.get("events") or [])[-120:],
        "prior_state": {
            key: dict(value) for key, value in list(context.profile.items())[:20]
        },
        "topic": context.goal.topic,
        "learning_objective": context.goal.expected_outcome,
    }
    agent = create_agent(
        agent_model(context.model, "learner_reflector"),
        skills=_registry("learner-state-reflector"),
        system_prompt=REFLECTOR_PROMPT,
        pinned_constraints=skill_constraints(
            "learner-state-reflector", REFLECTOR_RESOURCES, stage_artifacts=False
        ),
        name="learner-state-reflector",
    )
    parsed = extract_json(
        message_text(
            await invoke_agent(
                agent,
                HumanMessage(json.dumps(request, ensure_ascii=False)),
                context.runtime,
                agent_name="learner_reflector",
                recursion_limit=12,
            )
        )
    )
    if not parsed:
        raise ProviderError("learner-state-reflector returned no JSON result")

    observations = [
        EvidenceRecord(
            learner_id=context.learner_id,
            knowledge_point=str(item.get("knowledge_point") or context.knowledge_point_id),
            signal=Signal.SELF_REPORT,
            source_agent="learner_reflector",
            task_id=context.task_id,
            summary=str(item.get("summary") or "")[:200],
            payload={"proposal": True},
        )
        for item in (parsed.get("observations") or [])
        if str(item.get("summary") or "").strip()
    ]
    return ProviderResult(
        evidence=observations,
        data=parsed,
        persist_as="learner_reflection",
        detail=f"整理出 {len(observations)} 条状态观察",
    )


__all__ = [
    "curriculum_graph",
    "learner_reflector",
    "prerequisite_analyzer",
    "review_scheduler",
]
