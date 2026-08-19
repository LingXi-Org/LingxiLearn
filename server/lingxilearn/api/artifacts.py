"""HTTP boundary for learner-owned attachments and agent artifacts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from ..contracts.rest_models import AttachmentUploadResponse
from ..learner import LearnerContext
from .dependencies import current_learner_context, not_found, services_of

router = APIRouter(prefix="/api")


class AgentAttachmentUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(default="application/octet-stream", max_length=128)
    size: int = Field(ge=0, le=20 * 1024 * 1024)
    data: str = Field(min_length=1)


@router.post("/attachments", status_code=201, response_model=AttachmentUploadResponse)
async def upload_attachment(
    body: AgentAttachmentUpload,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).artifacts.upload_attachment(
            learner_id=context.learner_id,
            filename=body.filename,
            media_type=body.media_type,
            size=body.size,
            encoded=body.data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/attachments/{learner_id}/{attachment_id}")
async def get_attachment(
    learner_id: str,
    attachment_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> FileResponse:
    if learner_id != context.learner_id:
        raise not_found()
    try:
        path, media_type, filename = services_of(request).artifacts.attachment_path(
            learner_id, attachment_id
        )
    except KeyError as exc:
        raise not_found() from exc
    return FileResponse(path, media_type=media_type, filename=filename)


@router.get("/agent-tasks/{task_id}/artifacts/{kind}")
async def get_agent_artifact(
    task_id: str,
    kind: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> Response:
    services = services_of(request)
    try:
        content, media_type, filename = await services.artifacts.agent_artifact(
            task_id, kind, learner_id=context.learner_id
        )
    except KeyError as exc:
        raise not_found() from exc
    headers = {"Content-Disposition": f'inline; filename="{filename}"'}
    if kind == "visual":
        headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "img-src data:; font-src data:; connect-src 'none'; frame-src 'none'; "
            "base-uri 'none'; form-action 'none'"
        )
        headers["X-Content-Type-Options"] = "nosniff"
    return Response(content=content, media_type=media_type, headers=headers)
