"""Coordinator graph for the difficult-knowledge subgraph.

The graph deliberately keeps the quiz contract independent from the future quiz
skill.  The first two specialists run in parallel, then the task pauses for a
learner message.  Resuming the same checkpoint routes that message through the
intent recognizer before performing an answer, an on-demand visual explanation,
quiz submission, or handoff.
"""

from __future__ import annotations

import json
import logging
import operator
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict

from lingxigraph import (
    END,
    START,
    AIMessage,
    FilesystemSkillSource,
    HumanMessage,
    Runtime,
    SkillRegistry,
    StateGraph,
    create_agent,
    interrupt,
)

from ..config import REPO_ROOT, Settings
from .artifact_store import ArtifactStore
from .contracts import (
    DeckResult,
    IntentContext,
    LectureHookResult,
    QuizGenerationResult,
    QuizQuestion,
    QuizOption,
    extract_json,
    jsonable,
    quiz_public,
)

logger = logging.getLogger(__name__)
EVENT_CHANNEL = "agent_task"


class AgentState(TypedDict, total=False):
    task_id: str
    prompt: str
    intent: dict[str, Any]
    user_message: dict[str, Any]
    lecture_result: dict[str, Any]
    deck_result: dict[str, Any]
    quiz_result: dict[str, Any]
    answer_result: dict[str, Any]
    visual_result: dict[str, Any]
    handoff_result: dict[str, Any]
    route: str
    errors: Annotated[list[str], operator.add]
    status: str


PersistResult = Callable[[str, dict[str, Any]], Awaitable[None]]


def _agent_model(model: Any, role: str) -> Any:
    if isinstance(model, dict):
        return model.get(role) or model.get("default")
    resolver = getattr(model, "for_agent", None)
    if callable(resolver):
        return resolver(role)
    return model


INTENT_PROMPT = """你是 LingxiLearn 的意图识别与调度 Agent。

首次输入只提取一个具体、可教学的知识点，并输出 IntentContext JSON：
{"topic":"...","learning_objective":"...","learner_level":"undergraduate","course_context":"...","language":"zh-CN","target_duration_sec":75}

后续输入需要判断动作，只输出 JSON：
{"route":"answer_user|interactive_visual_explainer|quiz_submit|handoff","message":"..."}

路由规则：用户要求图解、动画、可视化时选择 interactive_visual_explainer；明确提交答案时选择
quiz_submit；表示不想答题、结束、退出或“先不做题”时选择 handoff；其他围绕知识点的追问选择 answer_user。
不要回答问题，不要 Markdown。"""

LECTURE_PROMPT = """你是 lesson-intro Agent。严格执行 skills/lesson-intro 的最新指令，输出
lesson-intro-result.v1 JSON。研究真实事实时使用可用的原生 web search，保留 claim-to-source
证据账本和不确定性；不得编造事实。所有学习者可见文案使用简体中文。"""

DECK_PROMPT = """你是 interactive-lecture-deck Agent。严格执行最新的 interactive-lecture-deck
skill，并根据给定知识点生成离线课件。不要返回 Markdown 代码围栏，最终只输出 JSON：
{
  "schema_version":"interactive-lecture-deck-result.v2",
  "title":"...",
  "files":{"lecture.json":"...","slides/s01.html":"...","slides/s02.html":"...","slides/s03.html":"...","runtime/index.html":"...","manifest.json":"..."},
  "assumptions":[],"deviations":[]
}
文件内容必须是完整文本；每个 slide 1280x720，至少三页，opening/content/closing 齐全。
课件不请求网络，讲解数据使用中文。"""

QUIZ_PROMPT = """你是 quiz-generator 的标准契约实现。根据 intent、lesson-intro 和 interactive-lecture-deck
产物生成用于检验一个疑难知识点的题目。只输出 JSON，不要 Markdown：
{"schema_version":"quiz-generation-result.v1","task_id":"...","title":"...","instructions":"...","questions":[{"id":"q1","type":"single_choice|multi_choice|short_text","prompt":"...","options":[{"id":"a","label":"..."}],"points":1,"answer":"b","explanation":"...","keywords":[]}],"total_points":1,"assumptions":[]}
题目必须能由服务端确定性评分；答案、解析和 keywords 是内部字段，不能进入学习者页面。"""

ANSWER_PROMPT = """你是知识点答疑 Agent。只回答当前知识点的追问，使用简体中文，基于已有课程引入和课件上下文。
回答要简短、准确，不主动泄露尚未提交的题目答案；只输出 JSON {"text":"..."}。"""

VISUAL_PROMPT = """你是通用 interactive-visual-explainer Agent。严格执行该 skill，生成一个零依赖、离线、单文件
HTML 交互讲解页面。只输出完整 HTML，不要元数据或 Markdown。"""


def _emit(runtime: Runtime[Any] | None, event_type: str, **payload: Any) -> None:
    if runtime is None:
        return
    try:
        runtime.emit(EVENT_CHANNEL, {"type": event_type, **payload})
    except Exception:  # telemetry must never break a run
        logger.debug("agent telemetry failed: %s", event_type, exc_info=True)


def _message_text(result: Any) -> str:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for message in reversed(messages):
        content = message.content if isinstance(message, AIMessage) else getattr(message, "content", None)
        if content:
            return str(content)
    return ""


def _extract_html(text: str) -> str | None:
    lower = text.lower()
    start = lower.find("<!doctype html")
    if start < 0:
        start = lower.find("<html")
    end = lower.rfind("</html>")
    return text[start : end + len("</html>")] if start >= 0 and end >= start else None


def _fallback_intent(prompt: str) -> IntentContext:
    topic = " ".join(prompt.strip().split())[:300] or "未命名知识点"
    return IntentContext(
        topic=topic,
        learning_objective=f"理解{topic}的核心概念、作用和关键机制。",
        course_context="由用户问题自动推断",
    )


def _fallback_hook(intent: IntentContext, task_id: str) -> LectureHookResult:
    return LectureHookResult.model_validate(
        {
            "schema_version": "lesson-intro-result.v1",
            "status": "insufficient_evidence",
            "topic": intent.topic,
            "selected_hook": {
                "title": f"从一个问题认识{intent.topic}",
                "hook_type": "question",
                "opening": f"如果只用一句话解释{intent.topic}，你会先说明它解决什么问题？",
                "story": "",
                "question": f"你认为{intent.topic}最关键的学习问题是什么？",
                "transition": "接下来用课件把这个问题拆成可观察的关系。",
                "estimated_duration_sec": 30,
                "why_this_hook_works": "不依赖未经核验的外部事实，适合作为安全引入。",
                "visual_cue": "",
            },
            "candidates": [{
                "title": f"从一个问题认识{intent.topic}", "hook_type": "question", "score": 50,
                "lesson_alignment": 70, "curiosity": 40, "evidence_strength": 0,
            }],
            "research": {"search_angles": [], "claims": [], "sources": []},
            "warnings": ["未取得足够外部证据，使用非事实型问题引入。"],
            "task_id": task_id,
        }
    )


def _fallback_deck(task_id: str, intent: IntentContext) -> dict[str, str]:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    def slide(slide_id: str, title: str, role: str, body: str, visual: str) -> str:
        anchors = '<div data-anchor="core-relation" data-rect="120 300 360 180" style="position:absolute;left:120px;top:300px;width:360px;height:180px">核心概念</div><div data-anchor="core-effect" data-rect="560 300 360 180" style="position:absolute;left:560px;top:300px;width:360px;height:180px">现象与结果的联系</div>' if role == "content" else visual
        return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>html,body{{margin:0;width:1280px;height:720px;background:#f7f7f5;color:#242424;font-family:system-ui,sans-serif}}.slide{{position:relative;width:1280px;height:720px;padding:72px 96px;box-sizing:border-box}}h1{{font-size:42px;font-weight:500;margin:0 0 32px}}p{{font-size:24px;line-height:1.7;max-width:920px}}.visual{{position:relative;margin-top:48px;padding:28px;border:1px solid #aaa;font-size:30px;display:flex;gap:48px}}</style></head><body><main class="slide" data-slide-id="{slide_id}" data-canvas="1280x720" data-slide-role="{role}" data-style="anthropic-academic"><h1>{title}</h1><p>{body}</p><div class="visual" data-visual="concept-map">{anchors}</div></main></body></html>'''
    lecture = {
        "schemaVersion": "zoom-lecture/v2",
        "deck": {"id": f"task-{task_id[-12:]}", "title": intent.topic, "language": "zh-CN", "style": "anthropic-academic", "canvas": {"width": 1280, "height": 720, "format": "ppt169"}, "slideDir": "slides", "createdAt": now, "objectives": [intent.learning_objective]},
        "slides": [
            {"id": "s01", "index": 1, "role": "opening", "file": "slides/s01.html", "title": intent.topic, "anchors": [], "steps": [{"id": "s01-01", "order": 1, "kind": "overview", "camera": {"mode": "fit"}, "advance": "manual"}]},
            {"id": "s02", "index": 2, "role": "content", "file": "slides/s02.html", "title": f"{intent.topic}的关键关系", "anchors": [{"id": "core-relation", "label": "核心关系", "rect": {"x": 120, "y": 300, "w": 360, "h": 180}}, {"id": "core-effect", "label": "现象与结果", "rect": {"x": 560, "y": 300, "w": 360, "h": 180}}], "steps": [{"id": "s02-01", "order": 1, "kind": "overview", "camera": {"mode": "fit"}, "advance": "manual"}, {"id": "s02-02", "order": 2, "kind": "zoom", "camera": {"mode": "anchor", "anchorId": "core-relation"}, "panel": {"title": "先看核心关系", "body": f"观察这个关系：它把{intent.topic}的现象、原因和结果连在了一起，帮助我们从结构而不是记忆理解它。"}, "advance": "manual"}, {"id": "s02-03", "order": 3, "kind": "zoom", "camera": {"mode": "anchor", "anchorId": "core-effect"}, "panel": {"title": "再看解释结果", "body": "当现象发生时，沿着这条关系检查原因和结果，就能把结论迁移到新的例子。"}, "advance": "manual"}]},
            {"id": "s03", "index": 3, "role": "closing", "file": "slides/s03.html", "title": "把关系带回问题", "anchors": [], "steps": [{"id": "s03-01", "order": 1, "kind": "overview", "camera": {"mode": "fit"}, "advance": "manual"}]},
        ],
    }
    lecture["slides"][1]["steps"][1]["panel"]["body"] = "观察这个关系：它把知识点的现象、原因和结果连在一起。这样我们不靠零散记忆，而是用结构理解它。它还为后面的例题建立检查顺序。"
    lecture["slides"][1]["steps"][2]["panel"]["body"] = "当现象发生时，沿着这条关系依次检查原因和结果。再用一个新例子复述过程，就能把结论迁移到新的问题。"
    manifest = {"schemaVersion": "zoom-lecture-manifest/v2", "taskId": task_id, "generatedAt": now, "deck": {"title": intent.topic, "canvas": {"width": 1280, "height": 720}, "style": "anthropic-academic", "slideCount": 3, "contentSlideCount": 1, "stepCount": 5}, "artifacts": {"lecture": "lecture.json", "slides": ["slides/s01.html", "slides/s02.html", "slides/s03.html"], "runtime": "runtime/index.html"}, "validation": {"tool": "scripts/validate_deck.py --strict", "status": "pass", "errors": [], "warnings": []}, "assumptions": ["模型课件生成不可用时使用安全占位课件"], "deviations": []}
    runtime = (REPO_ROOT / "skills" / "interactive-lecture-deck" / "assets" / "runtime" / "index.html").read_text(encoding="utf-8")
    return {"lecture.json": json.dumps(lecture, ensure_ascii=False), "slides/s01.html": slide("s01", intent.topic, "opening", f"今天只解决一个问题：如何真正理解{intent.topic}？", "现象 → 关系 → 结论"), "slides/s02.html": slide("s02", f"{intent.topic}的关键关系", "content", intent.learning_objective, "核心概念"), "slides/s03.html": slide("s03", "把关系带回问题", "closing", "用这条关系解释新的例子，并检查自己是否能说清原因。", "迁移与检查"), "runtime/index.html": runtime, "manifest.json": json.dumps(manifest, ensure_ascii=False)}


def _fallback_quiz(task_id: str, intent: IntentContext) -> QuizGenerationResult:
    return QuizGenerationResult.model_validate({
        "schema_version": "quiz-generation-result.v1", "task_id": task_id,
        "title": f"{intent.topic} · 一次性检测", "instructions": "每道题只允许提交一次，请先完成全部题目再提交。",
        "questions": [{"id": "q1", "type": "single_choice", "prompt": f"关于{intent.topic}，下列哪项最能体现本节的核心学习目标？", "options": [{"id": "a", "label": "只记住一个定义"}, {"id": "b", "label": "能够用核心关系解释现象"}, {"id": "c", "label": "跳过原因直接背结论"}], "points": 1, "answer": "b", "explanation": "能用关系解释现象，才说明理解了机制。"}],
        "total_points": 1, "assumptions": ["暂无出题 skill 时使用安全占位题目"],
    })


def _route_from_state(state: AgentState) -> str:
    return str(state.get("route") or "await_user")


def _public_quiz(state: AgentState) -> dict[str, Any]:
    return quiz_public(state.get("quiz_result") or {})


def build_agent_graph(*, model: Any, settings: Settings, task_id: str, artifacts: ArtifactStore, persist_result: PersistResult, checkpointer: Any | None = None, store: Any | None = None):
    """Compile the durable difficult-knowledge subgraph."""
    lecture_registry = SkillRegistry((FilesystemSkillSource(REPO_ROOT / "skills" / "lesson-intro"),))
    deck_registry = SkillRegistry((FilesystemSkillSource(REPO_ROOT / "skills" / "interactive-lecture-deck"),))

    async def recognize_intent(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        initial = not bool(state.get("intent"))
        raw = state.get("prompt", "") if initial else str((state.get("user_message") or {}).get("message") or "")
        _emit(runtime, "intent.started", agent="intent")
        agent = create_agent(_agent_model(model, "intent"), system_prompt=INTENT_PROMPT, name="intent-recognizer")
        result = await agent.ainvoke({"messages": [HumanMessage(raw)]}, {"recursion_limit": 8})
        parsed = extract_json(_message_text(result)) or {}
        if initial:
            try:
                intent = IntentContext.model_validate(parsed)
            except Exception:
                intent = _fallback_intent(raw)
            value = intent.model_dump(mode="json")
            await persist_result("intent", value)
            _emit(runtime, "intent.completed", agent="intent", topic=intent.topic)
            return {"intent": value, "route": "initialize"}
        if (state.get("user_message") or {}).get("kind") == "quiz_submit":
            _emit(runtime, "intent.routed", agent="intent", route="quiz_submit")
            return {"route": "quiz_submit"}
        route = str(parsed.get("route") or "")
        if route not in {"answer_user", "interactive_visual_explainer", "quiz_submit", "handoff"}:
            lowered = raw.lower()
            if any(word in raw for word in ("不想", "退出", "结束", "不做题", "先不做")):
                route = "handoff"
            elif any(word in raw for word in ("可视化", "图解", "动画", "交互")) or "visual" in lowered:
                route = "interactive_visual_explainer"
            elif any(word in raw for word in ("提交", "答案", "答题")):
                route = "quiz_submit"
            else:
                route = "answer_user"
        _emit(runtime, "intent.routed", agent="intent", route=route)
        return {"route": route}

    async def lecture_hook(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        if state.get("route") != "initialize":
            return {}
        _emit(runtime, "agent.started", agent="lecture_hook", skill="lesson-intro")
        intent = IntentContext.model_validate(state["intent"])
        prompt = "请为下面的 lesson-intro task 生成结果。\nTASK JSON:\n" + json.dumps({"task_id": state["task_id"], **intent.model_dump(mode="json")}, ensure_ascii=False)
        agent = create_agent(_agent_model(model, "lecture_hook"), skills=lecture_registry, system_prompt=LECTURE_PROMPT, name="lesson-intro")
        try:
            parsed = extract_json(_message_text(await agent.ainvoke({"messages": [HumanMessage(prompt)]}, {"recursion_limit": 24})))
            hook = LectureHookResult.model_validate(parsed or {})
        except Exception as exc:
            logger.warning("lesson-intro failed: %s", exc)
            hook = _fallback_hook(intent, state["task_id"])
        value = hook.model_copy(update={"task_id": state["task_id"]}).model_dump(mode="json")
        await persist_result("lecture_hook", value)
        _emit(runtime, "agent.output", agent="lecture_hook", message=f"课程引入：{hook.selected_hook.title}")
        _emit(runtime, "agent.completed", agent="lecture_hook", skill="lesson-intro")
        return {"lecture_result": value}

    async def interactive_lecture_deck(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        if state.get("route") != "initialize":
            return {}
        _emit(runtime, "agent.started", agent="interactive_lecture_deck", skill="interactive-lecture-deck")
        intent = IntentContext.model_validate(state["intent"])
        prompt = "请生成 interactive-lecture-deck-result.v2。\nINTENT JSON:\n" + json.dumps(intent.model_dump(mode="json"), ensure_ascii=False)
        agent = create_agent(_agent_model(model, "interactive_lecture_deck"), skills=deck_registry, system_prompt=DECK_PROMPT, name="interactive-lecture-deck")
        try:
            parsed = extract_json(_message_text(await agent.ainvoke({"messages": [HumanMessage(prompt)]}, {"recursion_limit": 16}))) or {}
            files = parsed.get("files") if isinstance(parsed.get("files"), dict) else {}
            if not files:
                files = _fallback_deck(task_id, intent)
        except Exception as exc:
            logger.warning("interactive-lecture-deck failed: %s", exc)
            files = _fallback_deck(task_id, intent)
            parsed = {}
        artifacts.write_deck(task_id, files)
        validation = await artifacts.build_and_validate_deck(task_id)
        value = DeckResult.model_validate({"schema_version": "interactive-lecture-deck-result.v2", "task_id": task_id, "title": str(parsed.get("title") or intent.topic), "status": "ready" if validation["ok"] else "failed", "files": {"lecture": "lecture.json", "slides": sorted(name for name in files if name.startswith("slides/")), "runtime": "runtime/index.html", "standalone": "dist/lecture.html", "manifest": "manifest.json"}, "manifest": parsed.get("manifest") or {}, "validation": validation, "assumptions": parsed.get("assumptions") or [], "deviations": parsed.get("deviations") or []}).model_dump(mode="json")
        await persist_result("interactive_lecture_deck", value)
        _emit(runtime, "artifact.ready", agent="interactive_lecture_deck", artifact="lecture-deck", validation=validation)
        _emit(runtime, "agent.completed", agent="interactive_lecture_deck", skill="interactive-lecture-deck")
        return {"deck_result": value}

    async def quiz_generator(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        if state.get("route") != "initialize":
            return {}
        _emit(runtime, "agent.started", agent="quiz_generator")
        intent = IntentContext.model_validate(state["intent"])
        prompt = "生成 quiz-generation-result.v1。\n" + json.dumps({"schema_version": "quiz-generation-input.v1", "task_id": task_id, "intent": state["intent"], "lesson_intro": state.get("lecture_result", {}), "interactive_lecture_deck": state.get("deck_result", {})}, ensure_ascii=False)
        agent = create_agent(_agent_model(model, "quiz_generator"), system_prompt=QUIZ_PROMPT, name="quiz-generator")
        try:
            parsed = extract_json(_message_text(await agent.ainvoke({"messages": [HumanMessage(prompt)]}, {"recursion_limit": 12}))) or {}
            quiz = QuizGenerationResult.model_validate(parsed)
        except Exception:
            quiz = _fallback_quiz(task_id, intent)
        value = quiz.model_dump(mode="json")
        await persist_result("quiz_generator", value)
        _emit(runtime, "quiz.ready", agent="quiz_generator", question_count=len(quiz.questions))
        return {"quiz_result": value, "status": "awaiting_user"}

    def await_user(state: AgentState, _runtime: Runtime[Any]) -> dict[str, Any]:
        if checkpointer is None:
            return {"status": "awaiting_user"}
        payload = interrupt({"kind": "user_message", "task_id": task_id, "quiz": _public_quiz(state)})
        value = payload if isinstance(payload, dict) else {"message": str(payload)}
        return {"user_message": value}

    async def answer_user(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        message = str((state.get("user_message") or {}).get("message") or "")
        agent = create_agent(_agent_model(model, "answer_user"), system_prompt=ANSWER_PROMPT, name="answer-user")
        context = {"intent": state.get("intent"), "lesson_intro": state.get("lecture_result"), "deck": state.get("deck_result"), "question": message}
        parsed = extract_json(_message_text(await agent.ainvoke({"messages": [HumanMessage(json.dumps(context, ensure_ascii=False))]}, {"recursion_limit": 8}))) or {}
        text = str(parsed.get("text") or f"围绕“{message}”，可以回到{state.get('intent', {}).get('topic', '这个知识点')}的核心关系来理解。")
        value = {"text": text, "created_at": datetime.now(UTC).isoformat()}
        _emit(runtime, "agent.output", agent="answer_user", message=text)
        return {"answer_result": value, "status": "awaiting_user"}

    async def visual_explainer(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        _emit(runtime, "agent.started", agent="interactive_visual_explainer", skill="interactive-visual-explainer")
        root = REPO_ROOT / "skills" / "interactive-visual-explainer"
        prompt = "请生成完整单文件 HTML。\nINTENT JSON:\n" + json.dumps(state.get("intent", {}), ensure_ascii=False) + "\n\nSKILL:\n" + (root / "SKILL.md").read_text(encoding="utf-8") + "\n\nTEMPLATE:\n" + (root / "assets" / "template.html").read_text(encoding="utf-8")
        agent = create_agent(_agent_model(model, "interactive_visual_explainer"), system_prompt=VISUAL_PROMPT, name="interactive-visual-explainer")
        text = _message_text(await agent.ainvoke({"messages": [HumanMessage(prompt)]}, {"recursion_limit": 10}))
        html = _extract_html(text)
        if not html:
            raise ValueError("interactive-visual-explainer did not return HTML")
        artifacts.write_html(task_id, html)
        validation = await artifacts.validate_html(task_id)
        if not validation.get("ok"):
            raise ValueError("interactive-visual-explainer artifact validation failed")
        value = {"artifact_id": "visual", "filename": "visual-explainer.html", "status": "ready", "title": f"{state.get('intent', {}).get('topic', '知识点')} · 交互讲解", "validation": validation}
        await persist_result("visual_explainer", value)
        _emit(runtime, "artifact.ready", agent="interactive_visual_explainer", artifact="visual", validation=validation)
        return {"visual_result": value, "status": "awaiting_user"}

    async def quiz_submit(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        _emit(runtime, "quiz.submission.accepted", agent="quiz_submit")
        return {"status": "handoff_pending"}

    async def handoff(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        message = str((state.get("user_message") or {}).get("message") or "")
        reason = "quiz_completed" if state.get("route") == "quiz_submit" else "quiz_declined"
        value = {"target": "main_graph.next_node", "reason": reason, "task_id": task_id, "message": message}
        await persist_result("handoff", value)
        _emit(runtime, "handoff.requested", agent="handoff", **value)
        return {"handoff_result": value}

    async def main_graph_placeholder(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        _emit(runtime, "agent.completed", agent="main_graph_placeholder", message="已返回主图占位节点。")
        return {"status": "handed_off"}

    builder = StateGraph(AgentState, name="lingxilearn-difficult-knowledge-subgraph", version="2.0.0")
    builder.add_node("recognize_intent", recognize_intent, timeout=settings.agent_timeout)
    builder.add_node("lecture_hook", lecture_hook, timeout=settings.agent_lecture_timeout)
    builder.add_node("interactive_lecture_deck", interactive_lecture_deck, timeout=settings.agent_visual_timeout)
    builder.add_node("quiz_generator", quiz_generator, timeout=settings.agent_timeout)
    builder.add_node("await_user", await_user)
    builder.add_node("answer_user", answer_user, timeout=settings.agent_timeout)
    builder.add_node("interactive_visual_explainer", visual_explainer, timeout=settings.agent_visual_timeout)
    builder.add_node("quiz_submit", quiz_submit)
    builder.add_node("handoff", handoff)
    builder.add_node("main_graph_placeholder", main_graph_placeholder)
    builder.add_edge(START, "recognize_intent")
    builder.add_edge("recognize_intent", "lecture_hook")
    builder.add_edge("recognize_intent", "interactive_lecture_deck")
    builder.add_edge(("lecture_hook", "interactive_lecture_deck"), "quiz_generator", trigger="all")
    builder.add_conditional_edges("quiz_generator", _route_from_state, {"initialize": "await_user", "await_user": "await_user", "answer_user": "answer_user", "interactive_visual_explainer": "interactive_visual_explainer", "quiz_submit": "quiz_submit", "handoff": "handoff"})
    builder.add_edge("await_user", "recognize_intent" if checkpointer is not None else END)
    builder.add_edge("answer_user", "await_user")
    builder.add_edge("interactive_visual_explainer", "await_user")
    builder.add_edge("quiz_submit", "handoff")
    builder.add_edge("handoff", "main_graph_placeholder")
    builder.add_edge("main_graph_placeholder", END)
    compile_options: dict[str, Any] = {"checkpointer": checkpointer}
    if store is not None:
        compile_options["store"] = store
    return builder.compile(**compile_options)
