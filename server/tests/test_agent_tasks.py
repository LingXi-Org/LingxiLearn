from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from lingxigraph import (
    AIMessage,
    AIMessageChunk,
    FilesystemSkillSource,
    GraphRecursionError,
    HumanMessage,
    ToolCallChunk,
    ToolMessage,
    create_agent,
    tool,
)

from lingxilearn.agents.artifact_store import ArtifactError, ArtifactStore
from lingxilearn.agents.contracts import IntentContext, LectureHookResult, extract_json
from lingxilearn.agents.model_runtime import invoke_agent as _invoke_agent
from lingxilearn.agents.providers.content import _lesson_intro_fallback
from lingxilearn.agents.skill_runtime import (
    ArtifactDraft,
    progressive_skill_prompt,
    staged_artifact_tools,
)
from lingxilearn.agents.web_tools import _assert_public_url
from lingxilearn.config import Settings
from lingxilearn.service import Service, _agent_task_status, _message_trace_events

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_agent_task_status_uses_the_runtime_loop_field() -> None:
    completed = _agent_task_status({"runtime_status": "COMPLETED"}, interrupted=False)
    assert completed == "completed"
    assert _agent_task_status({"runtime_status": "FAILED"}, interrupted=False) == "failed"
    assert (
        _agent_task_status({"runtime_status": "WAITING_FOR_USER"}, interrupted=False)
        == "awaiting_user"
    )
    assert _agent_task_status({}, interrupted=True) == "awaiting_user"
    assert _agent_task_status({}, interrupted=False) == "partial"


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
        if name == "interactive-lecture-deck":
            spec = source.load(name)
            assert spec.extra_metadata.get("version") == "1.4.0"
            assert "dist/lecture.html" in spec.content


def test_skill_runtime_supports_progressive_disclosure_and_staged_artifacts(tmp_path: Path) -> None:
    settings = Settings(_env_file="", agent_task_dir=tmp_path)
    draft = ArtifactDraft(ArtifactStore(settings), "staged-task", "deck")
    tools = {item.name: item for item in staged_artifact_tools(draft, batch=True)}
    result = tools["stage_artifact_file"].func("slides/s01.html", "<!doctype html><html></html>")
    assert "staged" in result
    assert draft.list() == [{"path": "slides/s01.html", "bytes": 28}]
    tools["stage_artifact_chunk"].func("slides/s01.html", "<body>", "replace")
    tools["stage_artifact_chunk"].func("slides/s01.html", "chunk</body>", "append")
    assert draft.read("slides/s01.html") == "<body>chunk</body>"
    assert tools["read_staged_artifact"].func("slides/s01.html") == "<body>chunk</body>"
    assert "slides/s01.html" in tools["list_staged_artifacts"].func()
    batch = tools["stage_artifact_files"].func(
        [
            {"path": "slides/s02.html", "content": "<!doctype html><html><body>2</body></html>"},
            {"path": "slides/s03.html", "content": "<!doctype html><html><body>3</body></html>"},
        ]
    )
    assert '"status": "staged"' in batch
    assert {item["path"] for item in draft.list()} == {
        "slides/s01.html",
        "slides/s02.html",
        "slides/s03.html",
    }
    with pytest.raises(ArtifactError):
        tools["stage_artifact_files"].func(
            [{"path": "slides/s04.html", "content": "<!doctype html><html></html>"}]
        )
    with pytest.raises(ArtifactError):
        tools["stage_artifact_file"].func("../escape.html", "bad")
    prompt = progressive_skill_prompt(
        "interactive-lecture-deck",
        "interactive-lecture-deck-result.v2.1",
        referenced_resources=("references/design-system.md",),
    )
    assert "read_skill" in prompt
    assert "read_skill_resource" in prompt
    assert "stage_artifact_file" in prompt
    batch_prompt = progressive_skill_prompt(
        "interactive-lecture-deck",
        "interactive-lecture-deck-result.v2.1",
        referenced_resources=("references/slide-types.md",),
        batch_artifacts=True,
    )
    assert "stage_artifact_files" in batch_prompt
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
    assert "摩擦力" in store.lesson_intro_path("intro-task").read_text(encoding="utf-8")

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
    assert store.deck_path("deck-task").name == "lecture.html"
    assert store.deck_path("deck-task").parent.name == "dist"

    with pytest.raises(ArtifactError, match="runtime/index.html"):
        store.write_deck("missing-runtime", {"lecture.json": "{}", "manifest.json": "{}"})


@pytest.mark.asyncio
async def test_lesson_intro_timeout_draft_is_recoverable(tmp_path: Path) -> None:
    settings = Settings(_env_file="", agent_task_dir=tmp_path)
    store = ArtifactStore(settings)
    intent = IntentContext(topic="TCP 协议", learning_objective="理解可靠传输")
    draft = ArtifactDraft(store, "timeout-task", "lesson-intro")
    draft.write(
        "lesson-intro.html",
        _lesson_intro_fallback(intent.topic, intent.learning_objective),
    )
    recovered = await store.recover_lesson_intro_draft("timeout-task")
    assert recovered is not None
    assert recovered["recovered"] is True
    assert store.lesson_intro_path("timeout-task").exists()
    assert not store.lesson_intro_draft_path("timeout-task").exists()
    draft.cleanup()


def test_deck_repairs_array_anchor_rect_before_strict_validation(tmp_path: Path) -> None:
    settings = Settings(_env_file="", agent_task_dir=tmp_path)
    store = ArtifactStore(settings)
    source = REPO_ROOT / "skills" / "interactive-lecture-deck" / "assets" / "examples" / "quadratic-vertex"
    lecture = json.loads((source / "lecture.json").read_text(encoding="utf-8"))
    first_anchor = next(slide["anchors"][0] for slide in lecture["slides"] if slide["anchors"])
    rect = first_anchor["rect"]
    first_anchor["rect"] = [rect["x"], rect["y"], rect["w"], rect["h"]]
    files = {
        "lecture.json": json.dumps(lecture, ensure_ascii=False),
        "manifest.json": (source / "manifest.json").read_text(encoding="utf-8"),
        "runtime/index.html": (REPO_ROOT / "skills" / "interactive-lecture-deck" / "assets" / "runtime" / "index.html").read_text(encoding="utf-8"),
    }
    for slide in (source / "slides").glob("s*.html"):
        files[f"slides/{slide.name}"] = slide.read_text(encoding="utf-8")

    store.write_deck("array-rect-task", files)
    stored = json.loads(store.deck_root("array-rect-task").joinpath("lecture.json").read_text(encoding="utf-8"))
    assert stored["slides"][1]["anchors"][0]["rect"] == rect
    validation = asyncio.run(store.build_and_validate_deck("array-rect-task"))
    assert validation["ok"] is True


def test_deck_repairs_v2_required_fields_and_svg_text_classes(tmp_path: Path) -> None:
    settings = Settings(_env_file="", agent_task_dir=tmp_path)
    store = ArtifactStore(settings)
    source = REPO_ROOT / "skills" / "interactive-lecture-deck" / "assets" / "examples" / "quadratic-vertex"
    lecture = json.loads((source / "lecture.json").read_text(encoding="utf-8"))
    content_slide = next(slide for slide in lecture["slides"] if slide["role"] == "content")
    for anchor in content_slide["anchors"]:
        anchor.pop("label", None)
    for step in content_slide["steps"]:
        step.pop("advance", None)
        if step["kind"] == "overview":
            step["camera"] = {
                "mode": "anchor",
                "anchorId": content_slide["anchors"][0]["id"],
                "depth": 2,
                "focus": {"cx": 0.5, "cy": 0.5},
            }

    files = {
        "lecture.json": json.dumps(lecture, ensure_ascii=False),
        "manifest.json": (source / "manifest.json").read_text(encoding="utf-8"),
        "runtime/index.html": (REPO_ROOT / "skills" / "interactive-lecture-deck" / "assets" / "runtime" / "index.html").read_text(encoding="utf-8"),
    }
    for slide in (source / "slides").glob("s*.html"):
        html = slide.read_text(encoding="utf-8")
        if slide.name == "s02.html":
            html = re.sub(r' class="(?:th|ts|tn|t)"', "", html, count=1)
        files[f"slides/{slide.name}"] = html

    store.write_deck("v2-repair-task", files)
    stored = json.loads(store.deck_root("v2-repair-task").joinpath("lecture.json").read_text(encoding="utf-8"))
    repaired_slide = next(slide for slide in stored["slides"] if slide["role"] == "content")
    assert all(anchor["label"] for anchor in repaired_slide["anchors"])
    assert all(step["advance"] == "manual" for step in repaired_slide["steps"])
    assert repaired_slide["steps"][0]["camera"] == {"mode": "fit"}
    validation = asyncio.run(store.build_and_validate_deck("v2-repair-task"))
    assert validation["ok"] is True


def test_deck_migrates_legacy_envelope_before_validation(tmp_path: Path) -> None:
    settings = Settings(_env_file="", agent_task_dir=tmp_path)
    store = ArtifactStore(settings)
    source = REPO_ROOT / "skills" / "interactive-lecture-deck" / "assets" / "examples" / "quadratic-vertex"
    lecture = json.loads((source / "lecture.json").read_text(encoding="utf-8"))
    deck = lecture["deck"]
    deck["canvas"] = {"w": 1280, "h": 720}
    deck["course"] = "数学"
    deck["subtitle"] = "旧版字段"
    deck["durationSec"] = 75
    deck.pop("slideDir", None)
    deck.pop("createdAt", None)
    lecture["defaults"]["advance"] = "manual"
    lecture["defaults"]["panelPlacement"] = "right"
    files = {
        "lecture.json": json.dumps(lecture, ensure_ascii=False),
        "manifest.json": (source / "manifest.json").read_text(encoding="utf-8"),
        "runtime/index.html": (REPO_ROOT / "skills" / "interactive-lecture-deck" / "assets" / "runtime" / "index.html").read_text(encoding="utf-8"),
    }
    for slide in (source / "slides").glob("s*.html"):
        files[f"slides/{slide.name}"] = slide.read_text(encoding="utf-8")

    store.write_deck("legacy-envelope-task", files)
    stored = json.loads(store.deck_root("legacy-envelope-task").joinpath("lecture.json").read_text(encoding="utf-8"))
    assert stored["deck"]["canvas"] == {"width": 1280, "height": 720, "format": "ppt169"}
    assert stored["deck"]["slideDir"] == "slides"
    assert stored["deck"]["createdAt"].endswith("Z")
    assert stored["extensions"]["legacyDeck"]["course"] == "数学"
    assert "advance" not in stored["defaults"]
    assert stored["defaults"]["panel"]["placement"] == "auto"
    assert asyncio.run(store.build_and_validate_deck("legacy-envelope-task"))["ok"] is True


def test_web_fetch_rejects_private_addresses() -> None:
    with pytest.raises(ValueError, match="private"):
        asyncio.run(_assert_public_url("http://127.0.0.1/latest"))
