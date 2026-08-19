"""Learner-owned context, profile, mastery, and preference endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ..contracts.rest_models import (
    AgentTaskCreateResponse,
    ContextResponse,
    LearningProfileResponse,
    MasteryResponse,
    PreferencesResponse,
    ProfileChangeResponse,
)
from ..learner import LearnerContext
from .dependencies import current_learner_context, not_found, services_of

router = APIRouter(prefix="/api")


class ProfileOverride(BaseModel):
    """A learner correcting their own record. Not an agent write."""

    model_config = ConfigDict(extra="forbid")

    override: bool = True
    mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    learning_state: str | None = Field(default=None, max_length=48)
    progress: float | None = Field(default=None, ge=0.0, le=1.0)


@router.get("/me/context", response_model=ContextResponse)
async def me_context(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    return context.public_dict()


@router.get("/me/learning-profile", response_model=LearningProfileResponse)
async def learning_profile(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """The learner's study record: one row per knowledge point.

    ``next_step`` on each row is an action the learner can take, not a
    description — POST it back to act on it.
    """

    services = services_of(request)
    rows = await services.learner_state.profile_for(context.learner_id)
    return {
        "profile": rows,
        "columns": {
            "learner": [
                "knowledge_point",
                "mastery",
                "learning_state",
                "progress",
                "my_questions",
                "recent_performance",
                "last_studied_at",
                "review_due_at",
                "next_step",
            ],
            "system": [
                "confidence",
                "evidence_count",
                "misconceptions",
                "prerequisites",
                "difficulty",
                "review_priority",
                "stability",
                "source_agent",
                "revision",
                "override_flag",
            ],
        },
    }


@router.post(
    "/me/learning-profile/{knowledge_point_id}/next-step",
    status_code=202,
    response_model=AgentTaskCreateResponse,
)
async def take_next_step(
    knowledge_point_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Act on a row's ``next_step`` by pushing it onto the goal stack.

    The runtime still decides what to run: this states an intent, exactly like
    typing it would, and the orchestrator ranks it against everything else.
    """

    services = services_of(request)
    row = await services.learner_state.profile_point(context.learner_id, knowledge_point_id)
    if row is None:
        raise not_found()
    step = dict(row.get("next_step") or {})
    if not step.get("capability"):
        raise HTTPException(status_code=409, detail="no_next_step")

    task_id = f"task-{uuid.uuid4().hex}"
    label = step.get("label") or row.get("knowledge_point") or knowledge_point_id
    return await services.agent_tasks.create_agent_task(
        task_id=task_id,
        learner_id=context.learner_id,
        prompt=str(label),
    )


@router.patch("/me/learning-profile/{knowledge_point_id}", response_model=ProfileChangeResponse)
async def override_learning_profile(
    knowledge_point_id: str,
    body: ProfileOverride,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Let a learner correct their own profile row.

    Sets ``override_flag`` so the state updater stops overwriting the fields the
    learner owns, while still counting new evidence against them.
    """

    services = services_of(request)
    fields = {
        name: value
        for name, value in (
            ("mastery", body.mastery),
            ("learning_state", body.learning_state),
            ("progress", body.progress),
        )
        if value is not None
    }
    try:
        change = await services.learner_state.override_profile(
            learner_id=context.learner_id,
            knowledge_point_id=knowledge_point_id,
            enabled=body.override,
            fields=fields,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if change is None:
        raise not_found()
    return change.to_dict()


@router.get("/me/mastery", response_model=MasteryResponse)
async def me_mastery(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    services = services_of(request)
    return {
        "mastery": await services.learners.get_mastery(context),
        "sessions": await services.conversation.list_sessions(context.learner_id),
    }


@router.get("/me/preferences", response_model=PreferencesResponse)
async def get_preferences(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    return {"preferences": context.preferences}


@router.patch("/me/preferences", response_model=PreferencesResponse)
async def patch_preferences(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    services = services_of(request)
    try:
        preference = await services.learners.update_preference(context, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"preferences": dict(preference.payload or {})}
