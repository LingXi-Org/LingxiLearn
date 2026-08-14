"""Learner-facing teaching providers.

The hint ladder and the answer-leakage guard in :mod:`lingxilearn.kernel.policy`
apply here, and they are applied as *post-validation* rather than as a request in
a prompt.  Asking a model politely not to give the answer away is not a
mechanism; checking its output against the step's answer markers before the
learner sees it is.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from lingxigraph import FilesystemSkillSource, HumanMessage, SkillRegistry, create_agent

from ...config import REPO_ROOT
from ...kernel.policy import LeakGuard, check_leakage, fallback_hint
from ...state.evidence import EvidenceRecord, Signal
from ..contracts import extract_json
from ..model_runtime import agent_model, emit, invoke_agent, message_text
from ..skill_runtime import progressive_skill_prompt, skill_constraints
from .base import ProviderContext, ProviderError, ProviderResult, register

logger = logging.getLogger(__name__)

PEDAGOGY_RESOURCES = (
    "references/strategy-kernel.md",
    "references/adaptive-pedagogy-result.schema.json",
    "references/learner-state.v2.schema.json",
)

PEDAGOGY_PROMPT = progressive_skill_prompt(
    "adaptive-pedagogy",
    "adaptive-pedagogy-result.v2",
    referenced_resources=PEDAGOGY_RESOURCES,
    artifact_instructions="""这是自适应教学 Agent，是本轮唯一面向学习者的教学写作者。
基于学习档案里的掌握度、证据条数和未消解误区选择最小可用的教学动作，不要把苏格拉底式追问
最大化。只输出 JSON：{"text":"...","strategy":"...","next_step":"..."}。""",
    stage_artifacts=False,
)

QA_PROMPT = """你是知识点答疑 Agent。基于本任务已产出的材料回答学习者的具体追问。

规则：材料里没有的就说没有，不要编细节；回答简短，一个问题一段话；
不得泄露尚未提交的题目答案；超出当前知识点范围时如实说明。
只输出 JSON：{"text":"...","out_of_scope":false}。"""

NEGOTIATION_PROMPT = """你是教学协商 Agent。系统打算做的事和学习者字面要求不同，你要写那一句协商。

必须包含：承认原始请求、引用档案里的具体数字作为理由、说明先做什么要多久、留一个明确的拒绝出口。
一到两句，不要道歉式措辞，不要写成选择题。
只输出 JSON：{"text":"..."}。"""


def _registry(name: str) -> SkillRegistry:
    return SkillRegistry((FilesystemSkillSource(REPO_ROOT / "skills" / name),))


def _learner_brief(context: ProviderContext) -> dict[str, Any]:
    profile = context.profile_of()
    system = dict(profile.get("system") or {})
    return {
        "topic": context.goal.topic,
        "knowledge_point": profile.get("knowledge_point") or context.knowledge_point_id,
        "expected_outcome": context.goal.expected_outcome,
        "mastery": profile.get("mastery"),
        "learning_state": profile.get("learning_state"),
        "evidence_count": system.get("evidence_count"),
        "misconceptions": system.get("misconceptions") or [],
        "open_questions": profile.get("my_questions") or [],
        "recent_performance": profile.get("recent_performance") or {},
        "learner_message": str(context.user_message.get("message") or ""),
    }


def _guarded(text: str, context: ProviderContext) -> tuple[str, bool]:
    """Return text safe to show, and whether the guard had to substitute it.

    The quiz answer key is the leak guard: while questions are outstanding, a
    teaching turn may not contain the phrases or numbers that give them away.
    """

    quiz = dict(context.result_of("quiz_generator"))
    graded = dict(context.result_of("grading"))
    if not quiz.get("questions") or graded:
        return text, False

    phrases: list[str] = []
    numbers: list[float] = []
    for question in quiz.get("questions") or []:
        answer = question.get("answer")
        for value in answer if isinstance(answer, list) else [answer]:
            if isinstance(value, (int, float)):
                numbers.append(float(value))
            elif isinstance(value, str) and len(value.strip()) >= 2:
                phrases.append(value.strip())

    guard = LeakGuard(phrases=phrases, numbers=numbers)
    verdict = check_leakage(text, guard, answer_unlocked=False)
    if not verdict.leaked:
        return text, False

    logger.info("teaching turn withheld for answer leakage: %s", verdict.reasons)
    step = {"hint_ladder": context.task.inputs.get("hint_ladder") or []}
    level = int(context.task.inputs.get("hint_level") or 0)
    return fallback_hint(step, level), True


@register("adaptive_pedagogy")
async def adaptive_pedagogy(context: ProviderContext) -> ProviderResult:
    """Choose and deliver the next teaching move (``teach.strategy``/``teach.explain``)."""

    if context.model is None:
        raise ProviderError("adaptive-pedagogy requires a model")

    emit(
        context.runtime, "agent.started", agent="adaptive_pedagogy", skill="adaptive-pedagogy"
    )
    brief = _learner_brief(context)
    brief["task_rationale"] = context.task.rationale

    agent = create_agent(
        agent_model(context.model, "adaptive_pedagogy"),
        skills=_registry("adaptive-pedagogy"),
        system_prompt=PEDAGOGY_PROMPT,
        pinned_constraints=skill_constraints(
            "adaptive-pedagogy", PEDAGOGY_RESOURCES, stage_artifacts=False
        ),
        name="adaptive-pedagogy",
    )
    parsed = extract_json(
        message_text(
            await invoke_agent(
                agent,
                HumanMessage(json.dumps(brief, ensure_ascii=False)),
                context.runtime,
                agent_name="adaptive_pedagogy",
                recursion_limit=10,
            )
        )
    ) or {}

    text = str(parsed.get("text") or "").strip()
    if not text:
        raise ProviderError("adaptive-pedagogy returned no learner-facing text")

    safe_text, withheld = _guarded(text, context)
    emit(context.runtime, "agent.output", agent="adaptive_pedagogy", message=safe_text)

    return ProviderResult(
        learner_message=safe_text,
        data={
            "text": safe_text,
            "strategy": str(parsed.get("strategy") or "explain"),
            "next_step": str(parsed.get("next_step") or ""),
            "withheld_for_leakage": withheld,
        },
        persist_as="adaptive_pedagogy",
        detail=f"教学策略：{parsed.get('strategy') or 'explain'}",
        warnings=["生成内容触发泄题保护，已改用提示阶梯"] if withheld else [],
    )


@register("answer_user")
async def answer_user(context: ProviderContext) -> ProviderResult:
    """Answer a direct follow-up question (``dialog.answer``)."""

    if context.model is None:
        raise ProviderError("knowledge-qa requires a model")

    question = str(context.user_message.get("message") or "").strip()
    if not question:
        raise ProviderError("there is no learner question to answer")

    payload = {
        "question": question,
        "learner_state": _learner_brief(context),
        "lesson_intro": context.result_of("lecture_hook").get("html") or "",
        "lecture_deck": dict(context.result_of("interactive_lecture_deck")),
    }
    agent = create_agent(
        agent_model(context.model, "answer_user"),
        system_prompt=QA_PROMPT,
        name="knowledge-qa",
    )
    parsed = extract_json(
        message_text(
            await invoke_agent(
                agent,
                HumanMessage(json.dumps(payload, ensure_ascii=False)),
                context.runtime,
                agent_name="answer_user",
                recursion_limit=8,
            )
        )
    ) or {}

    text = str(parsed.get("text") or "").strip()
    if not text:
        raise ProviderError("knowledge-qa returned no answer text")

    safe_text, withheld = _guarded(text, context)
    emit(context.runtime, "agent.output", agent="answer_user", message=safe_text)

    return ProviderResult(
        learner_message=safe_text,
        evidence=[
            EvidenceRecord(
                learner_id=context.learner_id,
                knowledge_point=context.knowledge_point_id,
                signal=Signal.SELF_REPORT,
                source_agent="answer_user",
                task_id=context.task_id,
                summary=question[:200],
            )
        ],
        data={"text": safe_text, "out_of_scope": bool(parsed.get("out_of_scope"))},
        persist_as="answer_user",
        detail="已回答学习者的追问",
        warnings=["回答触发泄题保护，已改用提示阶梯"] if withheld else [],
    )


@register("negotiator")
async def negotiator(context: ProviderContext) -> ProviderResult:
    """Write the one sentence that precedes deviating from the request.

    The system is allowed not to do what was literally asked; it is not allowed
    to do so quietly. Guardrails reject a deviating plan with no negotiation, so
    this provider exists to produce one.
    """

    brief = _learner_brief(context)
    brief["intended_action"] = context.task.inputs.get("intended_action") or ""
    brief["intended_reason"] = context.task.rationale

    if context.model is None:
        # A blunt but honest sentence beats stalling on a missing model.
        text = (
            f"你想学的是{context.goal.topic}。我看到相关的前置知识还不牢，"
            f"建议先补一下再回来——你也可以让我直接讲，我就按你说的来。"
        )
        return ProviderResult(
            learner_message=text,
            data={"text": text, "degraded": True},
            persist_as="negotiation",
            detail="使用降级协商话术",
        )

    agent = create_agent(
        agent_model(context.model, "negotiator"),
        system_prompt=NEGOTIATION_PROMPT,
        name="negotiation",
    )
    parsed = extract_json(
        message_text(
            await invoke_agent(
                agent,
                HumanMessage(json.dumps(brief, ensure_ascii=False)),
                context.runtime,
                agent_name="negotiator",
                recursion_limit=6,
            )
        )
    ) or {}
    text = str(parsed.get("text") or "").strip()
    if not text:
        raise ProviderError("negotiation returned no text")

    emit(context.runtime, "negotiation.requested", agent="negotiator", message=text)
    return ProviderResult(
        learner_message=text,
        data={"text": text},
        persist_as="negotiation",
        detail="已生成协商话术",
    )


__all__ = ["adaptive_pedagogy", "answer_user", "negotiator"]
