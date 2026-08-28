"""Agent-task command and query HTTP endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..application import agent_task_create_payload_digest
from ..contracts.rest_models import (
    AgentMessageResponse,
    AgentTaskCancelResponse,
    AgentTaskCreateResponse,
    AgentTaskDeleteResponse,
    AgentTaskForkResponse,
    AgentTaskListResponse,
    AgentTaskMetaResponse,
    AgentTaskRestoreResponse,
    AgentTaskSnapshotResponse,
)
from ..learner import LearnerContext
from .dependencies import current_learner_context, not_found, services_of

router = APIRouter(prefix="/api")


class CreateAgentTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=4000)
    resources: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=192)


class AgentTaskMetadataPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=4000)
    is_pinned: bool | None = None
    is_unread: bool | None = None
    resources: list[dict[str, Any]] | None = None


class AgentMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    resources: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=192)


async def _validated_task_context(
    request: Request,
    context: LearnerContext,
    resources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Transport mapping for task-resource validation; logic lives in the service."""

    services = services_of(request)
    try:
        return await services.agent_tasks.validate_task_resources(context.learner_id, resources)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise not_found() from exc


@router.post("/agent-tasks", status_code=202, response_model=AgentTaskCreateResponse)
async def create_agent_task(
    body: CreateAgentTask,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    services = services_of(request)
    task_id = f"t-{uuid.uuid4().hex[:20]}"
    payload_digest = agent_task_create_payload_digest(
        prompt=body.prompt,
        resources=body.resources,
    )
    if body.idempotency_key:
        existing = await services.agent_tasks.get_agent_task_by_create_idempotency_key(
            context.learner_id, body.idempotency_key
        )
        if existing is not None:
            if existing.create_payload_digest != payload_digest:
                raise HTTPException(status_code=409, detail="idempotency_key_reused")
            result = {"id": existing.id, "status": existing.status}
            if existing.error:
                result["error"] = existing.error
            return result
    try:
        task_resources = await _validated_task_context(request, context, body.resources)
        created = await services.agent_tasks.create_agent_task(
            task_id=task_id,
            learner_id=context.learner_id,
            prompt=body.prompt,
            resources=task_resources,
            idempotency_key=body.idempotency_key,
            create_payload_digest=payload_digest,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=409 if detail == "idempotency_key_reused" else 400,
            detail=detail,
        ) from exc
    return created


@router.get("/agent-tasks", response_model=AgentTaskListResponse)
async def list_agent_tasks(
    request: Request,
    scope: str = Query("active"),
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    if scope not in {"active", "archived"}:
        raise HTTPException(status_code=400, detail="invalid_scope")
    return {
        "tasks": await services_of(request).agent_tasks.list_agent_tasks(
            context.learner_id, scope=scope
        )
    }


@router.get("/agent-tasks/{task_id}", response_model=AgentTaskSnapshotResponse)
async def get_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    services = services_of(request)
    try:
        return await services.agent_tasks.agent_task_snapshot(
            task_id, learner_id=context.learner_id
        )
    except KeyError as exc:
        raise not_found() from exc


@router.post(
    "/agent-tasks/{task_id}/messages",
    status_code=202,
    response_model=AgentMessageResponse,
)
async def post_agent_message(
    task_id: str,
    body: AgentMessage,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    services = services_of(request)
    try:
        task_resources = await _validated_task_context(request, context, body.resources)
        if task_resources:
            await services.agent_tasks.update_agent_task(
                task_id, context.learner_id, resources=task_resources
            )
        result = await services.agent_tasks.agent_message(
            task_id,
            body.message,
            learner_id=context.learner_id,
            idempotency_key=body.idempotency_key,
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "accepted", "turnId": str((result or {}).get("turnId") or "")}


@router.patch("/agent-tasks/{task_id}", response_model=AgentTaskMetaResponse)
async def patch_agent_task(
    task_id: str,
    body: AgentTaskMetadataPatch,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.update_agent_task(
            task_id,
            context.learner_id,
            title=body.title,
            is_pinned=body.is_pinned,
            is_unread=body.is_unread,
            resources=body.resources,
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/agent-tasks/{task_id}", response_model=AgentTaskDeleteResponse)
async def delete_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.delete_agent_task(task_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/agent-tasks/{task_id}/restore", response_model=AgentTaskRestoreResponse)
async def restore_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.restore_agent_task(
            task_id, context.learner_id
        )
    except KeyError as exc:
        raise not_found() from exc


@router.post("/agent-tasks/{task_id}/fork", status_code=202, response_model=AgentTaskForkResponse)
async def fork_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.fork_agent_task(task_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/agent-tasks/{task_id}/cancel", response_model=AgentTaskCancelResponse)
async def cancel_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.cancel_agent_task(task_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc
