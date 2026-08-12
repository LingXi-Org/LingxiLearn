from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from lingxigraph import AIMessage, AIMessageChunk, FilesystemSkillSource, HumanMessage, ToolCallChunk, ToolMessage, create_agent, tool

from lingxilearn.agents.artifact_store import ArtifactError, ArtifactStore
from lingxilearn.agents.contracts import IntentContext, LectureHookResult, extract_json
from lingxilearn.agents.graph import _invoke_agent, build_agent_graph
from lingxilearn.service import Service, _message_trace_events
from lingxilearn.agents.web_tools import _assert_public_url
from lingxilearn.agents.skill_runtime import ArtifactDraft, progressive_skill_prompt, staged_artifact_tools
from lingxilearn.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_child_agent_stream_forwards_native_model_and_tool_events() -> None:
    emitted: list[dict[str, Any]] = []

    @tool(name="stage_probe", permissions=("artifact:write",))
    def stage_probe(value: str) -> str:
        return f"staged:{value}"

    class FakeModel:
        def __init__(self) -> None:
            self.calls = 0

        async def astream(self, _messages: Any, *, tools: Any = None, **_kwargs: Any):
            self.calls += 1
            if self.calls == 1:
                yield AIMessageChunk(
                    "",
                    additional_kwargs={"reasoning_content": "先调用写入工具"},
                    tool_call_chunks=(
                        ToolCallChunk(
                            name="stage_probe",
                            args='{"value":"lesson-intro.html"}',
                            id="call-1",
                            index=0,
                        ),
                    ),
                )
            else:
                yield AIMessageChunk("完成")

    class FakeRuntime:
        context: dict[str, Any] = {}
        cancellation = None

        def emit(self, channel: str, value: dict[str, Any]) -> None:
            assert channel == "agent_task"
            emitted.append(value)

    agent = create_agent(FakeModel(), tools=[stage_probe], name="trace-probe")
    result = await _invoke_agent(
        agent,
        HumanMessage("生成文件"),
        FakeRuntime(),  # type: ignore[arg-type]
        agent_name="lecture_hook",
        recursion_limit=8,
        tool_permissions=("artifact:write",),
    )

    assert result["messages"][-1].content == "完成"
    kinds = [event["type"] for event in emitted]
    assert "model.started" in kinds
    assert "reasoning.delta" in kinds
    assert "tool.call.delta" in kinds
    assert "tool.result" in kinds
    assert "model.completed" in kinds
    tool_result = next(event for event in emitted if event["type"] == "tool.result")
    assert tool_result["status"] == "success"
    assert tool_result["arguments"] == {"value": "lesson-intro.html"}


def test_agent_trace_preserves_reasoning_tool_calls_and_results() -> None:
    chunk = AIMessageChunk(
        "",
        additional_kwargs={"reasoning_content": "先阅读 skill，再生成产物"},
        tool_call_chunks=(ToolCallChunk(name="read_skill", args='{"skill_name":"lesson-intro"}', id="call-1", index=0),),
    )
    reasoning_and_tool = _message_trace_events((chunk, {"agent": "lecture_hook"}), "coordinator")
    assert {event["kind"] for event in reasoning_and_tool} == {"reasoning.delta", "tool.call.delta"}

    result = _message_trace_events(
        (ToolMessage(content="SKILL.md 内容", tool_call_id="call-1", name="read_skill"), {"agent": "lecture_hook"}),
        "coordinator",
    )
    assert result[0]["kind"] == "tool.result"
    assert result[0]["agent"] == "lecture_hook"
    assert result[0]["payload"]["tool_call_id"] == "call-1"
    assert result[0]["payload"]["name"] == "read_skill"
    assert result[0]["payload"]["content"] == "SKILL.md 内容"


def test_agent_skills_are_discoverable_and_have_resources() -> None:
    for name in ("lesson-intro", "interactive-lecture-deck", "interactive-visual-explainer"):
        skill_dir = REPO_ROOT / "skills" / name
        source = FilesystemSkillSource(skill_dir)
        metadata = source.discover()
        assert [item.name for item in metadata] == [name]
        assert (skill_dir / "SKILL.md").read_text(encoding="utf-8").startswith("---")


def test_skill_runtime_supports_progressive_disclosure_and_staged_artifacts(tmp_path: Path) -> None:
    settings = Settings(_env_file="", agent_task_dir=tmp_path)
    draft = ArtifactDraft(ArtifactStore(settings), "staged-task", "deck")
    tools = staged_artifact_tools(draft)
    result = tools[0].func("slides/s01.html", "<!doctype html><html></html>")
    assert "staged" in result
    assert draft.list() == [{"path": "slides/s01.html", "bytes": 28}]
    assert tools[1].func("slides/s01.html") == "<!doctype html><html></html>"
    assert "slides/s01.html" in tools[2].func()
    with pytest.raises(ArtifactError):
        tools[0].func("../escape.html", "bad")
    prompt = progressive_skill_prompt(
        "interactive-lecture-deck",
        "interactive-lecture-deck-result.v2",
        referenced_resources=("references/design-system.md",),
    )
    assert "read_skill" in prompt
    assert "read_skill_resource" in prompt
    assert "stage_artifact_file" in prompt
    draft.cleanup()
    assert not draft.root.exists()


def test_intent_and_lecture_contracts_reject_malformed_output() -> None:
    parsed = extract_json('```json\n{"topic":"TCP 拥塞控制"}\n```')
    assert parsed == {"topic": "TCP 拥塞控制"}
    intent = IntentContext.model_validate(parsed)
    assert intent.learner_level == "undergraduate"
    assert intent.target_duration_sec == 75

    with pytest.raises(ValueError):
        LectureHookResult.model_validate({"schema_version": "wrong"})


def test_agent_graph_fans_out_specialists_before_merge(tmp_path: Path) -> None:
    settings = Settings(_env_file="", agent_task_dir=tmp_path)
    graph = build_agent_graph(
        model=object(),
        settings=settings,
        task_id="topology-test",
        artifacts=ArtifactStore(settings),
        persist_result=lambda _agent, _value: None,
    )
    edges = {(edge.source, edge.target, edge.label) for edge in graph.get_graph().edges}
    assert ("recognize_intent", "lecture_hook", None) in edges
    assert ("recognize_intent", "interactive_lecture_deck", None) in edges
    assert ("lecture_hook", "quiz_generator", "all") in edges
    assert ("interactive_lecture_deck", "quiz_generator", "all") in edges


@pytest.mark.asyncio
async def test_specialists_start_in_parallel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    timeline: list[str] = []
    created: dict[str, dict[str, Any]] = {}
    lecture = {
        "schema_version": "lesson-intro-result.v1",
        "status": "ok",
        "topic": "TCP 拥塞控制",
        "selected_hook": {
            "title": "网络为什么会堵车",
            "hook_type": "analogy",
            "opening": "开场",
            "story": "故事",
            "question": "问题",
            "transition": "过渡",
            "estimated_duration_sec": 60,
            "why_this_hook_works": "便于建立直觉",
        },
        "candidates": [
            {
                "title": "网络为什么会堵车",
                "hook_type": "analogy",
                "score": 80,
                "lesson_alignment": 80,
                "curiosity": 80,
                "evidence_strength": 80,
            }
        ],
        "research": {"search_angles": [], "claims": [], "sources": []},
    }

    class FakeAgent:
        def __init__(self, name: str, tools: list[Any]) -> None:
            self.name = name
            self.tools = tools

        async def ainvoke(self, _input: Any, _config: Any) -> dict[str, Any]:
            created[self.name]["config"] = _config
            timeline.append(f"{self.name}:start")
            await asyncio.sleep(0.03)
            timeline.append(f"{self.name}:end")
            if self.name == "intent-recognizer":
                content = '{"topic":"TCP 拥塞控制"}'
            elif self.name in {"lecture-hook", "lesson-intro"}:
                content = '{"topic":"TCP 拥塞控制","status":"ok"}'
                stage = next(tool for tool in self.tools if tool.name == "stage_artifact_file")
                stage.func(
                    "lesson-intro.html",
                    "<!doctype html><html lang='zh-CN'><head><title>TCP</title></head><body><h1>TCP 拥塞控制</h1><p>理解一个可观察的问题。</p></body></html>",
                )
            elif self.name == "quiz-generator":
                content = '{"schema_version":"quiz-generation-result.v1","task_id":"parallel-test","title":"TCP","instructions":"完成测评。","questions":[{"id":"q01","type":"single_choice","prompt":"核心关系是什么？","options":[{"id":"A","label":"关系"},{"id":"B","label":"结论"}],"points":1,"answer":{"option_ids":["A"],"grading_mode":"exact"},"explanation":"关系。","keywords":["concept:TCP"]}],"total_points":1}'
            elif self.name == "interactive-lecture-deck":
                source = REPO_ROOT / "skills" / "interactive-lecture-deck" / "assets" / "examples" / "quadratic-vertex"
                stage = next(tool for tool in self.tools if tool.name == "stage_artifact_file")
                stage.func("lecture.json", (source / "lecture.json").read_text(encoding="utf-8"))
                stage.func("manifest.json", (source / "manifest.json").read_text(encoding="utf-8"))
                stage.func("runtime/index.html", (REPO_ROOT / "skills" / "interactive-lecture-deck" / "assets" / "runtime" / "index.html").read_text(encoding="utf-8"))
                for slide in (source / "slides").glob("s*.html"):
                    stage.func(f"slides/{slide.name}", slide.read_text(encoding="utf-8"))
                content = '{"title":"TCP 拥塞控制"}'
            else:
                content = (
                    "<!doctype html><html lang='zh-CN'><head><title>TCP</title></head>"
                    "<body><button>观察</button></body></html>"
                )
            return {"messages": [AIMessage(content=content)]}

    def fake_create_agent(_model: Any, *_tools: Any, name: str, **kwargs: Any) -> FakeAgent:
        created[name] = kwargs
        return FakeAgent(name, kwargs.get("tools", []))

    monkeypatch.setattr("lingxilearn.agents.graph.create_agent", fake_create_agent)
    settings = Settings(_env_file="", agent_task_dir=tmp_path)
    store = ArtifactStore(settings)

    async def fake_validate(_task_id: str) -> dict[str, Any]:
        return {"ok": True, "static": {"ok": True}, "palette": {}, "screenshot": "fixture"}

    monkeypatch.setattr(store, "validate_html", fake_validate)
    async def fake_validate_intro(_task_id: str) -> dict[str, Any]:
        return {"ok": True, "contract": "lesson-intro-html.v1"}
    monkeypatch.setattr(store, "validate_lesson_intro", fake_validate_intro)

    async def persist(_agent: str, _value: dict[str, Any]) -> None:
        return None

    graph = build_agent_graph(
        model=object(),
        settings=settings,
        task_id="parallel-test",
        artifacts=store,
        persist_result=persist,
    )
    result = await graph.ainvoke(
        {"task_id": "parallel-test", "prompt": "解释 TCP 拥塞控制", "errors": []}
    )
    assert result["status"] == "awaiting_user"
    first_end = min(
        index
        for index, item in enumerate(timeline)
        if item in {"lesson-intro:end", "interactive-lecture-deck:end"}
    )
    assert timeline.index("lesson-intro:start") < first_end
    assert timeline.index("interactive-lecture-deck:start") < first_end
    assert created["lesson-intro"]["skills"].discover()[0].name == "lesson-intro"
    assert {item.name for item in created["lesson-intro"]["tools"]} == {"web_search", "web_fetch", "stage_artifact_file", "read_staged_artifact", "list_staged_artifacts"}
    assert created["lesson-intro"]["config"]["tool_permissions"] == ["artifact:write"]
    deck_tools = {item.name for item in created["interactive-lecture-deck"]["tools"]}
    assert {"stage_artifact_file", "read_staged_artifact", "list_staged_artifacts"} <= deck_tools
    assert created["interactive-lecture-deck"]["skills"].discover()[0].name == "interactive-lecture-deck"
    assert created["interactive-lecture-deck"]["config"]["tool_permissions"] == ["artifact:write"]


@pytest.mark.asyncio
async def test_missing_deepseek_key_is_a_durable_failed_task(tmp_path: Path) -> None:
    suffix = uuid4().hex
    settings = Settings(
        _env_file="",
        database_url=f"sqlite+aiosqlite:///./var/agent-key-check-{suffix}.sqlite3",
        agent_task_dir=tmp_path,
    )
    service = Service(settings)
    await service.db.create_all()
    try:
        task_id = f"missing-key-{suffix}"
        created = await service.create_agent_task(
            task_id=task_id, learner_id="guest-test", prompt="解释 TCP"
        )
        assert created["status"] == "failed"
        snapshot = await service.agent_task_snapshot(task_id)
        assert snapshot["status"] == "failed"
        events = await service.repo.agent_events_after(task_id)
        assert [event["kind"] for event in events] == ["task.started", "task.failed"]
        assert "DS_API_KEY" in snapshot["error"]
    finally:
        await service.db.dispose()


def test_visual_artifact_is_task_scoped_and_single_file_only(tmp_path: Path) -> None:
    settings = Settings(_env_file="", agent_task_dir=tmp_path)
    store = ArtifactStore(settings)
    html = (
        "<!doctype html><html lang='zh-CN'><head><title>Demo</title></head>"
        "<body><button>开始</button></body></html>"
    )
    result = store.write_html("task-1", html)
    assert result["relative_path"] == "task-1/visual-explainer.html"
    assert store.read_html("task-1").decode() == html

    template = (REPO_ROOT / "skills" / "interactive-visual-explainer" / "assets" / "template.html").read_text(
        encoding="utf-8"
    )
    store.write_html("template-check", template)
    validation = asyncio.run(store.validate_html("template-check"))
    assert validation["ok"] is True
    assert validation["palette"]["light"]["ok"] is True
    assert validation["palette"]["dark"]["ok"] is True

    with pytest.raises(ArtifactError):
        store.write_html("../escape", html)
    with pytest.raises(ArtifactError):
        store.write_html("task-1", "")


def test_lesson_intro_artifact_and_skill_deck_are_publishable(tmp_path: Path) -> None:
    settings = Settings(_env_file="", agent_task_dir=tmp_path)
    store = ArtifactStore(settings)
    html = (REPO_ROOT / "skills" / "lesson-intro" / "assets" / "example-page.html").read_text(encoding="utf-8")
    intro = store.write_lesson_intro_file("intro-task", html)
    assert intro["artifact_id"] == "lesson-intro"
    assert "为什么雨后的石板路格外滑" in store.lesson_intro_path("intro-task").read_text(encoding="utf-8")

    source = REPO_ROOT / "skills" / "interactive-lecture-deck" / "assets" / "examples" / "quadratic-vertex"
    files = {
        "lecture.json": (source / "lecture.json").read_text(encoding="utf-8"),
        "manifest.json": (source / "manifest.json").read_text(encoding="utf-8"),
        "runtime/index.html": (REPO_ROOT / "skills" / "interactive-lecture-deck" / "assets" / "runtime" / "index.html").read_text(encoding="utf-8"),
    }
    for slide in (source / "slides").glob("s*.html"):
        files[f"slides/{slide.name}"] = slide.read_text(encoding="utf-8")
    store.write_deck("deck-task", files)
    validation = asyncio.run(store.build_and_validate_deck("deck-task"))
    assert validation["ok"] is True
    assert validation["validation"]["output"].find('"slideCount"') >= 0

    with pytest.raises(ArtifactError, match="runtime/index.html"):
        store.write_deck("missing-runtime", {"lecture.json": "{}", "manifest.json": "{}"})


def test_web_fetch_rejects_private_addresses() -> None:
    with pytest.raises(ValueError, match="private"):
        asyncio.run(_assert_public_url("http://127.0.0.1/latest"))
