"""Non-blocking specialist runners used by the knowledge deep-dive graph.

These functions deliberately return proposals or task-scoped artifacts.  The
service owns the durable sidecar row and the final database write; none of the
skills in this module can mutate learner state directly.
"""

from __future__ import annotations

import json
from typing import Any

try:
    import jsonschema
except ImportError:  # pragma: no cover - declared server dependency
    jsonschema = None

from lingxigraph import FilesystemSkillSource, HumanMessage, SkillRegistry, create_agent

from ..config import REPO_ROOT
from .artifact_store import ArtifactStore
from .contracts import QuizGenerationResult, extract_json
from .graph import _agent_model, _invoke_agent, _message_text
from .skill_runtime import (
    ArtifactDraft,
    progressive_skill_prompt,
    skill_constraints,
    staged_artifact_tools,
)

QUIZ_PROMPT = progressive_skill_prompt(
    "quiz-generator",
    "quiz-generation-result.v1",
    referenced_resources=(
        "references/quiz-generation-input.schema.json",
        "references/quiz-design-rules.md",
        "references/quality-gate.md",
        "references/quiz-generation-result.schema.json",
        "scripts/quiz_contract.py",
    ),
    artifact_instructions=(
        "这是后台测评预取 Agent。只处理已讲授材料，返回 quiz-generation-result.v1 JSON。"
        "不要等待学习者，也不要输出教学回复；答案、解析、keywords 和 assumptions 是内部字段。"
    ),
    stage_artifacts=False,
)

VISUAL_PROMPT = progressive_skill_prompt(
    "interactive-visual-explainer",
    "interactive-visual-explainer-delivery.v1.2",
    referenced_resources=(
        "references/interaction-patterns.md",
        "references/anti-patterns.md",
        "references/design-tokens.md",
        "references/svg-craft.md",
        "assets/template.html",
        "assets/lingxi.css",
    ),
    artifact_instructions=(
        "这是后台按需可视化 Agent。只生成 visual-explainer.html 并通过 stage_artifact_file 写入，"
        "不要返回 learner-facing 教学回复；宿主会在前台 fallback 之后发布单文件产物。"
    ),
)

REFLECTOR_PROMPT = progressive_skill_prompt(
    "learner-state-reflector",
    "learner-state-reflector-result.v1",
    referenced_resources=(
        "references/learner-state-reflector-task.schema.json",
        "references/learner-state-reflector-result.schema.json",
        "references/runtime-contract.md",
    ),
    artifact_instructions=(
        "这是后台学习状态反思 Agent。只返回 proposal JSON，不写数据库，不输出教学回复。"
        "保留原始 evidence ID，避免从单次行为推断永久掌握。"
    ),
    stage_artifacts=False,
)


def _skill_registry(name: str) -> SkillRegistry:
    return SkillRegistry((FilesystemSkillSource(REPO_ROOT / "skills" / name),))


def _validate_json_contract(name: str, value: dict[str, Any]) -> None:
    if jsonschema is None:
        raise ValueError("jsonschema is required for sidecar validation")
    schema_path = REPO_ROOT / "skills" / "learner-state-reflector" / "references" / name
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load sidecar schema: {name}") from exc
    except jsonschema.ValidationError as exc:
        raise ValueError(exc.message) from exc


async def build_quiz_prefetch(
    *, model: Any, task: dict[str, Any], artifacts: ArtifactStore, runtime: Any = None
) -> dict[str, Any]:
    """Generate and validate a private quiz artifact without blocking chat."""

    request = {
        "schema_version": "quiz-generation-input.v2",
        "task_id": task["id"],
        "intent": task.get("intent") or {},
        "lesson_intro": (task.get("lecture_result") or {}).get("html") or "",
        "interactive_lecture_deck": task.get("deck_result") or {},
    }
    agent = create_agent(
        _agent_model(model, "quiz_generator"),
        skills=_skill_registry("quiz-generator"),
        system_prompt=QUIZ_PROMPT,
        pinned_constraints=skill_constraints(
            "quiz-generator",
            (
                "references/quiz-generation-input.schema.json",
                "references/quiz-design-rules.md",
                "references/quality-gate.md",
                "references/quiz-generation-result.schema.json",
                "scripts/quiz_contract.py",
            ),
            stage_artifacts=False,
        ),
        name="quiz-generator",
    )
    result = await _invoke_agent(
        agent,
        HumanMessage(json.dumps(request, ensure_ascii=False)),
        runtime,
        agent_name="quiz_generator",
        recursion_limit=20,
    )
    parsed = extract_json(_message_text(result))
    if not parsed:
        raise ValueError("quiz-generator returned no JSON result")
    quiz = QuizGenerationResult.model_validate(parsed)
    value = quiz.model_dump(mode="json")
    validation = await artifacts.validate_quiz_result(task["id"], value)
    if not validation.get("ok"):
        raise ValueError(f"quiz-generator contract validation failed: {validation.get('output', validation)}")
    return value


async def build_visual_sidecar(
    *, model: Any, task: dict[str, Any], artifacts: ArtifactStore, runtime: Any = None
) -> dict[str, Any]:
    """Generate the requested single-file visual artifact after fallback text."""

    draft = ArtifactDraft(artifacts, task["id"], "visual")
    prompt = (
        "按 interactive-visual-explainer-delivery.v1.2 生成一个离线单文件可视化讲解。\n"
        "先读取 skill 和直接相关参考资料，选择一个主交互模式；通过 stage_artifact_file 写入"
        " visual-explainer.html，最后只返回 delivery receipt。\nINTENT JSON:\n"
        + json.dumps(task.get("intent") or {}, ensure_ascii=False)
        + "\nLESSON CONTEXT:\n"
        + json.dumps(
            {
                "lesson_intro": task.get("lecture_result") or {},
                "lecture_deck": task.get("deck_result") or {},
                "learner_message": task.get("user_message") or "",
            },
            ensure_ascii=False,
        )
    )
    agent = create_agent(
        _agent_model(model, "interactive_visual_explainer"),
        tools=staged_artifact_tools(draft),
        skills=_skill_registry("interactive-visual-explainer"),
        system_prompt=VISUAL_PROMPT,
        pinned_constraints=skill_constraints(
            "interactive-visual-explainer",
            (
                "references/interaction-patterns.md",
                "references/anti-patterns.md",
                "references/design-tokens.md",
                "references/svg-craft.md",
                "assets/template.html",
                "assets/lingxi.css",
            ),
        ),
        name="interactive-visual-explainer",
    )
    try:
        await _invoke_agent(
            agent,
            HumanMessage(prompt),
            runtime,
            agent_name="interactive_visual_explainer",
            recursion_limit=24,
            tool_permissions=("artifact:write",),
        )
        html = draft.snapshot().get("visual-explainer.html")
    finally:
        draft.cleanup()
    if not html:
        raise ValueError("interactive-visual-explainer did not return HTML")
    artifacts.write_html(task["id"], html)
    validation = await artifacts.validate_html(task["id"])
    if not validation.get("ok"):
        raise ValueError("interactive-visual-explainer artifact validation failed")
    return {
        "artifact_id": "visual",
        "filename": "visual-explainer.html",
        "status": "ready",
        "title": f"{(task.get('intent') or {}).get('topic', '知识点')} · 交互讲解",
        "validation": validation,
    }


async def build_learner_state_reflection(
    *,
    model: Any,
    task: dict[str, Any],
    events: list[dict[str, Any]],
    runtime: Any = None,
) -> dict[str, Any]:
    """Compress recent events into a proposal; the host decides persistence."""

    request = {
        "events": events[-120:],
        "prior_state": task.get("prior_state") or {},
        "topic": str((task.get("intent") or {}).get("topic") or task.get("prompt") or ""),
        "learning_objective": str((task.get("intent") or {}).get("learning_objective") or ""),
    }
    agent = create_agent(
        _agent_model(model, "learner_state_reflector"),
        skills=_skill_registry("learner-state-reflector"),
        system_prompt=REFLECTOR_PROMPT,
        pinned_constraints=skill_constraints(
            "learner-state-reflector",
            (
                "references/learner-state-reflector-task.schema.json",
                "references/learner-state-reflector-result.schema.json",
                "references/runtime-contract.md",
            ),
            stage_artifacts=False,
        ),
        name="learner-state-reflector",
    )
    result = await _invoke_agent(
        agent,
        HumanMessage(json.dumps(request, ensure_ascii=False)),
        runtime,
        agent_name="learner_state_reflector",
        recursion_limit=12,
    )
    parsed = extract_json(_message_text(result))
    if not parsed:
        raise ValueError("learner-state-reflector returned no JSON result")
    _validate_json_contract("learner-state-reflector-result.schema.json", parsed)
    return parsed


__all__ = [
    "build_learner_state_reflection",
    "build_quiz_prefetch",
    "build_visual_sidecar",
]
