"""Coordinator graph for the difficult-knowledge subgraph.

The first specialists generate the real lesson HTML, lecture deck, and quiz skill
artifacts in parallel. The task then pauses for learner interaction.
"""

from __future__ import annotations

import json
import logging
import operator
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict

from lingxigraph import (
    END,
    START,
    AIMessage,
    EventKind,
    FilesystemSkillSource,
    HumanMessage,
    Runtime,
    SkillRegistry,
    StateGraph,
    ToolMessage,
    create_agent,
    interrupt,
)

from ..config import REPO_ROOT, Settings
from .artifact_store import ArtifactStore
from .contracts import (
    DeckResult,
    IntentContext,
    QuizGenerationResult,
    extract_json,
    quiz_public,
)
from .skill_runtime import (
    ArtifactDraft,
    progressive_skill_prompt,
    skill_constraints,
    staged_artifact_tools,
)
from .web_tools import build_web_tools

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
AgentNode = Callable[[AgentState, Runtime[Any]], Awaitable[dict[str, Any]]]


def _agent_model(model: Any, role: str) -> Any:
    if isinstance(model, dict):
        return model.get(role) or model.get("default")
    resolver = getattr(model, "for_agent", None)
    if callable(resolver):
        return resolver(role)
    return model


def _emit_agent_failure(
    runtime: Runtime[Any], agent_name: str, exc: BaseException
) -> None:
    """Emit one correctly attributed failure even when siblings run in parallel."""

    _emit(
        runtime,
        "agent.failed",
        agent=agent_name,
        error_type=type(exc).__name__,
        message=str(exc) or type(exc).__name__,
    )


def _trace_agent_node(agent_name: str, node: AgentNode) -> AgentNode:
    async def traced(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        try:
            return await node(state, runtime)
        except Exception as exc:
            _emit_agent_failure(runtime, agent_name, exc)
            raise

    return traced


INTENT_PROMPT = """你是 LingxiLearn 的意图识别与调度 Agent。

首次输入只提取一个具体、可教学的知识点，并输出 IntentContext JSON：
{"topic":"...","learning_objective":"...","learner_level":"undergraduate","course_context":"...","language":"zh-CN","target_duration_sec":75}

后续输入需要判断动作，只输出 JSON：
{"route":"answer_user|interactive_visual_explainer|quiz_submit|handoff","message":"..."}

路由规则：用户要求图解、动画、可视化时选择 interactive_visual_explainer；明确提交答案时选择
quiz_submit；表示不想答题、结束、退出或“先不做题”时选择 handoff；其他围绕知识点的追问选择 answer_user。
不要回答问题，不要 Markdown。"""

LECTURE_PROMPT = progressive_skill_prompt(
    "lesson-intro",
    "lesson-intro-html.v1",
    referenced_resources=(
        "references/tool-contracts.md",
        "references/html-design.md",
        "assets/example-page.html",
        "scripts/validate_output.py",
    ),
    artifact_instructions="""这是课程引入 HTML 生成 Agent。完成必要检索后，生成一个完整的
lesson-intro.html 并通过 stage_artifact_file 写入；HTML 必须是零依赖、简体中文、可直接打开的
学习者页面。最后只返回包含 topic/status/warnings 的简短 JSON 回执，不要复制 HTML。""",
)

DECK_PROMPT = progressive_skill_prompt(
    "interactive-lecture-deck",
    "interactive-lecture-deck-result.v2",
    referenced_resources=(
        "references/task-contract.md",
        "references/design-system.md",
        "references/visual-authoring.md",
        "references/slide-authoring.md",
        "references/lecture-data.md",
        "references/zoom-contract.md",
    ),
    artifact_instructions="""这是分阶段课件生成。默认 problem 生成 5–7 页，concept 生成 6–8 页，lesson
生成 8–12 页；必须有 opening/content/closing。每写完一份 slides/sNN.html、lecture.json 或
manifest.json 和 runtime/index.html，就调用 stage_artifact_file；runtime/index.html 必须从 skill asset 原样写入 staged artifact；不要把完整文件放进最终回答。dist/lecture.html 由服务端执行 standalone build。最终回执示例：
{"status":"staged","title":"...","files":["lecture.json","slides/s01.html"],"assumptions":[],"deviations":[]}。""",
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
    artifact_instructions="""这是实际的知识点测评生成 Agent。严格使用 quiz-generation-input.v2，默认生成
3–4 道基于已讲授材料的诊断题；通过 scripts/quiz_contract.py 的规则检查答案结构和总分。只返回
quiz-generation-result.v1 JSON，不返回 Markdown。答案、解析、keywords 和 assumptions 是内部字段。""",
    stage_artifacts=False,
)

ANSWER_PROMPT = """你是知识点答疑 Agent。只回答当前知识点的追问，使用简体中文，基于已有课程引入和课件上下文。
回答要简短、准确，不主动泄露尚未提交的题目答案；只输出 JSON {"text":"..."}。"""

VISUAL_PROMPT = progressive_skill_prompt(
    "interactive-visual-explainer",
    "interactive-visual-explainer-delivery.v1",
    referenced_resources=(
        "references/interaction-patterns.md",
        "references/anti-patterns.md",
        "assets/template.html",
        "assets/lingxi.css",
    ),
    artifact_instructions="""这是分阶段单文件 artifact 生成。先选择一个主交互模式，再从模板构建
visual-explainer.html，并通过 stage_artifact_file 写入该文件。服务端会执行 palette 和 static
check。最终只返回简短中文 delivery receipt，不要返回 HTML。""",
)


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


def _message_payload(message: Any) -> tuple[str, str]:
    """Return provider reasoning and visible content from a native message."""

    additional = getattr(message, "additional_kwargs", {}) or {}
    reasoning = ""
    if isinstance(additional, dict):
        for key in ("reasoning_content", "reasoning", "thinking"):
            if additional.get(key):
                reasoning = str(additional[key])
                break
    return reasoning, str(getattr(message, "content", "") or "")


async def _invoke_agent(
    agent: Any,
    message: HumanMessage,
    runtime: Runtime[Any],
    *,
    agent_name: str,
    recursion_limit: int,
    tool_permissions: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Run a child Agent while forwarding its native runtime events.

    Calling a compiled Agent with ``ainvoke`` inside an ordinary graph node does
    not make it a native subgraph, so its model/tool events never reach the
    parent's stream.  Streaming the child explicitly keeps progressive skill
    disclosure observable without a second UI event implementation.
    """

    stream = getattr(agent, "astream", None)
    if not callable(stream):
        return await agent.ainvoke(
            {"messages": [message]},
            {
                "recursion_limit": recursion_limit,
                "tool_permissions": list(tool_permissions),
            },
        )

    config = {
        "recursion_limit": recursion_limit,
        "tool_permissions": list(tool_permissions),
    }
    latest: dict[str, Any] = {}
    reasoning_parts: list[str] = []
    content_parts: list[str] = []
    tool_calls: dict[str, dict[str, Any]] = {}
    model_started = 0.0
    tool_batch_started = 0.0

    def flush_text() -> None:
        if reasoning_parts:
            _emit(
                runtime,
                "reasoning.delta",
                agent=agent_name,
                delta="".join(reasoning_parts),
            )
            reasoning_parts.clear()
        if content_parts:
            _emit(
                runtime,
                "assistant.delta",
                agent=agent_name,
                delta="".join(content_parts),
            )
            content_parts.clear()

    try:
        async for mode, value in stream(
            {"messages": [message]},
            config,
            stream_mode=("events", "values"),
            context=runtime.context,
            cancellation=runtime.cancellation,
            subgraphs=True,
        ):
            if mode == "values":
                if isinstance(value, dict):
                    latest = value
                continue
            event = value
            if event.kind is EventKind.MESSAGE:
                envelope = event.data.get("value")
                native_message = envelope[0] if isinstance(envelope, (tuple, list)) and envelope else None
                if native_message is not None:
                    reasoning, content = _message_payload(native_message)
                    if reasoning and not (getattr(native_message, "additional_kwargs", {}) or {}).get("_reasoning_replay"):
                        reasoning_parts.append(reasoning)
                    if content:
                        content_parts.append(content)
                    if sum(map(len, reasoning_parts)) + sum(map(len, content_parts)) >= 256:
                        flush_text()
                continue
            if event.kind is EventKind.NODE_STARTED and event.node == "agent":
                model_started = time.monotonic()
                _emit(runtime, "model.started", agent=agent_name)
                continue
            if event.kind is EventKind.NODE_STARTED and event.node == "tools":
                tool_batch_started = time.monotonic()
                continue
            if event.kind is not EventKind.NODE_COMPLETED:
                continue
            update = event.data.get("update") or {}
            messages = update.get("messages", ()) if isinstance(update, dict) else ()
            if event.node == "agent":
                flush_text()
                response = messages[-1] if messages else None
                if isinstance(response, AIMessage):
                    for call in response.tool_calls:
                        call_payload = {
                            "id": call.id,
                            "name": call.name,
                            "args": dict(call.args),
                        }
                        tool_calls[call.id] = call_payload
                        _emit(
                            runtime,
                            "tool.call.delta",
                            agent=agent_name,
                            calls=[call_payload],
                        )
                    usage = dict(response.usage or {})
                    if usage:
                        _emit(runtime, "model.usage", agent=agent_name, usage=usage)
                    _emit(
                        runtime,
                        "model.completed",
                        agent=agent_name,
                        duration_ms=round((time.monotonic() - model_started) * 1000, 2)
                        if model_started
                        else None,
                        response_metadata=getattr(response, "response_metadata", {}) or {},
                        additional_kwargs=getattr(response, "additional_kwargs", {}) or {},
                    )
                continue
            if event.node == "tools":
                duration_ms = (
                    round((time.monotonic() - tool_batch_started) * 1000, 2)
                    if tool_batch_started
                    else None
                )
                for result in messages:
                    if not isinstance(result, ToolMessage):
                        continue
                    call = tool_calls.get(result.tool_call_id, {})
                    _emit(
                        runtime,
                        "tool.result",
                        agent=agent_name,
                        tool_call_id=result.tool_call_id,
                        name=result.name,
                        arguments=call.get("args", {}),
                        content=result.content,
                        status=result.status,
                        duration_ms=duration_ms,
                        additional_kwargs=result.additional_kwargs,
                        response_metadata=result.response_metadata,
                    )
        flush_text()
        return latest
    except Exception:
        flush_text()
        raise


def _route_from_state(state: AgentState) -> str:
    route = state.get("route")
    if route not in {"initialize", "await_user", "answer_user", "interactive_visual_explainer", "quiz_submit", "handoff"}:
        raise ValueError(f"unknown graph route: {route!r}")
    return str(route)


def _public_quiz(state: AgentState) -> dict[str, Any]:
    return quiz_public(state.get("quiz_result") or {})


def build_agent_graph(*, model: Any, settings: Settings, task_id: str, artifacts: ArtifactStore, persist_result: PersistResult, checkpointer: Any | None = None, store: Any | None = None):
    """Compile the durable difficult-knowledge subgraph."""
    lecture_registry = SkillRegistry((FilesystemSkillSource(REPO_ROOT / "skills" / "lesson-intro"),))
    deck_registry = SkillRegistry((FilesystemSkillSource(REPO_ROOT / "skills" / "interactive-lecture-deck"),))
    visual_registry = SkillRegistry((FilesystemSkillSource(REPO_ROOT / "skills" / "interactive-visual-explainer"),))
    quiz_registry = SkillRegistry((FilesystemSkillSource(REPO_ROOT / "skills" / "quiz-generator"),))

    async def recognize_intent(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        initial = not bool(state.get("intent"))
        raw = state.get("prompt", "") if initial else str((state.get("user_message") or {}).get("message") or "")
        _emit(runtime, "intent.started", agent="intent")
        agent = create_agent(_agent_model(model, "intent"), system_prompt=INTENT_PROMPT, name="intent-recognizer")
        result = await _invoke_agent(
            agent,
            HumanMessage(raw),
            runtime,
            agent_name="intent",
            recursion_limit=8,
        )
        parsed = extract_json(_message_text(result)) or {}
        if initial:
            try:
                intent = IntentContext.model_validate(parsed)
            except Exception as exc:
                raise ValueError("intent recognizer returned an invalid IntentContext") from exc
            value = intent.model_dump(mode="json")
            await persist_result("intent", value)
            _emit(runtime, "intent.completed", agent="intent", topic=intent.topic)
            return {"intent": value, "route": "initialize"}
        if (state.get("user_message") or {}).get("kind") == "quiz_submit":
            _emit(runtime, "intent.routed", agent="intent", route="quiz_submit")
            return {"route": "quiz_submit"}
        route = str(parsed.get("route") or "")
        if route not in {"answer_user", "interactive_visual_explainer", "quiz_submit", "handoff"}:
            raise ValueError(f"intent recognizer returned an invalid route: {route!r}")
        _emit(runtime, "intent.routed", agent="intent", route=route)
        return {"route": route}

    async def lecture_hook(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        if state.get("route") != "initialize":
            return {}
        _emit(runtime, "agent.started", agent="lecture_hook", skill="lesson-intro")
        intent = IntentContext.model_validate(state["intent"])
        draft = ArtifactDraft(artifacts, task_id, "lesson-intro")
        prompt = (
            "按 lesson-intro-html.v1 生成课程引入页面。先读取 skill 和直接相关资源，完成必要研究，"
            "再通过 stage_artifact_file 写入 lesson-intro.html，回读检查后只返回 JSON 回执。\nTASK JSON:\n"
            + json.dumps({"task_id": state["task_id"], **intent.model_dump(mode="json")}, ensure_ascii=False)
        )
        agent = create_agent(
            _agent_model(model, "lecture_hook"),
            tools=build_web_tools(settings) + staged_artifact_tools(draft),
            skills=lecture_registry,
            system_prompt=LECTURE_PROMPT,
            pinned_constraints=skill_constraints(
                "lesson-intro",
                (
                    "references/tool-contracts.md",
                    "references/html-design.md",
                    "assets/example-page.html",
                    "scripts/validate_output.py",
                ),
            ),
            name="lesson-intro",
        )
        try:
            response_text = _message_text(
                await _invoke_agent(
                    agent,
                    HumanMessage(prompt),
                    runtime,
                    agent_name="lecture_hook",
                    recursion_limit=30,
                    tool_permissions=("artifact:write",),
                )
            )
            parsed = extract_json(response_text) or {}
            html = draft.snapshot().get("lesson-intro.html")
            if not html:
                raise ValueError("lesson-intro did not stage lesson-intro.html")
            artifacts.write_lesson_intro_file(state["task_id"], html)
            validation = await artifacts.validate_lesson_intro(state["task_id"])
            if not validation["ok"]:
                raise ValueError(f"lesson-intro HTML validation failed: {validation}")
            value = {
                "html": html,
                "topic": str(parsed.get("topic") or intent.topic),
                "status": str(parsed.get("status") or "ok"),
                "warnings": list(parsed.get("warnings") or []),
                "structured_data": parsed.get("structured_data") or {},
                "validation": validation,
            }
        finally:
            draft.cleanup()
        await persist_result("lecture_hook", value)
        intro_artifact = {"relative_path": f"{state['task_id']}/lesson-intro.html"}
        _emit(runtime, "agent.output", agent="lecture_hook", message="课程引入 HTML 已生成")
        _emit(runtime, "artifact.ready", agent="lecture_hook", artifact="lesson-intro", path=intro_artifact["relative_path"])
        _emit(runtime, "agent.completed", agent="lecture_hook", skill="lesson-intro")
        return {"lecture_result": value}

    async def interactive_lecture_deck(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        if state.get("route") != "initialize":
            return {}
        _emit(runtime, "agent.started", agent="interactive_lecture_deck", skill="interactive-lecture-deck")
        intent = IntentContext.model_validate(state["intent"])
        draft = ArtifactDraft(artifacts, task_id, "deck")
        prompt = (
            "按分阶段协议完成 interactive-lecture-deck-result.v2。\n"
            "阶段 1：读取 skill 入口和直接相关 references。\n"
            "阶段 2：形成内部视觉大纲，决定页数、页角色、视觉关系和 zoom anchors。\n"
            "阶段 3：逐文件调用 stage_artifact_file 生成课件源文件，并回读检查。\n"
            "阶段 4：返回 JSON receipt，不要回传完整文件。\n"
            "INTENT JSON:\n"
            + json.dumps(intent.model_dump(mode="json"), ensure_ascii=False)
        )
        agent = create_agent(
            _agent_model(model, "interactive_lecture_deck"),
            tools=staged_artifact_tools(draft),
            skills=deck_registry,
            system_prompt=DECK_PROMPT,
            pinned_constraints=skill_constraints(
                "interactive-lecture-deck",
                (
                    "references/task-contract.md",
                    "references/design-system.md",
                    "references/visual-authoring.md",
                    "references/slide-authoring.md",
                    "references/lecture-data.md",
                    "references/zoom-contract.md",
                ),
            ),
            name="interactive-lecture-deck",
        )
        try:
            parsed = extract_json(
                _message_text(
                    await _invoke_agent(
                        agent,
                        HumanMessage(prompt),
                        runtime,
                        agent_name="interactive_lecture_deck",
                        recursion_limit=40,
                        tool_permissions=("artifact:write",),
                    )
                )
            ) or {}
            files = draft.snapshot()
            if not files:
                raise ValueError("interactive-lecture-deck did not stage any artifact")
        finally:
            draft.cleanup()
        artifacts.write_deck(task_id, files)
        validation = await artifacts.build_and_validate_deck(task_id)
        if not validation["ok"]:
            raise ValueError(f"interactive-lecture-deck validation failed: {validation}")
        value = DeckResult.model_validate({"schema_version": "interactive-lecture-deck-result.v2", "task_id": task_id, "title": str(parsed.get("title") or intent.topic), "status": "ready" if validation["ok"] else "failed", "files": {"lecture": "lecture.json", "slides": sorted(name for name in files if name.startswith("slides/")), "runtime": "runtime/index.html", "standalone": "dist/lecture.html", "manifest": "manifest.json"}, "manifest": parsed.get("manifest") or {}, "validation": validation, "assumptions": parsed.get("assumptions") or [], "deviations": parsed.get("deviations") or []}).model_dump(mode="json")
        await persist_result("interactive_lecture_deck", value)
        _emit(runtime, "artifact.ready", agent="interactive_lecture_deck", artifact="lecture-deck", validation=validation)
        _emit(runtime, "agent.completed", agent="interactive_lecture_deck", skill="interactive-lecture-deck")
        return {"deck_result": value}

    async def quiz_generator(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        if state.get("route") != "initialize":
            return {}
        _emit(runtime, "agent.started", agent="quiz_generator")
        prompt = "生成 quiz-generation-result.v1。\n" + json.dumps(
            {
                "schema_version": "quiz-generation-input.v2",
                "task_id": task_id,
                "intent": state["intent"],
                "lesson_intro": (state.get("lecture_result") or {}).get("html") or "",
                "interactive_lecture_deck": state.get("deck_result", {}),
            },
            ensure_ascii=False,
        )
        agent = create_agent(
            _agent_model(model, "quiz_generator"),
            skills=quiz_registry,
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
        parsed = extract_json(
            _message_text(
                await _invoke_agent(
                    agent,
                    HumanMessage(prompt),
                    runtime,
                    agent_name="quiz_generator",
                    recursion_limit=20,
                )
            )
        )
        if not parsed:
            raise ValueError("quiz-generator returned no JSON result")
        quiz = QuizGenerationResult.model_validate(parsed)
        value = quiz.model_dump(mode="json")
        validation = await artifacts.validate_quiz_result(task_id, value)
        if not validation["ok"]:
            raise ValueError(f"quiz-generator contract validation failed: {validation['output']}")
        await persist_result("quiz_generator", value)
        _emit(runtime, "quiz.ready", agent="quiz_generator", question_count=len(quiz.questions), validation=validation)
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
        parsed = extract_json(
            _message_text(
                await _invoke_agent(
                    agent,
                    HumanMessage(json.dumps(context, ensure_ascii=False)),
                    runtime,
                    agent_name="answer_user",
                    recursion_limit=8,
                )
            )
        )
        text = str((parsed or {}).get("text") or "").strip()
        if not text:
            raise ValueError("answer-user returned no answer text")
        value = {"text": text, "created_at": datetime.now(UTC).isoformat()}
        _emit(runtime, "agent.output", agent="answer_user", message=text)
        return {"answer_result": value, "status": "awaiting_user"}

    async def visual_explainer(state: AgentState, runtime: Runtime[Any]) -> dict[str, Any]:
        _emit(runtime, "agent.started", agent="interactive_visual_explainer", skill="interactive-visual-explainer")
        draft = ArtifactDraft(artifacts, task_id, "visual")
        prompt = (
            "按分阶段协议完成 interactive-visual-explainer-delivery.v1。\n"
            "先读取 skill 和直接相关参考资料，选择一个主交互模式；然后通过 stage_artifact_file 写入"
            " visual-explainer.html，最后只返回 delivery receipt。\nINTENT JSON:\n"
            + json.dumps(state.get("intent", {}), ensure_ascii=False)
            + "\nLESSON CONTEXT:\n"
            + json.dumps(
                {
                    "lesson_intro": state.get("lecture_result", {}),
                    "lecture_deck": state.get("deck_result", {}),
                },
                ensure_ascii=False,
            )
        )
        agent = create_agent(
            _agent_model(model, "interactive_visual_explainer"),
            tools=staged_artifact_tools(draft),
            skills=visual_registry,
            system_prompt=VISUAL_PROMPT,
            pinned_constraints=skill_constraints(
                "interactive-visual-explainer",
                (
                    "references/interaction-patterns.md",
                    "references/anti-patterns.md",
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
            staged = draft.snapshot()
            html = staged.get("visual-explainer.html")
        finally:
            draft.cleanup()
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

    builder = StateGraph(AgentState, name="lingxilearn-difficult-knowledge-subgraph", version="2.0.0")
    builder.add_node("recognize_intent", _trace_agent_node("intent", recognize_intent), timeout=settings.agent_timeout)
    builder.add_node("lecture_hook", _trace_agent_node("lecture_hook", lecture_hook), timeout=settings.agent_lecture_timeout)
    builder.add_node("interactive_lecture_deck", _trace_agent_node("interactive_lecture_deck", interactive_lecture_deck), timeout=settings.agent_visual_timeout)
    builder.add_node("quiz_generator", _trace_agent_node("quiz_generator", quiz_generator), timeout=settings.agent_timeout)
    builder.add_node("await_user", await_user)
    builder.add_node("answer_user", _trace_agent_node("answer_user", answer_user), timeout=settings.agent_timeout)
    builder.add_node("interactive_visual_explainer", _trace_agent_node("interactive_visual_explainer", visual_explainer), timeout=settings.agent_visual_timeout)
    builder.add_node("quiz_submit", quiz_submit)
    builder.add_node("handoff", handoff)
    builder.add_edge(START, "recognize_intent")
    builder.add_edge("recognize_intent", "lecture_hook")
    builder.add_edge("recognize_intent", "interactive_lecture_deck")
    builder.add_edge(("lecture_hook", "interactive_lecture_deck"), "quiz_generator", trigger="all")
    builder.add_conditional_edges("quiz_generator", _route_from_state, {"initialize": "await_user", "await_user": "await_user", "answer_user": "answer_user", "interactive_visual_explainer": "interactive_visual_explainer", "quiz_submit": "quiz_submit", "handoff": "handoff"})
    builder.add_edge("await_user", "recognize_intent" if checkpointer is not None else END)
    builder.add_edge("answer_user", "await_user")
    builder.add_edge("interactive_visual_explainer", "await_user")
    builder.add_edge("quiz_submit", "handoff")
    builder.add_edge("handoff", END)
    compile_options: dict[str, Any] = {"checkpointer": checkpointer}
    if store is not None:
        compile_options["store"] = store
    return builder.compile(**compile_options)
