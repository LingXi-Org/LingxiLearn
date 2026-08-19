"""Real-concurrency regression for parallel-safe siblings (issue #60).

The dispatch node gathers same-tier parallel-safe tasks with
``asyncio.gather`` over ``Dispatcher.run``.  This test proves the pipeline
keeps that semantic after the ownership split: two sibling tasks genuinely
overlap, instead of degrading into a hidden serial loop.

The proof is a rendezvous, not a wall-clock guess: each provider blocks until
*both* providers have started.  Serial execution deadlocks into the timeout
and fails the test; real concurrency lets both through.
"""

from __future__ import annotations

import asyncio
from typing import Any

from lingxilearn.agents.providers import ProviderContext, ProviderResult, register
from lingxilearn.runtime.contracts import Cost, DoneCondition, PlannedTask
from lingxilearn.runtime.dispatch import DispatchDeps, Dispatcher
from lingxilearn.runtime.guardrails import Budget
from lingxilearn.state.session_state import Goal

_PROBE: dict[str, Any] = {}


@register("test_parallel_visual", display_name="并行可视化", execution_kind="model")
async def _test_parallel_visual(context: ProviderContext) -> ProviderResult:
    _PROBE["started"].append("visual")
    if len(_PROBE["started"]) == 2:
        _PROBE["both_started"].set()
    await asyncio.wait_for(_PROBE["both_started"].wait(), timeout=5)
    return ProviderResult(status="completed", detail="visual done")


@register("test_parallel_deck", display_name="并行课件", execution_kind="model")
async def _test_parallel_deck(context: ProviderContext) -> ProviderResult:
    _PROBE["started"].append("deck")
    if len(_PROBE["started"]) == 2:
        _PROBE["both_started"].set()
    await asyncio.wait_for(_PROBE["both_started"].wait(), timeout=5)
    return ProviderResult(status="completed", detail="deck done")


SKILLS = [
    {
        "skill_id": "visual-skill",
        "capabilities": ["content.visual"],
        "provider": "test_parallel_visual",
        "cost": {"latency_weight": 0.5},
        "preconditions": {},
        "enabled": True,
        "version": "1.0.0",
        "checksum": "sha256:visual",
    },
    {
        "skill_id": "deck-skill",
        "capabilities": ["content.deck"],
        "provider": "test_parallel_deck",
        "cost": {"latency_weight": 0.5},
        "preconditions": {},
        "enabled": True,
        "version": "1.0.0",
        "checksum": "sha256:deck",
    },
]


class FakeRuntimeState:
    async def evidence_for_task(self, task_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        return []

    async def profile_for(self, learner_id: str) -> list[dict[str, Any]]:
        return []

    async def append_evidence(self, records: Any) -> list[dict[str, Any]]:
        return []


class FakeRepo:
    def __init__(self) -> None:
        self.agent_runs: list[dict[str, Any]] = []

    async def create_agent_run(self, **fields: Any) -> dict[str, Any]:
        self.agent_runs.append(fields)
        return fields

    async def update_agent_run(self, agent_run_id: str, **fields: Any) -> dict[str, Any]:
        for row in self.agent_runs:
            if row["agent_run_id"] == agent_run_id:
                row.update(fields)
        return {}

    async def create_skill_run(self, **fields: Any) -> dict[str, Any]:
        return fields

    async def update_skill_run(self, skill_run_id: str, **fields: Any) -> dict[str, Any]:
        return {}


def _task(task_id: str, capability: str) -> PlannedTask:
    return PlannedTask(
        id=task_id,
        capability=capability,
        done_when=DoneCondition(kind="always"),
        rationale=task_id,
        estimated_cost=Cost(parallel_safe=True),
    )


async def test_parallel_safe_siblings_overlap_in_real_time() -> None:
    _PROBE.clear()
    _PROBE["started"] = []
    _PROBE["both_started"] = asyncio.Event()

    repo = FakeRepo()
    dispatcher = Dispatcher(
        DispatchDeps(
            runtime_state=FakeRuntimeState(),  # type: ignore[arg-type]
            learner_id="learner_1",
            task_id="task_parallel",
            goal=Goal(goal_type="learn", topic="并发回归"),
            skills=SKILLS,
            runtime_repository=repo,
            execution_id="exec_1",
            turn_id="turn_1",
        )
    )

    outcomes = await asyncio.gather(
        dispatcher.run(_task("t_visual", "content.visual"), profile={}, budget=Budget.from_dict({})),
        dispatcher.run(_task("t_deck", "content.deck"), profile={}, budget=Budget.from_dict({})),
    )

    assert _PROBE["both_started"].is_set(), (
        "serial dispatch deadlocks the rendezvous: both providers must start "
        "before either may finish"
    )
    assert sorted(_PROBE["started"]) == ["deck", "visual"]
    assert [outcome.status for outcome in outcomes] == ["completed", "completed"]

    # Concurrency must not blur attempt identity: each sibling kept its own
    # AgentRun, and neither observed the other's run id.
    assert len(repo.agent_runs) == 2
    run_ids = {row["agent_run_id"] for row in repo.agent_runs}
    assert len(run_ids) == 2
    capabilities = {row["capability"] for row in repo.agent_runs}
    assert capabilities == {"content.visual", "content.deck"}
