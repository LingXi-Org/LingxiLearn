"""Canonical Workspace Artifact HTTP endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response

from ..application.workspace_errors import WorkspaceDomainError
from ..contracts.rest_models import (
    ArtifactListResponse,
    ArtifactRenameRequest,
    ArtifactResponse,
    SuccessResponse,
)
from ..learner import LearnerContext
from .dependencies import current_learner_context, services_of
from .mappers.artifacts import artifact_response
from .workspace_route_shared import _workspace_for_id

router = APIRouter(prefix="/api/workspaces/{workspace_id}/artifacts", tags=["Artifact"])


def _raise_http(error: WorkspaceDomainError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.code) from error


@router.get("", response_model=ArtifactListResponse, operation_id="list_artifacts")
async def list_artifacts(
    workspace_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    artifacts = await services_of(request).workspace_artifacts.list(workspace.id)
    return {"artifacts": [artifact_response(item) for item in artifacts]}


@router.post(
    "",
    response_model=ArtifactResponse,
    operation_id="create_artifact",
    status_code=status.HTTP_201_CREATED,
)
async def create_artifact(
    workspace_id: str,
    request: Request,
    file: UploadFile = File(...),
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        artifact = await services_of(request).workspace_artifacts.create(
            workspace_id=workspace.id,
            learner_id=context.learner_id,
            name=file.filename or "artifact",
            mime_type=file.content_type,
            content=await file.read(),
        )
    except WorkspaceDomainError as error:
        _raise_http(error)
    return {"artifact": artifact_response(artifact)}


@router.get("/{artifact_id}", response_model=ArtifactResponse, operation_id="get_artifact")
async def get_artifact(
    workspace_id: str,
    artifact_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        artifact = await services_of(request).workspace_artifacts.require(workspace.id, artifact_id)
    except WorkspaceDomainError as error:
        _raise_http(error)
    return {"artifact": artifact_response(artifact)}


@router.patch("/{artifact_id}", response_model=ArtifactResponse, operation_id="rename_artifact")
async def rename_artifact(
    workspace_id: str,
    artifact_id: str,
    body: ArtifactRenameRequest,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        artifact = await services_of(request).workspace_artifacts.rename(
            workspace.id, artifact_id, body.name
        )
    except WorkspaceDomainError as error:
        _raise_http(error)
    return {"artifact": artifact_response(artifact)}


@router.delete("/{artifact_id}", response_model=SuccessResponse, operation_id="delete_artifact")
async def delete_artifact(
    workspace_id: str,
    artifact_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, bool]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        await services_of(request).workspace_artifacts.delete(
            workspace.id, artifact_id, context.learner_id
        )
    except WorkspaceDomainError as error:
        _raise_http(error)
    return {"success": True}


@router.get("/{artifact_id}/content", operation_id="download_artifact")
async def download_artifact(
    workspace_id: str,
    artifact_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> Response:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        artifact, content = await services_of(request).workspace_artifacts.read(
            workspace.id, artifact_id, context.learner_id
        )
    except WorkspaceDomainError as error:
        _raise_http(error)
    return Response(
        content=content,
        media_type=artifact.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.name}"'},
    )


@router.put(
    "/{artifact_id}/content",
    response_model=ArtifactResponse,
    operation_id="replace_artifact_content",
)
async def replace_artifact_content(
    workspace_id: str,
    artifact_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    workspace = await _workspace_for_id(request, workspace_id, context)
    try:
        artifact = await services_of(request).workspace_artifacts.replace(
            workspace_id=workspace.id,
            artifact_id=artifact_id,
            learner_id=context.learner_id,
            content=await request.body(),
        )
    except WorkspaceDomainError as error:
        _raise_http(error)
    return {"artifact": artifact_response(artifact)}
