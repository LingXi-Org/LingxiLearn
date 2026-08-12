from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from lingxigraph import AIMessage, FilesystemSkillSource

from lingxilearn.agents.artifact_store import ArtifactError, ArtifactStore
from lingxilearn.agents.contracts import IntentContext, LectureHookResult, extract_json
from lingxilearn.agents.graph import build_agent_graph
from lingxilearn.agents.web_tools import _assert_public_url
from lingxilearn.config import Settings
from lingxilearn.service import Service

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_agent_skills_are_discoverable_and_have_resources() -> None:
    for name in ("lecture-hook", "visual-explainer"):
        skill_dir = REPO_ROOT / "skills" / name
        source = FilesystemSkillSource(skill_dir)
        metadata = source.discover()
        assert [item.name for item in metadata] == [name]
        assert (skill_dir / "SKILL.md").read_text(encoding="utf-8").startswith("---")


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
    assert ("recognize_intent", "visual_explainer", None) in edges
    assert ("lecture_hook", "merge_results", "all") in edges
    assert ("visual_explainer", "merge_results", "all") in edges


@pytest.mark.asyncio
async def test_specialists_start_in_parallel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    timeline: list[str] = []
    lecture = {
        "schema_version": "lecture-hook-result.v1",
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
        def __init__(self, name: str) -> None:
            self.name = name

        async def ainvoke(self, _input: Any, _config: Any) -> dict[str, Any]:
            timeline.append(f"{self.name}:start")
            await asyncio.sleep(0.03)
            timeline.append(f"{self.name}:end")
            if self.name == "intent-recognizer":
                content = '{"topic":"TCP 拥塞控制"}'
            elif self.name == "lecture-hook":
                content = LectureHookResult.model_validate(lecture).model_dump_json()
            else:
                content = (
                    "<!doctype html><html lang='zh-CN'><head><title>TCP</title></head>"
                    "<body><button>观察</button></body></html>"
                )
            return {"messages": [AIMessage(content=content)]}

    def fake_create_agent(_model: Any, *_tools: Any, name: str, **_kwargs: Any) -> FakeAgent:
        return FakeAgent(name)

    monkeypatch.setattr("lingxilearn.agents.graph.create_agent", fake_create_agent)
    settings = Settings(_env_file="", agent_task_dir=tmp_path)
    store = ArtifactStore(settings)

    async def fake_validate(_task_id: str) -> dict[str, Any]:
        return {"ok": True, "static": {"ok": True}, "palette": {}, "screenshot": "fixture"}

    monkeypatch.setattr(store, "validate_html", fake_validate)

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
    assert result["status"] == "completed"
    first_end = min(
        index
        for index, item in enumerate(timeline)
        if item in {"lecture-hook:end", "visual-explainer:end"}
    )
    assert timeline.index("lecture-hook:start") < first_end
    assert timeline.index("visual-explainer:start") < first_end


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

    template = (REPO_ROOT / "skills" / "visual-explainer" / "assets" / "template.html").read_text(
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


def test_web_fetch_rejects_private_addresses() -> None:
    with pytest.raises(ValueError, match="private"):
        asyncio.run(_assert_public_url("http://127.0.0.1/latest"))
