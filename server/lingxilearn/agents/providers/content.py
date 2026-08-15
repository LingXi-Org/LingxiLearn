"""Providers that produce learner-facing artifacts.

Ported from the coordinator graph's specialist nodes with their prompts,
progressive-disclosure setup, staged-artifact tooling and recovery paths intact.
What was removed is the graph state they used to read (``if state["route"] !=
"initialize": return {}``) and the edges that decided when they ran — that
decision is now the orchestrator's, recomputed each round from the profile.

The recovery behaviour is deliberately preserved: a seeded fallback page before
generation starts, and a draft that survives a timeout, because a model that
runs out of budget mid-artifact should cost the learner a worse page, not the
page.
"""

from __future__ import annotations

import asyncio
import json
import logging
from html import escape

from lingxigraph import (
    FilesystemSkillSource,
    GraphRecursionError,
    HumanMessage,
    SkillRegistry,
    create_agent,
)
from lingxigraph.errors import GraphTimeoutError

from ...config import REPO_ROOT
from ..contracts import DeckResult, extract_json
from ..model_runtime import agent_model, emit, invoke_agent, message_text
from ..skill_runtime import (
    ArtifactDraft,
    progressive_skill_prompt,
    skill_constraints,
    staged_artifact_tools,
)
from .base import ProviderContext, ProviderError, ProviderResult, register

logger = logging.getLogger(__name__)

LESSON_INTRO_RESOURCES = (
    "references/tool-contracts.md",
    "references/html-design.md",
    "assets/example-page.html",
    "scripts/validate_output.py",
)

DECK_RESOURCES = (
    "references/task-contract.md",
    "references/design-system.md",
    "references/visual-authoring.md",
    "references/slide-authoring.md",
    "references/lecture-data.md",
    "references/zoom-contract.md",
)

VISUAL_RESOURCES = (
    "references/interaction-patterns.md",
    "references/anti-patterns.md",
    "references/design-tokens.md",
    "references/svg-craft.md",
    "assets/template.html",
    "assets/lingxi.css",
)

LECTURE_PROMPT = progressive_skill_prompt(
    "lesson-intro",
    "lesson-intro-html.v1",
    referenced_resources=LESSON_INTRO_RESOURCES,
    artifact_instructions="""这是课程引入 HTML 生成 Agent。当前 lesson-intro 只允许基于输入
上下文直接生成，禁止联网检索、禁止调用 web_search/web_fetch，也不要等待其他 Agent。先尽快生成并通过
stage_artifact_file 写入一个完整的 lesson-intro.html；如果内容较长，改用 stage_artifact_chunk
分块写入。HTML 必须是零依赖、简体中文、可直接打开的学习者页面。最后只返回包含 topic/status/warnings
的简短 JSON 回执，不要复制 HTML。""",
)

DECK_PROMPT = progressive_skill_prompt(
    "interactive-lecture-deck",
    "interactive-lecture-deck-result.v2.1",
    referenced_resources=DECK_RESOURCES,
    artifact_instructions="""这是分阶段课件生成 Agent。默认 problem 生成 5–7 页，
concept 生成 6–8 页，lesson 生成 8–12 页；必须有 opening/content/closing。
视觉大纲完成后，优先按 2–3 个文件一批调用
stage_artifact_files：先生成 slides，再生成 lecture.json 与 manifest.json。runtime/index.html
由宿主从 assets/runtime/index.html 原样预置；不要重复生成或覆盖它。不要生成 PNG/JPG、PowerPoint/
PPTX 或重复的 HTML/JSON 导出。dist/lecture.html 由服务端执行 standalone build，是唯一主要学习者
交付物。每页 slide 根节点下的直接内容块最多 8 个，绝不能超过 10 个；把装饰性元素合并进主视觉，
不要为了填满画布继续堆块。最终只返回简短 JSON receipt。""",
    batch_artifacts=True,
)

VISUAL_PROMPT = progressive_skill_prompt(
    "interactive-visual-explainer",
    "interactive-visual-explainer-delivery.v1.2",
    referenced_resources=VISUAL_RESOURCES,
    artifact_instructions="""这是单文件 artifact 生成。先选择一个主交互模式，再从最新模板构建
visual-explainer.html，并通过 stage_artifact_file 写入该文件。严格遵循
interactive-visual-explainer-delivery.v1.2：离线、无外部请求、支持明暗模式和打印，服务端会执行
palette 与 static check。最终只返回简短中文 delivery receipt，不要返回 HTML。""",
)


def _registry(name: str) -> SkillRegistry:
    return SkillRegistry((FilesystemSkillSource(REPO_ROOT / "skills" / name),))


def _teaching_context(context: ProviderContext) -> dict[str, object]:
    """The shared shape every content provider is briefed with.

    Providers read the profile rather than being handed a paragraph written by
    another agent — that is the rule the four state tables exist to enforce.
    """

    profile = context.profile_of()
    system = dict(profile.get("system") or {})
    return {
        "task_id": context.task_id,
        "topic": context.goal.topic,
        "knowledge_point": profile.get("knowledge_point") or context.knowledge_point_id,
        "knowledge_point_id": context.knowledge_point_id,
        "learning_objective": context.goal.expected_outcome,
        "constraints": list(context.goal.constraints),
        "language": "zh-CN",
        "learner_state": {
            "mastery": profile.get("mastery"),
            "learning_state": profile.get("learning_state"),
            "evidence_count": system.get("evidence_count"),
            "misconceptions": system.get("misconceptions") or [],
            "open_questions": profile.get("my_questions") or [],
        },
    }


_FALLBACK_PAGE = REPO_ROOT / "skills" / "lesson-intro" / "assets" / "fallback-page.html"


def _lesson_intro_fallback(topic: str, objective: str) -> str:
    """A valid page staged before generation, so interruption stays recoverable.

    Read from the skill's assets rather than embedded here: it is a real
    learner-facing page, and a page maintained as a Python string literal stops
    being maintained.
    """

    return (
        _FALLBACK_PAGE.read_text(encoding="utf-8")
        .replace("__TOPIC__", escape(topic))
        .replace("__OBJECTIVE__", escape(objective or f"理解{topic}的核心概念"))
    )


@register("lesson_intro")
async def lesson_intro(context: ProviderContext) -> ProviderResult:
    """Generate the course opening page (capability ``content.lesson_intro``)."""

    if context.artifacts is None or context.model is None:
        raise ProviderError("lesson-intro requires an artifact store and a model")

    brief = _teaching_context(context)
    topic = str(brief["topic"] or context.knowledge_point_id)
    emit(context.runtime, "agent.started", agent="lesson_intro", skill="lesson-intro")

    draft = ArtifactDraft(context.artifacts, context.task_id, "lesson-intro")
    fallback_html = _lesson_intro_fallback(topic, str(brief["learning_objective"] or ""))
    draft.write("lesson-intro.html", fallback_html)

    prompt = (
        "按 lesson-intro-html.v1 直接生成课程引入页面，不联网检索。先读取 skill 和直接相关资源，"
        "尽快通过 stage_artifact_file 写入 lesson-intro.html；"
        "内容较长时用 stage_artifact_chunk 分块写入，"
        "回读检查后只返回 JSON 回执。\nTASK JSON:\n"
        + json.dumps(brief, ensure_ascii=False)
    )
    agent = create_agent(
        agent_model(context.model, "lesson_intro"),
        tools=staged_artifact_tools(draft),
        skills=_registry("lesson-intro"),
        system_prompt=LECTURE_PROMPT,
        pinned_constraints=skill_constraints("lesson-intro", LESSON_INTRO_RESOURCES),
        name="lesson-intro",
    )

    configured = float(getattr(context.settings, "agent_lecture_timeout", 180.0))
    timeout = max(5.0, min(90.0, configured - 15.0))
    warnings: list[str] = []
    published = False
    try:
        try:
            response = message_text(
                await asyncio.wait_for(
                    invoke_agent(
                        agent,
                        HumanMessage(prompt),
                        context.runtime,
                        agent_name="lesson_intro",
                        recursion_limit=20,
                        tool_permissions=("artifact:write",),
                    ),
                    timeout=timeout,
                )
            )
        except (TimeoutError, GraphTimeoutError, GraphRecursionError):
            # The fallback is already staged and valid; publish it rather than
            # losing the artifact because the model ran long.
            emit(
                context.runtime,
                "agent.output",
                agent="lesson_intro",
                message="课程引入生成超时，已保留可用页面并继续发布。",
            )
            response = "{}"
            warnings.append("生成超时，已回退到可用课程引入页面")

        parsed = extract_json(response) or {}
        html = draft.snapshot().get("lesson-intro.html")
        if not html:
            raise ProviderError("lesson-intro did not stage lesson-intro.html")

        context.artifacts.write_lesson_intro_file(context.task_id, html)
        validation = await context.artifacts.validate_lesson_intro(context.task_id)
        if not validation["ok"]:
            # A model can stage a file successfully and still produce a malformed
            # page. Restore the validated fallback instead of shipping it.
            html = fallback_html
            draft.write("lesson-intro.html", html)
            context.artifacts.write_lesson_intro_file(context.task_id, html)
            validation = await context.artifacts.validate_lesson_intro(context.task_id)
            if not validation["ok"]:
                raise ProviderError(f"lesson-intro fallback validation failed: {validation}")
            warnings.append("生成页面未通过校验，已回退到可用课程引入页面")
        published = True
    finally:
        if published:
            draft.cleanup()

    emit(context.runtime, "agent.output", agent="lesson_intro", message="课程引入 HTML 已生成")
    emit(
        context.runtime,
        "artifact.ready",
        agent="lesson_intro",
        artifact="lesson-intro",
        path=f"{context.task_id}/lesson-intro.html",
    )
    return ProviderResult(
        learner_message="课程引入已经准备好，可以先看这一页。",
        artifacts=["lesson-intro"],
        validations={"lesson-intro": bool(validation["ok"])},
        data={
            "html": html,
            "topic": str(parsed.get("topic") or topic),
            "status": "ok",
            "warnings": [*warnings, *(parsed.get("warnings") or [])],
            "validation": validation,
        },
        persist_as="lecture_hook",
        detail="课程引入已生成并通过校验",
        warnings=warnings,
    )


@register("lecture_deck")
async def lecture_deck(context: ProviderContext) -> ProviderResult:
    """Generate the offline lecture deck (capability ``content.deck``)."""

    if context.artifacts is None or context.model is None:
        raise ProviderError("lecture-deck requires an artifact store and a model")

    brief = _teaching_context(context)
    emit(
        context.runtime,
        "agent.started",
        agent="lecture_deck",
        skill="interactive-lecture-deck",
    )

    draft = ArtifactDraft(context.artifacts, context.task_id, "deck")
    runtime_template = (
        REPO_ROOT / "skills" / "interactive-lecture-deck" / "assets" / "runtime" / "index.html"
    ).read_text(encoding="utf-8")
    draft.write("runtime/index.html", runtime_template)

    prompt = (
        "按最新分阶段协议完成 interactive-lecture-deck-result.v2.1。\n"
        "阶段 1：读取 skill 入口和直接相关 references。\n"
        "阶段 2：形成内部视觉大纲，决定页数、页角色、视觉关系和 zoom anchors。\n"
        "阶段 3：每次调用 stage_artifact_files 批量写入 2–3 个完整源文件；"
        "禁止逐张幻灯片单独进行一次模型续轮。\n"
        "阶段 3.1：宿主已预置 runtime/index.html；"
        "禁止读取 runtime 模板或重写 runtime/index.html。\n"
        "阶段 3.2：不要生成 PNG/JPG、PowerPoint/PPTX 或重复 HTML/JSON 导出；"
        "dist/lecture.html 由服务端构建。\n"
        "lecture.json 必须严格使用 v2：每个 anchor 都有 id、label、rect 对象；"
        '每个 step 都有 advance:"manual"；overview 的 camera 只能是 {"mode":"fit"}，'
        '不得带 anchorId/depth/scale/focus；zoom 才能使用 mode:"anchor"。'
        'anchor.rect 必须是对象 {"x":整数,"y":整数,"w":整数,"h":整数}，'
        "禁止写成 [x,y,w,h] 数组。每个 SVG 的每个 <text> 都必须带 class t/ts/th/tn。\n"
        "每页 slide 根节点下的直接内容块最多 8 个，绝不能超过 10 个；"
        "装饰元素应并入主视觉，不要单独堆叠。\n"
        "阶段 4：返回 JSON receipt，不要回传完整文件。\n"
        "TASK JSON:\n" + json.dumps(brief, ensure_ascii=False)
    )
    agent = create_agent(
        agent_model(context.model, "lecture_deck"),
        tools=staged_artifact_tools(draft, batch=True),
        skills=_registry("interactive-lecture-deck"),
        system_prompt=DECK_PROMPT,
        pinned_constraints=skill_constraints(
            "interactive-lecture-deck", DECK_RESOURCES, batch_artifacts=True
        )
        + (
            "The host already staged runtime/index.html; do not read "
            "assets/runtime/index.html and do not overwrite runtime/index.html.",
            "Generate 2-3 complete source files per stage_artifact_files call; do not use "
            "one model round-trip per slide.",
            "Do not generate PNG/JPG, PowerPoint/PPTX, or duplicate learner-facing HTML/JSON "
            "exports; the service builds dist/lecture.html as the primary delivery.",
            "Do not narrate progress between tool calls; emit the final JSON receipt only "
            "after source artifacts are staged.",
        ),
        name="interactive-lecture-deck",
    )

    recursion = int(getattr(context.settings, "agent_deck_recursion_limit", 80))
    warnings: list[str] = []
    try:
        parsed = extract_json(
            message_text(
                await asyncio.wait_for(
                    invoke_agent(
                        agent,
                        HumanMessage(prompt),
                        context.runtime,
                        agent_name="lecture_deck",
                        recursion_limit=recursion,
                        tool_permissions=("artifact:write",),
                    ),
                    timeout=float(getattr(context.settings, "agent_deck_timeout", 360.0)),
                )
            )
        ) or {}
    except (TimeoutError, GraphTimeoutError, GraphRecursionError):
        # Writes are durable in the draft: a child agent can stage its last file
        # and then run out of budget before emitting the receipt.
        staged = draft.list()
        emit(
            context.runtime,
            "agent.output",
            agent="lecture_deck",
            message=(
                "课件生成达到子 Agent 时间或步数上限，已写入文件将继续进入完整性校验。"
                f"当前已写入 {len(staged)} 个文件。"
            ),
        )
        warnings.append("生成达到时间或步数上限，已用已写入文件继续校验")
        parsed = {}

    files = draft.snapshot()
    if not files:
        raise ProviderError("interactive-lecture-deck did not stage any artifact")

    published = False
    try:
        context.artifacts.write_deck(context.task_id, files)
        validation = await context.artifacts.build_and_validate_deck(context.task_id)
        if not validation["ok"]:
            raise ProviderError(f"interactive-lecture-deck validation failed: {validation}")
        published = True
    finally:
        # Keep the draft when the build or validator fails so a later round can
        # retry the same normalized source.
        if published:
            draft.cleanup()

    value = DeckResult.model_validate(
        {
            "schema_version": "interactive-lecture-deck-result.v2.1",
            "task_id": context.task_id,
            "title": str(parsed.get("title") or brief["topic"]),
            "status": "ready",
            "files": {
                "lecture": "lecture.json",
                "slides": sorted(name for name in files if name.startswith("slides/")),
                "runtime": "runtime/index.html",
                "standalone": "dist/lecture.html",
                "manifest": "manifest.json",
            },
            "manifest": parsed.get("manifest") or {},
            "validation": validation,
            "assumptions": parsed.get("assumptions") or [],
            "deviations": parsed.get("deviations") or [],
        }
    ).model_dump(mode="json")

    emit(
        context.runtime,
        "artifact.ready",
        agent="lecture_deck",
        artifact="lecture-deck",
        validation=validation,
    )
    return ProviderResult(
        learner_message="讲义课件已经生成，可以逐页看。",
        artifacts=["lecture-deck"],
        validations={"lecture-deck": True},
        data=value,
        persist_as="interactive_lecture_deck",
        detail="课件已构建并通过校验",
        warnings=warnings,
    )


@register("visual_explainer")
async def visual_explainer(context: ProviderContext) -> ProviderResult:
    """Generate the single-file interactive explainer (``content.visual``)."""

    if context.artifacts is None or context.model is None:
        raise ProviderError("visual-explainer requires an artifact store and a model")

    brief = _teaching_context(context)
    emit(
        context.runtime,
        "agent.started",
        agent="visual_explainer",
        skill="interactive-visual-explainer",
    )

    draft = ArtifactDraft(context.artifacts, context.task_id, "visual")
    prompt = (
        "按最新协议完成 interactive-visual-explainer-delivery.v1.2。\n"
        "先读取 skill 和直接相关参考资料，选择一个主交互模式；然后通过 stage_artifact_file 写入"
        " visual-explainer.html，最后只返回 delivery receipt。\nTASK JSON:\n"
        + json.dumps(brief, ensure_ascii=False)
    )
    agent = create_agent(
        agent_model(context.model, "visual_explainer"),
        tools=staged_artifact_tools(draft),
        skills=_registry("interactive-visual-explainer"),
        system_prompt=VISUAL_PROMPT,
        pinned_constraints=skill_constraints(
            "interactive-visual-explainer", VISUAL_RESOURCES
        ),
        name="interactive-visual-explainer",
    )
    try:
        await asyncio.wait_for(
            invoke_agent(
                agent,
                HumanMessage(prompt),
                context.runtime,
                agent_name="visual_explainer",
                recursion_limit=24,
                tool_permissions=("artifact:write",),
            ),
            timeout=float(getattr(context.settings, "agent_visual_timeout", 240.0)),
        )
        html = draft.snapshot().get("visual-explainer.html")
    except (TimeoutError, GraphTimeoutError, GraphRecursionError):
        html = draft.snapshot().get("visual-explainer.html")
        emit(context.runtime, "agent.output", agent="visual_explainer", message="可视化讲解生成超时，已保留已写入的内容。")
    finally:
        draft.cleanup()

    if not html:
        raise ProviderError("interactive-visual-explainer did not return HTML")

    context.artifacts.write_html(context.task_id, html)
    validation = await context.artifacts.validate_html(context.task_id)
    if not validation.get("ok"):
        raise ProviderError("interactive-visual-explainer artifact validation failed")

    emit(
        context.runtime,
        "artifact.ready",
        agent="visual_explainer",
        artifact="visual",
        validation=validation,
    )
    return ProviderResult(
        learner_message="可视化讲解已经生成，可以直接操作看看。",
        artifacts=["visual"],
        validations={"visual": True},
        data={
            "artifact_id": "visual",
            "filename": "visual-explainer.html",
            "status": "ready",
            "title": f"{brief['topic']} · 交互讲解",
            "validation": validation,
        },
        persist_as="visual_explainer",
        detail="可视化讲解已生成并通过校验",
    )


__all__ = ["lecture_deck", "lesson_intro", "visual_explainer"]
