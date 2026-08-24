"""Workspace API routes split by resource family."""

from fastapi import APIRouter

from ..application.workspace_errors import WorkspaceDomainError
from .workspace_route_shared import (
    Any,
    Depends,
    HTTPException,
    LearnerContext,
    Request,
    SkillCreateResponse,
    SkillUpdateResponse,
    SuccessResponse,
    _skill_public,
    current_learner_context,
    services_of,
)

router = APIRouter(prefix="/api")


@router.post("/skills", response_model=SkillCreateResponse)
async def create_skill(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        row = await services_of(request).skills.create(context.learner_id, body)
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    public = _skill_public(row)
    return {"skills": [public], "skill": public, "data": public}


@router.patch("/skills/{skill_id}", response_model=SkillUpdateResponse)
async def update_skill(
    skill_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        row = await services_of(request).skills.update(context.learner_id, skill_id, body)
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    public = _skill_public(row)
    return {"skill": public, "data": public}


@router.delete("/skills/{skill_id}", response_model=SuccessResponse)
async def delete_skill(
    skill_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    try:
        await services_of(request).skills.delete(context.learner_id, skill_id)
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return {"success": True}


# Logs -----------------------------------------------------------------------
