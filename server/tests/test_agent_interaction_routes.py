from types import SimpleNamespace

import pytest

from lingxilearn.api.agent_interactions import (
    LegacyToolPermissionDecision,
    LegacyToolPermissionRequest,
    SchedulePermissionDecision,
    SchedulePermissionRequest,
    decide_schedule_permissions,
    legacy_copilot_tool_permission,
)
from lingxilearn.learner import LearnerContext


class _AgentTasks:
    def __init__(self) -> None:
        self.decisions: list[dict[str, str]] = []

    async def decide_schedule_permission(
        self, *, learner_id: str, decisions: list[dict[str, str]]
    ) -> list[dict[str, object]]:
        assert learner_id == "learner-1"
        self.decisions = decisions
        return [
            {
                "toolCallId": item["toolCallId"],
                "decision": item["decision"],
                "applied": True,
            }
            for item in decisions
        ]


def _context() -> LearnerContext:
    return LearnerContext(
        learner_id="learner-1",
        subject="subject-1",
        issuer="test",
        profile={},
        mastery={},
        misconceptions=[],
        preferences={},
    )


@pytest.mark.asyncio
async def test_schedule_permission_uses_proposal_identity() -> None:
    agent_tasks = _AgentTasks()
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(services=SimpleNamespace(agent_tasks=agent_tasks)))
    )
    body = SchedulePermissionRequest(
        decisions=[SchedulePermissionDecision(proposalId="proposal-1", decision="allow")]
    )

    response = await decide_schedule_permissions(body, request, _context())

    assert agent_tasks.decisions == [{"toolCallId": "proposal-1", "decision": "allow"}]
    assert response == {
        "success": True,
        "results": [{"proposalId": "proposal-1", "decision": "allow", "applied": True}],
    }


@pytest.mark.asyncio
async def test_deprecated_copilot_adapter_preserves_old_wire_shape() -> None:
    agent_tasks = _AgentTasks()
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(services=SimpleNamespace(agent_tasks=agent_tasks)))
    )
    body = LegacyToolPermissionRequest(
        decisions=[LegacyToolPermissionDecision(toolCallId="proposal-2", decision="skip")]
    )

    response = await legacy_copilot_tool_permission(body, request, _context())

    assert response == {
        "success": True,
        "results": [{"toolCallId": "proposal-2", "decision": "skip", "applied": True}],
    }
