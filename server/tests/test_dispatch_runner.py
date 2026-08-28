"""Execution-runner tests: fake provider in, canonical identity out (issue #60).

The runner owns AgentRun/SkillRun lifecycle and the single provider
invocation.  These tests prove:

* identity is stable within one attempt and fresh on every retry attempt;
* provider exceptions are normalised into the same lifecycle closure
  (``agent.failed``/``skill.failed`` + durable rows ended), then re-raised;
* the runner never emits a UI-specific payload — every event is one of the
  canonical dispatch kinds the public projector consumes.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from lingxilearn.agents.providers import ProviderError, ProviderResult
from lingxilearn.runtime.contracts import Cost, DoneCondition, PlannedTask
from lingxilearn.runtime.dispatch.binding import Resolution
from lingxilearn.runtime.dispatch.projection import DispatchProjector
from lingxilearn.runtime.dispatch.runner import ExecutionRunner
from lingxilearn.state.agent_task_state import Goal

CANONICAL_DISPATCH_KINDS = {
    "work.claimed",
    "node.revising",
    "node.started",
    "node.held",
    "agent.started",
    "skill.started",
    "agent.status",
    "agent.completed",
    "agent.failed",
    "skill.completed",
    "skill.failed",
}
"""The runner may emit only this vocabulary; UI envelopes are not its job."""

UI_ENVELOPE_KEYS = {"scope", "toolKind", "agentRunId", "skillRunId", "displayTitle"}
"""Camel-cased public-stream envelope fields the runner must never build."""


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


class _Owner:
    """Runner delegation owner; these tests never delegate."""

    async def run_child(self, **kwargs: Any) -> ProviderResult:  # pragma: no cover
        raise AssertionError(f"unexpected delegation: {kwargs}")


def _deps(repo: FakeRepo, emitted: list[tuple[str, dict[str, Any]]]) -> Any:
    return SimpleNamespace(
        task_id="task_1",
        learner_id="learner_1",
        goal=Goal(goal_type="learn", topic="量子叠加"),
        execution_id="exec_1",
        turn_id="turn_1",
        runtime_repository=repo,
        graph_runtime=None,
        model=None,
        settings=None,
        artifacts=None,
        registry=None,
        pack=None,
        user_message={},
        shared_skills=(),
        emit=lambda kind, payload: emitted.append((kind, dict(payload))),
    )


def _runner(repo: FakeRepo, emitted: list[tuple[str, dict[str, Any]]]) -> ExecutionRunner:
    deps = _deps(repo, emitted)
    return ExecutionRunner(deps, DispatchProjector(lambda: deps.emit), owner=_Owner())


def _task() -> PlannedTask:
    return PlannedTask(
        id="t1",
        capability="content.visual",
        done_when=DoneCondition(kind="always"),
        rationale="测试任务",
        estimated_cost=Cost(),
    )


def _resolution() -> Resolution:
    return Resolution(
        capability="content.visual",
        skill_id="visual-skill",
        provider="p_visual",
        display_name="可视化讲解",
        skill_version="2.0.0",
        skill_checksum="sha256:cafe",
    )


async def test_begin_mints_identity_and_persists_rows() -> None:
    repo, emitted = FakeRepo(), []
    runner = _runner(repo, emitted)
    prepared = await runner.begin(
        _task(), resolution=_resolution(), node_id="n1", emit_node_events=True
    )

    assert prepared.run_context.agent_run_id.startswith("ar_")
    assert prepared.skill_run_id.startswith("sr_")
    assert repo.agent_runs[0]["agent_run_id"] == prepared.run_context.agent_run_id
    assert repo.agent_runs[0]["capability"] == "content.visual"
    assert repo.skill_runs[0]["skill_id"] == "visual-skill"
    assert repo.skill_runs[0]["version"] == "2.0.0"
    assert repo.skill_runs[0]["checksum"] == "sha256:cafe"

    kinds = [kind for kind, _ in emitted]
    assert kinds == [
        "node.started",
        "agent.started",
        "skill.started",
        "agent.status",
    ], "exactly one started lifecycle, in order — never a duplicate emission"


async def test_each_attempt_gets_a_fresh_identity() -> None:
    """WorkItem retry ≠ AgentRun reuse: two attempts, two run ids (issue #18)."""

    repo, emitted = FakeRepo(), []
    runner = _runner(repo, emitted)
    first = await runner.begin(_task(), resolution=_resolution(), node_id="n1")
    second = await runner.begin(_task(), resolution=_resolution(), node_id="n1")
    assert first.run_context.agent_run_id != second.run_context.agent_run_id
    assert first.skill_run_id != second.skill_run_id
    assert len(repo.agent_runs) == 2


async def test_successful_invoke_closes_identity_and_emits_completion() -> None:
    repo, emitted = FakeRepo(), []
    runner = _runner(repo, emitted)
    prepared = await runner.begin(_task(), resolution=_resolution(), node_id="n1")

    async def provider(context: Any) -> ProviderResult:
        assert context.run_context.agent_run_id == prepared.run_context.agent_run_id
        assert context.run_context.skill_run_id == prepared.skill_run_id
        return ProviderResult(status="completed", detail="done")

    result = await runner.invoke(provider, _task(), prepared, profile={}, prior_results={})
    assert result.status == "completed"
    assert repo.agent_runs[0]["status"] == "completed"
    assert repo.agent_runs[0]["ended"] is True
    assert repo.skill_runs[0]["status"] == "completed"
    kinds = [kind for kind, _ in emitted]
    assert kinds.count("agent.completed") == 1
    assert kinds.count("skill.completed") == 1


async def test_provider_error_is_normalised_then_reraised() -> None:
    repo, emitted = FakeRepo(), []
    runner = _runner(repo, emitted)
    prepared = await runner.begin(_task(), resolution=_resolution(), node_id="n1")

    async def provider(context: Any) -> ProviderResult:
        raise ProviderError("model declined")

    with pytest.raises(ProviderError, match="model declined"):
        await runner.invoke(provider, _task(), prepared, profile={}, prior_results={})
    assert repo.agent_runs[0]["status"] == "failed"
    assert repo.skill_runs[0]["status"] == "failed"
    failed = next(payload for kind, payload in emitted if kind == "agent.failed")
    assert failed["detail"] == "model declined"
    assert failed["agent_run_id"] == prepared.run_context.agent_run_id


async def test_unexpected_exception_is_normalised_then_reraised() -> None:
    repo, emitted = FakeRepo(), []
    runner = _runner(repo, emitted)
    prepared = await runner.begin(_task(), resolution=_resolution(), node_id="n1")

    async def provider(context: Any) -> ProviderResult:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await runner.invoke(provider, _task(), prepared, profile={}, prior_results={})
    assert repo.agent_runs[0]["status"] == "failed"
    failed = next(payload for kind, payload in emitted if kind == "agent.failed")
    assert failed["detail"] == "ValueError: boom"


async def test_runner_never_emits_ui_specific_payloads() -> None:
    """Public envelopes (scope/toolKind/camel ids) belong to the projector."""

    repo, emitted = FakeRepo(), []
    runner = _runner(repo, emitted)
    prepared = await runner.begin(
        _task(), resolution=_resolution(), node_id="n1", emit_node_events=True
    )

    async def provider(context: Any) -> ProviderResult:
        return ProviderResult(status="completed")

    await runner.invoke(provider, _task(), prepared, profile={}, prior_results={})
    assert emitted, "the lifecycle must have emitted canonical events"
    for kind, payload in emitted:
        assert kind in CANONICAL_DISPATCH_KINDS, f"non-canonical event kind: {kind}"
        assert not UI_ENVELOPE_KEYS & set(payload), f"UI envelope keys in {kind}: {payload}"
