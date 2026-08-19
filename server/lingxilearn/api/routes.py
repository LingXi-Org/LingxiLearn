"""Legacy learning-session REST and SSE surface."""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ..contracts.rest_models import (
    AgentTaskCreateResponse,
    AnswerResponse,
    ContextResponse,
    LearningProfileResponse,
    MasteryResponse,
    PreferencesResponse,
    ProfileChangeResponse,
    SessionCreateResponse,
    SessionSnapshotResponse,
)
from ..learner import LearnerContext
from .dependencies import current_learner_context, not_found, services_of

router = APIRouter(prefix="/api")

TERMINAL = {"done", "failed", "cancelled"}

# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------


class CreateSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: str
    pack_id: str


class AnswerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: Any


@router.post("/sessions", status_code=201, response_model=SessionCreateResponse)
async def create_session(
    body: CreateSession,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    services = services_of(request)
    session_id = f"s-{uuid.uuid4().hex[:16]}"
    try:
        created = await services.conversation.create_session(
            session_id=session_id,
            learner_id=context.learner_id,
            pack_id=body.pack_id,
            mission_id=body.mission_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return created


@router.get("/sessions/{session_id}", response_model=SessionSnapshotResponse)
async def get_session(
    session_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    services = services_of(request)
    if await services.conversation.get_session_record(session_id, context.learner_id) is None:
        raise not_found()
    try:
        return await services.conversation.snapshot(session_id, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/sessions/{session_id}/answer", status_code=202, response_model=AnswerResponse)
async def answer(
    session_id: str,
    body: AnswerBody,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    services = services_of(request)
    record = await services.conversation.get_session_record(session_id, context.learner_id)
    if record is None:
        raise not_found()
    if record.status == "running":
        raise HTTPException(status_code=409, detail="run_in_progress")
    if record.status in TERMINAL:
        raise HTTPException(status_code=409, detail=f"session_{record.status}")
    await services.conversation.answer(session_id, body.answer, learner_id=context.learner_id)
    return {"status": "accepted"}


@router.get("/sessions/{session_id}/report", response_model=dict[str, Any])
async def get_report(
    session_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    services = services_of(request)
    if await services.conversation.get_session_record(session_id, context.learner_id) is None:
        raise not_found()
    stored = await services.conversation.get_report(session_id, context.learner_id)
    if stored is not None:
        return stored
    try:
        snapshot = await services.conversation.snapshot(session_id, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc
    if not snapshot.get("report"):
        raise HTTPException(status_code=404, detail="report_not_ready")
    return snapshot["report"]


@router.get("/sessions/{session_id}/artifact/{artifact_id}")
async def download_artifact(
    session_id: str,
    artifact_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> FileResponse:
    """Hand over the raw capture so the learner can audit us in Wireshark."""
    services = services_of(request)
    record = await services.conversation.get_session_record(session_id, context.learner_id)
    if record is None:
        raise not_found()
    pack = services.packs.get(record.pack_id)
    mission = pack.missions.get(record.mission_id) if pack else None
    artifact = mission.artifacts.get(artifact_id) if mission else None
    if artifact is None or not Path(artifact.path).exists():  # noqa: ASYNC240
        raise HTTPException(status_code=404, detail="unknown_artifact")
    return FileResponse(
        artifact.path, media_type="application/vnd.tcpdump.pcap", filename=Path(artifact.path).name
    )


@router.get("/me/context", response_model=ContextResponse)
async def me_context(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    return context.public_dict()


class ProfileOverride(BaseModel):
    """A learner correcting their own record. Not an agent write."""

    model_config = ConfigDict(extra="forbid")

    override: bool = True
    mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    learning_state: str | None = Field(default=None, max_length=48)
    progress: float | None = Field(default=None, ge=0.0, le=1.0)


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


# --------------------------------------------------------------------------
# SSE
# --------------------------------------------------------------------------


@router.get("/sessions/{session_id}/events")
async def stream_events(
    session_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    services = services_of(request)
    record = await services.conversation.get_session_record(session_id, context.learner_id)
    if record is None:
        raise not_found()

    header = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    try:
        cursor = int(header) if header else 0
    except ValueError:
        cursor = 0

    heartbeat = services.settings.sse_heartbeat_seconds

    async def generate():  # noqa: ANN202
        nonlocal cursor
        waiter = services.conversation.waiter(session_id)
        while True:
            if await request.is_disconnected():
                return
            events = await services.conversation.events_after(
                session_id, context.learner_id, cursor
            )
            for event in events:
                cursor = event["sequence"]
                payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"

            current = await services.conversation.get_session_record(session_id, context.learner_id)
            status = current.status if current else "failed"
            # Only a terminal status closes the stream. `awaiting_learner` means
            # the session is alive and will emit again the moment the learner
            # answers, so the connection is held open with heartbeats instead.
            if status in TERMINAL:
                # Drain anything appended between the query and the status read.
                tail = await services.conversation.events_after(
                    session_id, context.learner_id, cursor
                )
                for event in tail:
                    cursor = event["sequence"]
                    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                    yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"
                yield (
                    "event: stream.end\n"
                    f"data: {json.dumps({'status': status}, ensure_ascii=False)}\n\n"
                )
                return

            if not events:
                yield ": heartbeat\n\n"
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(waiter.wait(), timeout=heartbeat)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
