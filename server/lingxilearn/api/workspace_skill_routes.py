"""Workspace API routes split by resource family."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ..application.workspace_errors import WorkspaceDomainError
from ..contracts.rest_models import (
    SkillCreateRequest,
    SkillCreateResponse,
    SkillUpdateRequest,
    SkillUpdateResponse,
    SuccessResponse,
)
from ..learner import LearnerContext
from .dependencies import current_learner_context, services_of
from .mappers.skills import skill_response as _skill_public

router = APIRouter(prefix="/api")


@router.post("/skills", response_model=SkillCreateResponse)
async def create_skill(
    body: SkillCreateRequest,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        row = await services_of(request).skills.create(
            context.learner_id, body.model_dump(exclude_unset=True)
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    public = _skill_public(row)
    return {"skill": public}


@router.patch("/skills/{skill_id}", response_model=SkillUpdateResponse)
async def update_skill(
    skill_id: str,
    body: SkillUpdateRequest,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        row = await services_of(request).skills.update(
            context.learner_id, skill_id, body.model_dump(exclude_unset=True)
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    public = _skill_public(row)
    return {"skill": public}


@router.delete("/skills/{skill_id}", response_model=SuccessResponse)
async def delete_skill(
    skill_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    try:
        await services_of(request).skills.delete(context.learner_id, skill_id)
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return {"success": True}
