"""Canonical Workspace HTTP endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..contracts.rest_models import (
    WorkspaceListResponse,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)
from ..learner import LearnerContext
from .dependencies import current_learner_context, services_of
from .mappers.workspaces import workspace_response
from .workspace_route_shared import _workspace, _workspace_for_id

router = APIRouter(prefix="/api/workspaces", tags=["Workspace"])


@router.get("", response_model=WorkspaceListResponse, operation_id="list_workspaces")
async def list_workspaces(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace(request, context)
    return {"workspaces": [workspace_response(workspace)]}


@router.get("/{workspace_id}", response_model=WorkspaceResponse, operation_id="get_workspace")
async def get_workspace(
    workspace_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    return {"workspace": workspace_response(workspace)}


@router.patch("/{workspace_id}", response_model=WorkspaceResponse, operation_id="update_workspace")
async def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdateRequest,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await services_of(request).workspaces.update(
        context.learner_id, workspace_id, body.model_dump(exclude_unset=True)
    )
    return {"workspace": workspace_response(workspace)}
