"""Dispatcher-owned AgentRun/SkillRun lifecycle tests (issue #18 §4.4/§4.6).

The dispatcher is the single owner of agent lifecycle identity: every real
provider attempt gets a fresh ``agent_run_id``, rows are durable when a
repository is present, and provider-side events are stamped with the canonical
identity instead of inventing their own.
"""

from __future__ import annotations

from typing import Any

from lingxilearn.agents.providers import ProviderContext, ProviderResult, descriptor, register
from lingxilearn.runtime.contracts import Cost, DoneCondition, PlannedTask
from lingxilearn.runtime.dispatch import DispatchDeps, Dispatcher
from lingxilearn.runtime.guardrails import Budget
from lingxilearn.runtime.run_context import (
    RunContext,
    new_agent_run_id,
    new_skill_run_id,
    presentation_role_for,
)
from lingxilearn.state.capabilities import info
from lingxilearn.state.session_state import Goal

SKILLS = [
    {
        "skill_id": "knowledge-qa",
        "capabilities": ["dialog.answer"],
        "provider": "test_answerer",
        "cost": {"latency_weight": 0.5},
        "preconditions": {},
        "enabled": True,
        "display_name": "知识点答疑",
        "version": "1.4.0",
        "checksum": "sha256:deadbeef",
    },
    {
        "skill_id": "visual-explainer",
        "capabilities": ["content.visual"],
        "provider": "test_visualizer",
        "cost": {"latency_weight": 0.9},
        "preconditions": {},
        "enabled": True,
        "display_name": "可视化讲解",
        "version": "2.0.0",
        "checksum": "sha256:cafe",
    },
]


class FakeRepo:
    def __init__(self) -> None:
        self.agent_runs: list[dict[str, Any]] = []
        self.skill_runs: list[dict[str, Any]] = []

    async def create_agent_run(self, **fields: Any) -> dict[str, Any]:
        self.agent_runs.append(fields)
        return fields

    async def update_agent_run(self, agent_run_id: str, **fields: Any) -> dict[str, Any]:
        for row in self.agent_runs:
            if row["agent_run_id"] == agent_run_id:
                row.update(fields)
        return {}

    async def create_skill_run(self, **fields: Any) -> dict[str, Any]:
        self.skill_runs.append(fields)
        return fields

    async def update_skill_run(self, skill_run_id: str, **fields: Any) -> dict[str, Any]:
        for row in self.skill_runs:
            if row["skill_run_id"] == skill_run_id:
                row.update(fields)
        return {}


class FakeRuntime:
    def __init__(self) -> None:
        self.emitted: list[tuple[str, dict[str, Any]]] = []

    def emit(self, channel: str, value: Any) -> None:
        self.emitted.append((channel, dict(value)))


# Registered at import so every dispatcher test can resolve them; ids are
# unique to this module so they cannot collide with real providers.
PROVIDER_IDENTITY: dict[str, list[dict[str, Any]]] = {"answer": [], "visual": []}


@register("test_answerer", display_name="知识点答疑", execution_kind="model")
async def _test_answerer(context: ProviderContext) -> ProviderResult:
    assert context.run_context is not None
    PROVIDER_IDENTITY["answer"].append(dict(context.run_context.identity_fields()))
    assert context.runtime is not None
    context.runtime.narrate("正在检索你提供的资料…")
    return ProviderResult(status="completed", learner_message="答案")


@register("test_visualizer", display_name="可视化讲解", execution_kind="model")
async def _test_visualizer(context: ProviderContext) -> ProviderResult:
    assert context.run_context is not None
    PROVIDER_IDENTITY["visual"].append(dict(context.run_context.identity_fields()))
    return ProviderResult(status="completed", artifacts=["visual"])


def _task(capability: str, *, critical_path: bool = True) -> PlannedTask:
    return PlannedTask(
        id="t1",
        capability=capability,
        done_when=DoneCondition(kind="always"),
        rationale="测试任务",
        estimated_cost=Cost(critical_path=critical_path),
    )


class FakeRuntimeState:
    """Just enough of RuntimeStateRepository for the always-done path."""

    async def evidence_for_task(self, task_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        return []

    async def profile_for(self, learner_id: str) -> list[dict[str, Any]]:
        return []

    async def append_evidence(self, records: Any) -> list[dict[str, Any]]:
        return []


def _deps(repo: FakeRepo | None, *, runtime: Any = None) -> DispatchDeps:
    return DispatchDeps(
        runtime_state=FakeRuntimeState(),  # type: ignore[arg-type]
        learner_id="learner_1",
        task_id="task_1",
        goal=Goal(goal_type="learn", topic="量子叠加"),
        skills=SKILLS,
        repository=repo,
        graph_runtime=runtime,
        emit=None,
        execution_id="exec_1",
        turn_id="turn_1",
    )


async def test_dispatcher_creates_canonical_identity_rows() -> None:
    repo = FakeRepo()
    dispatcher = Dispatcher(_deps(repo, runtime=FakeRuntime()))
    outcome = await dispatcher.run(_task("dialog.answer"), profile={}, budget=Budget.from_dict({}))
    assert outcome.status == "completed"

    assert len(repo.agent_runs) == 1
    run = repo.agent_runs[0]
    assert run["agent_run_id"].startswith("ar_")
    assert run["provider_id"] == "test_answerer"
    assert run["agent_display_name"] == "知识点答疑"
    assert run["presentation_role"] == "primary", "dialog.answer is conversational+turn_complete"
    assert run["turn_id"] == "turn_1"
    assert run["execution_id"] == "exec_1"

    assert len(repo.skill_runs) == 1
    skill = repo.skill_runs[0]
    assert skill["skill_run_id"].startswith("sr_")
    assert skill["skill_id"] == "knowledge-qa"
    assert skill["display_name"] == "知识点答疑"
    assert skill["version"] == "1.4.0"
    assert skill["checksum"] == "sha256:deadbeef"

    assert PROVIDER_IDENTITY["answer"], "provider must observe its run context"


async def test_retry_attempt_gets_a_fresh_agent_run_id() -> None:
    repo = FakeRepo()
    dispatcher = Dispatcher(_deps(repo, runtime=FakeRuntime()))
    first = await dispatcher.run(_task("dialog.answer"), profile={}, budget=Budget.from_dict({}))
    second = await dispatcher.run(_task("dialog.answer"), profile={}, budget=Budget.from_dict({}))
    assert first.status == second.status == "completed"
    ids = [row["agent_run_id"] for row in repo.agent_runs]
    assert len(ids) == 2 and ids[0] != ids[1], "WorkItem != AgentRun (issue #18 §4.4)"


async def test_conversational_capability_is_primary_background_is_not() -> None:
    assert (
        presentation_role_for(
            capability="dialog.answer",
            capability_info=info("dialog.answer"),
            critical_path=True,
        )
        == "primary"
    )
    assert (
        presentation_role_for(
            capability="content.visual",
            capability_info=info("content.visual"),
            critical_path=True,
        )
        == "supporting"
    )
    assert (
        presentation_role_for(
            capability="content.visual",
            capability_info=info("content.visual"),
            critical_path=False,
        )
        == "background"
    )


async def test_lifecycle_events_carry_identity() -> None:
    repo = FakeRepo()
    emitted: list[tuple[str, dict[str, Any]]] = []

    def emit(kind: str, payload: dict[str, Any]) -> None:
        emitted.append((kind, payload))

    deps = _deps(repo, runtime=FakeRuntime())
    deps.emit = emit
    dispatcher = Dispatcher(deps)
    await dispatcher.run(_task("dialog.answer"), profile={}, budget=Budget.from_dict({}))

    kinds = [kind for kind, _ in emitted]
    assert "agent.started" in kinds
    assert "skill.started" in kinds
    assert "agent.completed" in kinds
    assert "skill.completed" in kinds

    started = next(payload for kind, payload in emitted if kind == "agent.started")
    completed = next(payload for kind, payload in emitted if kind == "agent.completed")
    assert started["agent_run_id"] == completed["agent_run_id"]
    assert started["display_name"] == "知识点答疑"
    assert started["presentation_role"] == "primary"

    skill_started = next(payload for kind, payload in emitted if kind == "skill.started")
    skill_done = next(payload for kind, payload in emitted if kind == "skill.completed")
    assert skill_started["skill_run_id"] == skill_done["skill_run_id"]
    assert skill_started["agent_run_id"] == started["agent_run_id"]


async def test_provider_runtime_stamps_identity_on_every_event() -> None:
    """The dispatcher identity reaches provider-side emits automatically."""
    from lingxilearn.runtime.dispatch import _ProviderRuntime

    runtime = FakeRuntime()
    context = RunContext(
        task_id="task_1",
        execution_id="exec_1",
        turn_id="turn_1",
        agent_run_id="ar_stamp",
        skill_run_id="sr_stamp",
    )
    proxy = _ProviderRuntime(runtime, task_id="t1", node_id="node_9", step=3, run_context=context)
    proxy.emit("agent_task", {"type": "agent.status", "text": "工作中"})
    proxy.narrate("正在根据你的掌握情况选择讲法…", code="adaptive.select")

    assert runtime.emitted[0][1]["agent_run_id"] == "ar_stamp"
    assert runtime.emitted[0][1]["skill_run_id"] == "sr_stamp"
    assert runtime.emitted[0][1]["execution_id"] == "exec_1"
    assert runtime.emitted[0][1]["node_id"] == "node_9"

    narration = runtime.emitted[1][1]
    assert narration["type"] == "agent.status"
    assert narration["text"] == "正在根据你的掌握情况选择讲法…"
    assert narration["code"] == "adaptive.select"
    assert narration["agent_run_id"] == "ar_stamp"


def test_provider_descriptors_are_registered_with_display_names() -> None:
    load = descriptor("test_answerer")
    assert load is not None
    assert load.display_name == "知识点答疑"
    assert load.execution_kind == "model"
    unknown = descriptor("never_registered_provider")
    assert unknown is None


def test_run_context_identity_fields() -> None:
    context = RunContext(
        task_id="t", execution_id="e", turn_id="tu", agent_run_id="ar", skill_run_id="sr"
    )
    fields = context.identity_fields()
    assert fields == {
        "task_id": "t",
        "execution_id": "e",
        "turn_id": "tu",
        "agent_run_id": "ar",
        "skill_run_id": "sr",
    }
    assert new_agent_run_id() != new_agent_run_id()
    assert new_skill_run_id().startswith("sr_")
