"""Canonical event → public projection regression for the dispatch split (issue #60).

The dispatcher emits each canonical runtime event exactly once, in a stable
order, and the public projector turns that stream into one span lifecycle —
never a duplicate.  These tests pin that contract after the ownership split:
provider outcomes flow execution → canonical event → existing projector, with
no provider-specific emission side channel.
"""

from __future__ import annotations

from typing import Any

from lingxilearn.agents.providers import ProviderContext, ProviderResult, register
from lingxilearn.runtime.contracts import Cost, DoneCondition, PlannedTask
from lingxilearn.runtime.dispatch import DispatchDeps, Dispatcher
from lingxilearn.runtime.guardrails import Budget
from lingxilearn.runtime.public_projection import PublicProjector
from lingxilearn.state.agent_task_state import Goal


@register("test_event_answerer", display_name="事件答疑", execution_kind="model")
async def _test_event_answerer(context: ProviderContext) -> ProviderResult:
    return ProviderResult(status="completed", learner_message="答案", detail="答完")


@register("test_event_visualizer", display_name="事件可视化", execution_kind="model")
async def _test_event_visualizer(context: ProviderContext) -> ProviderResult:
    return ProviderResult(status="completed", artifacts=["visual"], detail="图成")


SKILLS = [
    {
        "skill_id": "qa-skill",
        "capabilities": ["dialog.answer"],
        "provider": "test_event_answerer",
        "cost": {"latency_weight": 0.5},
        "preconditions": {},
        "enabled": True,
        "display_name": "知识点答疑",
        "version": "1.0.0",
        "checksum": "sha256:qa",
    },
    {
        "skill_id": "visual-skill",
        "capabilities": ["content.visual"],
        "provider": "test_event_visualizer",
        "cost": {"latency_weight": 0.9},
        "preconditions": {},
        "enabled": True,
        "display_name": "可视化讲解",
        "version": "2.0.0",
        "checksum": "sha256:cafe",
    },
]


class FakeRuntimeState:
    async def evidence_for_task(self, task_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        return []

    async def profile_for(self, learner_id: str) -> list[dict[str, Any]]:
        return []

    async def append_evidence(self, records: Any) -> list[dict[str, Any]]:
        return []


def _task(capability: str) -> PlannedTask:
    return PlannedTask(
        id="t1",
        capability=capability,
        done_when=DoneCondition(kind="always"),
        rationale="测试任务",
        estimated_cost=Cost(),
    )


async def _run(capability: str) -> tuple[list[tuple[str, dict[str, Any]]], Any]:
    emitted: list[tuple[str, dict[str, Any]]] = []
    deps = DispatchDeps(
        runtime_state=FakeRuntimeState(),  # type: ignore[arg-type]
        learner_id="learner_1",
        task_id="task_1",
        goal=Goal(goal_type="learn", topic="事件回归"),
        skills=SKILLS,
        emit=lambda kind, payload: emitted.append((kind, dict(payload))),
        execution_id="exec_1",
        turn_id="turn_1",
    )
    outcome = await Dispatcher(deps).run(_task(capability), profile={}, budget=Budget.from_dict({}))
    return emitted, outcome


def _project(emitted: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    projector = PublicProjector(chat_id="task_1", execution_id="exec_1", turn_id="turn_1")
    envelopes: list[dict[str, Any]] = []
    for kind, payload in emitted:
        envelopes.extend(
            projector.consume(
                {"kind": kind, "agent": str(payload.get("agent") or ""), "payload": payload}
            )
        )
    return envelopes


async def test_successful_run_emits_each_canonical_event_once_in_order() -> None:
    emitted, outcome = await _run("dialog.answer")
    assert outcome.status == "completed"

    kinds = [kind for kind, _ in emitted]
    assert kinds == [
        "node.started",
        "agent.started",
        "skill.started",
        "agent.status",
        "agent.completed",
        "skill.completed",
    ], "each lifecycle event exactly once, in canonical order"

    envelopes = _project(emitted)
    span_starts = [
        e for e in envelopes if e["type"] == "span" and e["payload"].get("event") == "start"
    ]
    span_ends = [e for e in envelopes if e["type"] == "span" and e["payload"].get("event") == "end"]
    assert len(span_starts) == 1, "no duplicate agent span emission"
    assert len(span_ends) == 1
    assert span_starts[0]["payload"]["agentRunId"] == span_ends[0]["payload"]["agentRunId"]


async def test_held_outcome_emits_node_held_once_after_completion() -> None:
    emitted, outcome = await _run("content.visual")
    assert outcome.status == "completed"
    assert outcome.held is True

    kinds = [kind for kind, _ in emitted]
    assert kinds.count("node.held") == 1
    assert kinds.index("node.held") > kinds.index("agent.completed")
    held_payload = next(payload for kind, payload in emitted if kind == "node.held")
    assert held_payload["held"] is True
    assert held_payload["status"] == "completed"
