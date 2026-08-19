"""Capability-gated internal runtime diagnostics.

These endpoints intentionally live outside the public learner API module so the
raw execution surface has an explicit physical boundary as well as authorization.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from lingxi_identity import Principal  # type: ignore[import-untyped]

from ..application import ApplicationServices
from ..auth import get_principal
from ..contracts.rest_models import AgentDecisionsResponse, RuntimeGraphResponse
from ..learner import LearnerContext
from ..runtime.execution_graph import build_execution_graph
from .dependencies import not_found, services_of

router = APIRouter(prefix="/api")

_DEBUG_SECRET_KEYS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "system_prompt",
    "token",
)


def _require_runtime_debug(
    services: ApplicationServices, principal: Principal | None = None
) -> None:
    """Hide raw runtime diagnostics unless the deployment opts in explicitly."""

    if not services.settings.runtime_debug_enabled:
        raise not_found()
    if services.settings.insecure_dev_auth:
        return
    if principal is None or not (
        "runtime:debug" in principal.permissions
        or bool({"admin", "internal"}.intersection(principal.roles))
    ):
        raise not_found()


async def runtime_debug_context(
    request: Request, principal: Principal = Depends(get_principal)
) -> LearnerContext:
    """Authorize the internal debug capability, then resolve its learner scope."""

    services = services_of(request)
    _require_runtime_debug(services, principal)
    try:
        return await services.learners.get_learner_context(principal)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="invalid_identity") from exc


def _redact_runtime_debug(value: Any) -> Any:
    """Recursively remove credentials and prompts from diagnostic payloads."""

    if isinstance(value, Mapping):
        return {
            key: "[REDACTED]"
            if any(
                marker.replace("_", "")
                in re.sub(r"[^a-z0-9]", "", str(key).lower())
                for marker in _DEBUG_SECRET_KEYS
            )
            else _redact_runtime_debug(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_runtime_debug(item) for item in value]
    return value


@router.get("/agent-tasks/{task_id}/decisions", response_model=AgentDecisionsResponse)
async def agent_task_decisions(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(runtime_debug_context),
) -> dict[str, Any]:
    """Every decision this task made: candidates, choice, reason, evidence, diff."""

    services = services_of(request)
    if await services.agent_tasks.get_task_record(task_id, context.learner_id) is None:
        raise not_found()
    decisions = await services.agent_events.decisions_for_task(task_id)
    return {"decisions": _redact_runtime_debug(decisions)}


@router.get(
    "/agent-tasks/{task_id}/runtime-graph", response_model=RuntimeGraphResponse
)
async def agent_task_runtime_graph(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(runtime_debug_context),
) -> dict[str, Any]:
    """Return the durable Sim-compatible runtime graph for this task.

    ``executionGraph`` is the canonical V1 graph whose nodes are AgentRuns --
    the same identities the chat renders (issue #18 section 14).
    ``workflowState`` remains the legacy heuristic projection for today's UI.
    """

    services = services_of(request)
    task = await services.agent_tasks.get_task_record(task_id, context.learner_id)
    if task is None:
        raise not_found()
    execution_id = task.latest_execution_id or task.current_execution_id
    execution = (
        await services.agent_events.get_agent_execution(execution_id, context.learner_id)
        if execution_id
        else None
    )
    state = dict(execution.workflow_state or {}) if execution is not None else {}
    runs = await services.agent_events.agent_runs_for_task(task_id)
    dependencies = await services.agent_events.work_dependencies_for_task(task_id)
    skill_runs = await services.agent_events.skill_runs_for_task(task_id)
    return {
        "id": f"runtime-graph:{task_id}",
        "type": "runtime-graph",
        "taskId": task_id,
        "latestExecutionId": execution.id if execution is not None else None,
        "status": execution.status if execution is not None else task.status,
        "updatedAt": execution.updated_at.isoformat()
        if execution and execution.updated_at
        else None,
        "workflowState": _redact_runtime_debug(state),
        "executionGraph": _redact_runtime_debug(
            build_execution_graph(
                runs,
                task_id=task_id,
                work_dependencies=cast(list[Mapping[str, Any]], dependencies),
                skill_runs=skill_runs,
            )
        ),
    }
