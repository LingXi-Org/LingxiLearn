"""Workspace log HTTP adapters."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ..contracts.rest_models import ExecutionSnapshotResponse
from ..learner import LearnerContext
from .dependencies import current_learner_context, not_found, services_of
from .workspace_route_shared import _workspace_for_id

router = APIRouter(prefix="/api")


@router.get("/logs")
async def list_logs(
    request: Request,
    workspaceId: str = "lingxi",
    limit: int = 50,
    cursor: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _workspace_for_id(request, workspaceId, context)
    return await services_of(request).logs.list_logs(context.learner_id, limit)


@router.get("/logs/stats")
async def log_stats(
    request: Request,
    workspaceId: str = "lingxi",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _workspace_for_id(request, workspaceId, context)
    return await services_of(request).logs.stats(context.learner_id)


@router.get("/logs/export")
async def export_logs(
    request: Request,
    format: str = "json",
    context: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    export = await services_of(request).logs.export(context.learner_id, format)
    headers = (
        {"Content-Disposition": f"attachment; filename={export.filename}"}
        if export.filename
        else None
    )
    return StreamingResponse(iter([export.content]), media_type=export.media_type, headers=headers)


@router.get("/logs/by-execution/{execution_id}")
async def log_by_execution(
    execution_id: str,
    request: Request,
    workspaceId: str = "lingxi",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _workspace_for_id(request, workspaceId, context)
    try:
        return await services_of(request).logs.by_execution(context.learner_id, execution_id)
    except KeyError as exc:
        raise not_found() from exc


@router.get("/logs/execution/{execution_id}", response_model=ExecutionSnapshotResponse)
async def execution_snapshot(
    execution_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).logs.execution_snapshot(context.learner_id, execution_id)
    except KeyError as exc:
        raise not_found() from exc


@router.get("/logs/{log_id}")
async def log_detail(
    log_id: str,
    request: Request,
    workspaceId: str = "lingxi",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _workspace_for_id(request, workspaceId, context)
    detail = await services_of(request).logs.detail(context.learner_id, log_id)
    if detail is None:
        raise not_found()
    return detail
