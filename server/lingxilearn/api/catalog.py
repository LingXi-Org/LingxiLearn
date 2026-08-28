"""Read-only Skill Catalog endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..contracts.rest_models import (
    SkillRegistryResponse,
    SkillsResponse,
)
from ..learner import LearnerContext
from .dependencies import current_learner_context, services_of

router = APIRouter(prefix="/api")


@router.get("/skills", response_model=SkillsResponse)
async def list_skills(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Expose the native LingxiSkills catalogue to the workspace."""

    return {"skills": await services_of(request).skills.list_all(context.learner_id)}


@router.get("/skill-registry", response_model=SkillRegistryResponse)
async def skill_registry(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Expose the machine-readable capability registry used for planning."""

    return await services_of(request).skills.registry(context.learner_id)
