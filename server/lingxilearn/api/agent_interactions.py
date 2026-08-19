"""Learner responses to blocking agent interactions.

This boundary owns human-in-the-loop commands.  The historical Copilot URL is
kept as a transport adapter only; schedule permissions use Lingxi-native
proposal terminology at the canonical endpoint.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ..contracts.rest_models import (
    AckDeliveryResponse,
    ConfirmWorkResponse,
    InteractionAnswerResponse,
    QuizSubmissionResponse,
    SchedulePermissionResponse,
)
from ..learner import LearnerContext
from .dependencies import current_learner_context, not_found, services_of

router = APIRouter(prefix="/api")


class AgentInteractionAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[dict[str, Any]] = Field(min_length=1, max_length=20)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=192)


class QuizSubmissionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: str = Field(min_length=1, max_length=128)
    answers: dict[str, Any]
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=192)


class AgentConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_item_id: str = Field(min_length=1, max_length=128)
    approve: bool
    payload_digest: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=192)


class SchedulePermissionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(alias="proposalId", min_length=1, max_length=255)
    decision: Literal["allow", "allow_chat", "always_allow", "skip"]


class SchedulePermissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[SchedulePermissionDecision] = Field(min_length=1, max_length=50)


class LegacyToolPermissionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_call_id: str = Field(alias="toolCallId", min_length=1, max_length=255)
    decision: Literal["allow", "allow_chat", "always_allow", "skip"]


class LegacyToolPermissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[LegacyToolPermissionDecision] = Field(min_length=1, max_length=50)


class LegacyToolPermissionResult(BaseModel):
    toolCallId: str
    decision: str
    applied: bool = False
    status: str = "unknown"
    scope: Any = None


class LegacyToolPermissionResponse(BaseModel):
    success: bool
    results: list[LegacyToolPermissionResult] = Field(default_factory=list)


async def _decide_schedule_permissions(
    request: Request,
    context: LearnerContext,
    decisions: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Shared application adapter for canonical and compatibility transports."""

    try:
        return await services_of(request).agent_tasks.decide_schedule_permission(
            learner_id=context.learner_id,
            decisions=decisions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/agent-interactions/schedule-permissions",
    response_model=SchedulePermissionResponse,
)
async def decide_schedule_permissions(
    body: SchedulePermissionRequest,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    decisions = [
        {"toolCallId": item.proposal_id, "decision": item.decision} for item in body.decisions
    ]
    results = await _decide_schedule_permissions(request, context, decisions)
    return {
        "success": True,
        "results": [
            {"proposalId": result.get("toolCallId"), **{k: v for k, v in result.items() if k != "toolCallId"}}
            for result in results
        ],
    }


@router.post(
    "/copilot/tool-permission",
    response_model=LegacyToolPermissionResponse,
    deprecated=True,
)
async def legacy_copilot_tool_permission(
    body: LegacyToolPermissionRequest,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Deprecated compatibility adapter; use schedule-permissions instead."""

    decisions = [
        {"toolCallId": item.tool_call_id, "decision": item.decision} for item in body.decisions
    ]
    results = await _decide_schedule_permissions(request, context, decisions)
    return {"success": True, "results": results}


@router.post(
    "/agent-tasks/{task_id}/interactions/{interaction_id}/answers",
    status_code=202,
    response_model=InteractionAnswerResponse,
)
async def answer_agent_interaction(
    task_id: str,
    interaction_id: str,
    body: AgentInteractionAnswerRequest,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.answer_agent_interaction(
            task_id,
            interaction_id,
            answers=body.answers,
            idempotency_key=body.idempotency_key or "",
            learner_id=context.learner_id,
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=409 if detail == "idempotency_key_reused" else 400,
            detail=detail,
        ) from exc


@router.post(
    "/agent-tasks/{task_id}/quiz-submissions",
    status_code=202,
    response_model=QuizSubmissionResponse,
)
async def submit_agent_quiz(
    task_id: str,
    body: QuizSubmissionBody,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.submit_agent_quiz(
            task_id,
            submission_id=body.submission_id,
            answers=body.answers,
            learner_id=context.learner_id,
            idempotency_key=body.idempotency_key,
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=409
            if detail in {"already_submitted", "task_not_waiting:awaiting_user"}
            or detail.startswith("task_not_waiting")
            else 400,
            detail=detail,
        ) from exc


@router.post(
    "/agent-tasks/{task_id}/confirmations", status_code=202, response_model=ConfirmWorkResponse
)
async def confirm_agent_work(
    task_id: str,
    body: AgentConfirmation,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.confirm_agent_work(
            task_id,
            work_item_id=body.work_item_id,
            approve=body.approve,
            payload_digest=body.payload_digest,
            idempotency_key=body.idempotency_key,
            learner_id=context.learner_id,
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/agent-tasks/{task_id}/delivery/{artifact}/ack", response_model=AckDeliveryResponse
)
async def ack_agent_delivery(
    task_id: str,
    artifact: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.ack_delivery(
            task_id, artifact, learner_id=context.learner_id, idempotency_key=idempotency_key
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
