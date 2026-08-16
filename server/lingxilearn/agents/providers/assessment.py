"""Providers that generate, grade and interpret assessment.

Grading is deliberately not a model call: :mod:`lingxilearn.agents.quiz_grading`
is the authority, and the model's job is to explain a verdict it did not
produce. That is what makes the evidence these providers emit trustworthy enough
for state_updater to move a mastery number on.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from lingxigraph import FilesystemSkillSource, HumanMessage, SkillRegistry, create_agent

from ...config import REPO_ROOT
from ...state.evidence import EvidenceRecord, Signal
from ..contracts import QuizGenerationResult, extract_json
from ..model_runtime import agent_model, emit, invoke_agent, message_text
from ..quiz_grading import grade_quiz
from ..skill_runtime import progressive_skill_prompt, skill_constraints
from .base import ProviderContext, ProviderError, ProviderResult, register

logger = logging.getLogger(__name__)

QUIZ_RESOURCES = (
    "references/quiz-generation-input.schema.json",
    "references/quiz-design-rules.md",
    "references/quality-gate.md",
    "references/quiz-generation-result.schema.json",
    "scripts/quiz_contract.py",
)

QUIZ_PROMPT = progressive_skill_prompt(
    "quiz-generator",
    "quiz-generation-result.v1",
    referenced_resources=QUIZ_RESOURCES,
    artifact_instructions="""这是实际的知识点测评生成 Agent。严格使用 quiz-generation-input.v2，
默认生成 3–4 道基于已讲授材料的诊断题；通过 scripts/quiz_contract.py 的规则检查答案结构和总分。
只返回 quiz-generation-result.v1 JSON，不返回 Markdown。
答案、解析、keywords 和 assumptions 是内部字段。""",
    stage_artifacts=False,
)

RETRIEVAL_RESOURCES = (
    "references/retrieval-practice-builder-task.schema.json",
    "references/retrieval-practice-builder-result.schema.json",
)

RETRIEVAL_PROMPT = progressive_skill_prompt(
    "retrieval-practice-builder",
    "retrieval-practice-builder-result.v1",
    referenced_resources=RETRIEVAL_RESOURCES,
    artifact_instructions="""这是检索练习构建 Agent。基于已讲授内容和学习证据，产出一道检索、迁移、
边界或误区辨析任务。优先针对档案里未消解的误区。只返回结构化 JSON。""",
    stage_artifacts=False,
)

ASSESSOR_RESOURCES = (
    "references/formative-assessor-task.schema.json",
    "references/formative-assessor-result.schema.json",
)

ASSESSOR_PROMPT = progressive_skill_prompt(
    "formative-assessor",
    "formative-assessor-result.v1",
    referenced_resources=ASSESSOR_RESOURCES,
    artifact_instructions="""这是形成性评估解释 Agent。把已判分的确定性证据翻译成误区模式和
教学信号。不要重新判分，不要写面向学习者的回复，不要从单次行为推断永久掌握。只返回结构化 JSON。""",
    stage_artifacts=False,
)


def _registry(name: str) -> SkillRegistry:
    return SkillRegistry((FilesystemSkillSource(REPO_ROOT / "skills" / name),))


def _learner_state(context: ProviderContext) -> dict[str, Any]:
    profile = context.profile_of()
    system = dict(profile.get("system") or {})
    return {
        "knowledge_point_id": context.knowledge_point_id,
        "knowledge_point": profile.get("knowledge_point") or context.knowledge_point_id,
        "mastery": profile.get("mastery"),
        "learning_state": profile.get("learning_state"),
        "evidence_count": system.get("evidence_count"),
        "misconceptions": system.get("misconceptions") or [],
        "recent_performance": profile.get("recent_performance") or {},
    }


@register(
    "quiz_generator",
    display_name="知识检测",
    description="生成检查理解的题目",
    execution_kind="model",
)
async def quiz_generator(context: ProviderContext) -> ProviderResult:
    """Produce a diagnostic quiz over what has been taught (``assess.generate``)."""

    if context.model is None or context.artifacts is None:
        raise ProviderError("quiz-generator requires a model and an artifact store")

    emit(context.runtime, "agent.started", agent="quiz_generator", skill="quiz-generator")
    request = {
        "schema_version": "quiz-generation-input.v2",
        "task_id": context.task_id,
        "intent": {
            "topic": context.goal.topic,
            "learning_objective": context.goal.expected_outcome,
        },
        "learner_state": _learner_state(context),
        "lesson_intro": context.result_of("lecture_hook").get("html") or "",
        "interactive_lecture_deck": dict(context.result_of("interactive_lecture_deck")),
    }
    agent = create_agent(
        agent_model(context.model, "quiz_generator"),
        skills=_registry("quiz-generator"),
        system_prompt=QUIZ_PROMPT,
        pinned_constraints=skill_constraints(
            "quiz-generator", QUIZ_RESOURCES, stage_artifacts=False
        ),
        name="quiz-generator",
    )
    parsed = extract_json(
        message_text(
            await invoke_agent(
                agent,
                HumanMessage(json.dumps(request, ensure_ascii=False)),
                context.runtime,
                agent_name="quiz_generator",
                recursion_limit=20,
            )
        )
    )
    if not parsed:
        raise ProviderError("quiz-generator returned no JSON result")

    quiz = QuizGenerationResult.model_validate(parsed)
    value = quiz.model_dump(mode="json")
    validation = await context.artifacts.validate_quiz_result(context.task_id, value)
    if not validation["ok"]:
        raise ProviderError(f"quiz-generator contract validation failed: {validation['output']}")

    emit(
        context.runtime,
        "quiz.ready",
        agent="quiz_generator",
        question_count=len(quiz.questions),
        validation=validation,
    )
    return ProviderResult(
        learner_message=f"我出了 {len(quiz.questions)} 道题，做完我就知道该往哪里补。",
        artifacts=["quiz"],
        validations={"quiz": True},
        data=value,
        persist_as="quiz_generator",
        detail=f"生成 {len(quiz.questions)} 道诊断题",
    )


@register(
    "retrieval_practice",
    display_name="检索练习",
    description="安排巩固记忆的练习",
    execution_kind="model",
)
async def retrieval_practice(context: ProviderContext) -> ProviderResult:
    """Build one retrieval/transfer task from evidence (``assess.generate``).

    Distinct from ``quiz_generator``: this targets a specific misconception or
    a due review rather than covering freshly taught material.
    """

    if context.model is None:
        raise ProviderError("retrieval-practice-builder requires a model")

    emit(
        context.runtime,
        "agent.started",
        agent="retrieval_practice",
        skill="retrieval-practice-builder",
    )
    request = {
        "task_id": context.task_id,
        "learner_state": _learner_state(context),
        "topic": context.goal.topic,
        "taught_content": context.result_of("lecture_hook").get("html") or "",
    }
    agent = create_agent(
        agent_model(context.model, "retrieval_practice"),
        skills=_registry("retrieval-practice-builder"),
        system_prompt=RETRIEVAL_PROMPT,
        pinned_constraints=skill_constraints(
            "retrieval-practice-builder", RETRIEVAL_RESOURCES, stage_artifacts=False
        ),
        name="retrieval-practice-builder",
    )
    parsed = extract_json(
        message_text(
            await invoke_agent(
                agent,
                HumanMessage(json.dumps(request, ensure_ascii=False)),
                context.runtime,
                agent_name="retrieval_practice",
                recursion_limit=12,
            )
        )
    )
    if not parsed:
        raise ProviderError("retrieval-practice-builder returned no JSON result")

    return ProviderResult(
        learner_message=str(parsed.get("prompt") or "来一道检索练习。"),
        data=parsed,
        persist_as="retrieval_practice",
        detail="已生成一道检索练习",
    )


@register(
    "deterministic_grader",
    display_name="自动判分",
    description="规则判分，不调用模型",
    execution_kind="deterministic",
)
async def deterministic_grader(context: ProviderContext) -> ProviderResult:
    """Grade a submitted attempt by rule and emit the evidence (``assess.grade``).

    No model is involved in deciding a score, and every graded item becomes one
    evidence row — including the ones the learner skipped, because a blank is an
    observation too and dropping it would freeze the evidence count.
    """

    submission = dict(context.task.inputs.get("submission") or {})
    answers = dict(submission.get("answers") or {})
    quiz = dict(context.result_of("quiz_generator"))
    if not quiz.get("questions"):
        raise ProviderError("there is no quiz to grade")

    graded = grade_quiz(quiz, answers)
    point = context.knowledge_point_id
    hint_level = int(submission.get("hint_level") or 0)

    evidence: list[EvidenceRecord] = []
    for item in graded["per_question"]:
        points = max(1, int(item["points"]))
        score = round(float(item["score"]) / points, 4)
        if not item["answered"]:
            signal = Signal.NO_ANSWER
        elif item["correct"]:
            signal = Signal.CORRECT
        else:
            signal = Signal.INCORRECT
        evidence.append(
            EvidenceRecord(
                learner_id=context.learner_id,
                knowledge_point=point,
                signal=signal,
                source_agent="deterministic_grader",
                score=score,
                misconceptions=tuple(item["misconceptions"]),
                hint_level=hint_level,
                task_id=context.task_id,
                summary=f"{item['id']}：{'对' if item['correct'] else '错'}",
                locator={"item": item["id"]},
            )
        )

    total_points = max(1, int(graded["total_points"]))
    overall = round(float(graded["total_score"]) / total_points, 4)
    correct_count = sum(1 for item in graded["per_question"] if item["correct"])

    emit(
        context.runtime,
        "assessment.graded",
        agent="deterministic_grader",
        overall=overall,
        item_count=len(graded["per_question"]),
    )
    return ProviderResult(
        learner_message=f"判分完成：{correct_count}/{len(graded['per_question'])} 题正确。",
        evidence=evidence,
        data={**graded, "overall": overall, "submission_id": submission.get("submission_id", "")},
        persist_as="grading",
        detail=f"判分 {len(graded['per_question'])} 题，总体 {overall:.2f}",
    )


@register(
    "formative_assessor",
    display_name="形成性评估",
    description="评估当前掌握情况",
    execution_kind="model",
)
async def formative_assessor(context: ProviderContext) -> ProviderResult:
    """Interpret graded evidence into misconception patterns (``assess.interpret``)."""

    if context.model is None:
        raise ProviderError("formative-assessor requires a model")

    emit(
        context.runtime,
        "agent.started",
        agent="formative_assessor",
        skill="formative-assessor",
    )
    request = {
        "task_id": context.task_id,
        "learner_state": _learner_state(context),
        "grading": dict(context.result_of("grading")),
    }
    agent = create_agent(
        agent_model(context.model, "formative_assessor"),
        skills=_registry("formative-assessor"),
        system_prompt=ASSESSOR_PROMPT,
        pinned_constraints=skill_constraints(
            "formative-assessor", ASSESSOR_RESOURCES, stage_artifacts=False
        ),
        name="formative-assessor",
    )
    parsed = extract_json(
        message_text(
            await invoke_agent(
                agent,
                HumanMessage(json.dumps(request, ensure_ascii=False)),
                context.runtime,
                agent_name="formative_assessor",
                recursion_limit=12,
            )
        )
    )
    if not parsed:
        raise ProviderError("formative-assessor returned no JSON result")

    patterns = [str(item) for item in (parsed.get("error_patterns") or [])]
    evidence = (
        [
            EvidenceRecord(
                learner_id=context.learner_id,
                knowledge_point=context.knowledge_point_id,
                signal=Signal.ERROR_PATTERN,
                source_agent="formative_assessor",
                misconceptions=tuple(patterns),
                task_id=context.task_id,
                summary=str(parsed.get("summary") or "识别到错误模式"),
                payload={"patterns": patterns},
            )
        ]
        if patterns
        else []
    )

    return ProviderResult(
        evidence=evidence,
        data=parsed,
        persist_as="formative_assessment",
        detail=f"识别到 {len(patterns)} 个错误模式",
    )


__all__ = [
    "deterministic_grader",
    "formative_assessor",
    "quiz_generator",
    "retrieval_practice",
]
