"""REST + SSE surface.

The SSE endpoint is the interesting one: it serves from the persisted event log
rather than from the live run, honours ``Last-Event-ID``, sends heartbeat
comments while idle, and closes only when the session actually finishes.
Pausing for the learner keeps the connection open, because the session is still
alive and will emit again the moment they answer.  A learner who reloads
mid-lesson reconnects and catches up; nothing is lost because nothing was only
ever in flight.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ..application import agent_task_create_payload_digest
from ..contracts.rest_models import (
    AckDeliveryResponse,
    AgentEvidenceResponse,
    AgentMessageResponse,
    AgentTaskCancelResponse,
    AgentTaskCreateResponse,
    AgentTaskDeleteResponse,
    AgentTaskEventsResponse,
    AgentTaskForkResponse,
    AgentTaskListResponse,
    AgentTaskMetaResponse,
    AgentTaskRestoreResponse,
    AgentTaskSnapshotResponse,
    AnswerResponse,
    ConfirmWorkResponse,
    ContextResponse,
    CopilotToolPermissionResponse,
    InteractionAnswerResponse,
    LearningProfileResponse,
    MasteryResponse,
    PreferencesResponse,
    ProfileChangeResponse,
    QuizSubmissionResponse,
    SessionCreateResponse,
    SessionSnapshotResponse,
)
from ..learner import LearnerContext
from .dependencies import current_learner_context, not_found, services_of

router = APIRouter(prefix="/api")

TERMINAL = {"done", "failed", "cancelled"}

@router.post("/copilot/tool-permission", response_model=CopilotToolPermissionResponse)
async def copilot_tool_permission(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Use Sim's native permission card contract for agent schedule proposals."""

    decisions = body.get("decisions") if isinstance(body, dict) else None
    if (
        not isinstance(decisions, list)
        or not decisions
        or any(not isinstance(item, dict) for item in decisions)
    ):
        raise HTTPException(status_code=422, detail="At least one decision is required")
    services = services_of(request)
    try:
        results = await services.agent_tasks.decide_schedule_permission(
            learner_id=context.learner_id,
            decisions=decisions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "results": results}


async def _validated_task_context(
    request: Request,
    context: LearnerContext,
    resource_refs: list[dict[str, Any]],
    skill_ids: list[str],
) -> list[dict[str, Any]]:
    """Transport mapping for task-resource validation; logic lives in the service."""

    services = services_of(request)
    try:
        return await services.agent_tasks.validate_task_resources(
            context.learner_id, resource_refs, skill_ids
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise not_found() from exc


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


class CreateAgentTask(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt: str = Field(min_length=1, max_length=4000)
    attachments: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    skill_ids: list[str] = Field(default_factory=list, max_length=50)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=192)


class AgentTaskMetadataPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=4000)
    is_pinned: bool | None = None
    is_unread: bool | None = None
    resources: list[dict[str, Any]] | None = None


class AgentMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str = Field(min_length=1, max_length=4000)
    attachments: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    skill_ids: list[str] = Field(default_factory=list, max_length=50)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=192)


class AgentInteractionAnswerRequest(BaseModel):
    """Structured answers for one blocking interaction (issue #18 §10.4)."""

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


@router.post(
    "/sessions/{session_id}/answer", status_code=202, response_model=AnswerResponse
)
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


# --------------------------------------------------------------------------
# Intent-driven Agent Tasks
# --------------------------------------------------------------------------


@router.post("/agent-tasks", status_code=202, response_model=AgentTaskCreateResponse)
async def create_agent_task(
    body: CreateAgentTask,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    services = services_of(request)
    task_id = f"t-{uuid.uuid4().hex[:20]}"
    payload_digest = agent_task_create_payload_digest(
        prompt=body.prompt,
        attachments=body.attachments,
        resource_refs=body.resource_refs,
        skill_ids=body.skill_ids,
    )
    if body.idempotency_key:
        existing = await services.agent_tasks.get_agent_task_by_create_idempotency_key(
            context.learner_id, body.idempotency_key
        )
        if existing is not None:
            if existing.create_payload_digest != payload_digest:
                raise HTTPException(status_code=409, detail="idempotency_key_reused")
            result = {"id": existing.id, "status": existing.status}
            if existing.error:
                result["error"] = existing.error
            return result
    try:
        task_resources = await _validated_task_context(
            request, context, body.resource_refs, body.skill_ids
        )
        created = await services.agent_tasks.create_agent_task(
            task_id=task_id,
            learner_id=context.learner_id,
            prompt=body.prompt,
            attachments=body.attachments,
            resources=task_resources,
            idempotency_key=body.idempotency_key,
            create_payload_digest=payload_digest,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=409 if detail == "idempotency_key_reused" else 400,
            detail=detail,
        ) from exc
    return created


@router.get("/agent-tasks", response_model=AgentTaskListResponse)
async def list_agent_tasks(
    request: Request,
    scope: str = Query("active"),
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    if scope not in {"active", "archived"}:
        raise HTTPException(status_code=400, detail="invalid_scope")
    return {"tasks": await services_of(request).agent_tasks.list_agent_tasks(context.learner_id, scope=scope)}


@router.get("/agent-tasks/{task_id}", response_model=AgentTaskSnapshotResponse)
async def get_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    services = services_of(request)
    try:
        return await services.agent_tasks.agent_task_snapshot(task_id, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post(
    "/agent-tasks/{task_id}/messages", status_code=202, response_model=AgentMessageResponse
)
async def post_agent_message(
    task_id: str,
    body: AgentMessage,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    services = services_of(request)
    try:
        task_resources = await _validated_task_context(
            request, context, body.resource_refs, body.skill_ids
        )
        if task_resources:
            await services.agent_tasks.update_agent_task(task_id, context.learner_id, resources=task_resources)
        result = await services.agent_tasks.agent_message(
            task_id,
            body.message,
            attachments=body.attachments,
            learner_id=context.learner_id,
            idempotency_key=body.idempotency_key,
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "accepted",
        "turnId": str((result or {}).get("turnId") or ""),
    }


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
    """Answer a blocking interaction; the server resumes the paused checkpoint."""

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
        # Reusing a key with a different answer is a conflict, not a bad
        # request — same semantics as the create-task idempotency contract.
        detail = str(exc)
        raise HTTPException(
            status_code=409 if detail == "idempotency_key_reused" else 400,
            detail=detail,
        ) from exc


@router.patch("/agent-tasks/{task_id}", response_model=AgentTaskMetaResponse)
async def patch_agent_task(
    task_id: str,
    body: AgentTaskMetadataPatch,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.update_agent_task(
            task_id,
            context.learner_id,
            title=body.title,
            is_pinned=body.is_pinned,
            is_unread=body.is_unread,
            resources=body.resources,
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/agent-tasks/{task_id}", response_model=AgentTaskDeleteResponse)
async def delete_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.delete_agent_task(task_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/agent-tasks/{task_id}/restore", response_model=AgentTaskRestoreResponse)
async def restore_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.restore_agent_task(task_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/agent-tasks/{task_id}/fork", status_code=202, response_model=AgentTaskForkResponse)
async def fork_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.fork_agent_task(task_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/agent-tasks/{task_id}/cancel", response_model=AgentTaskCancelResponse)
async def cancel_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await services_of(request).agent_tasks.cancel_agent_task(task_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


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
    services = services_of(request)
    try:
        return await services.agent_tasks.submit_agent_quiz(
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


@router.get("/agent-tasks/{task_id}/events", response_model=AgentTaskEventsResponse)
async def stream_agent_events(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> Any:
    services = services_of(request)
    try:
        await services.agent_tasks.agent_task_snapshot(task_id, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc

    # V1 clients (protocol=v1) read the versioned Mothership stream; everyone
    # else keeps the historical V0 event vocabulary, unchanged.
    protocol_version = 1 if request.query_params.get("protocol") == "v1" else 0

    # Both SSE replay and JSON catch-up use the durable AgentTaskEvent row
    # sequence.  This is intentionally different from the protocol envelope's
    # own `seq`, because V0 and V1 rows share one database event log.
    header = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    try:
        cursor = int(header) if header else 0
    except ValueError:
        cursor = 0

    # History hydration is also the fallback catch-up transport for clients
    # behind proxies that buffer a long-lived SSE response.  Respect the same
    # cursor so polling transfers only rows the client has not consumed.
    if request.query_params.get("format") == "json":
        events = await services.agent_events.events_after(
            task_id,
            context.learner_id,
            cursor,
            protocol_version=protocol_version,
        )
        return Response(
            content=json.dumps({"events": events}, ensure_ascii=False, separators=(",", ":")),
            media_type="application/json",
        )
    heartbeat = services.settings.sse_heartbeat_seconds

    async def generate():  # noqa: ANN202
        nonlocal cursor
        waiter = services.agent_events.waiter(task_id)
        while True:
            if await request.is_disconnected():
                return
            events = await services.agent_events.events_after(
                task_id, context.learner_id, cursor, protocol_version=protocol_version
            )
            for event in events:
                cursor = event["sequence"]
                payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"

            current = await services.agent_tasks.agent_task_snapshot(task_id, learner_id=context.learner_id)
            # The stream ends only when the *thread* is terminal, not when a
            # single turn delivers — a long-lived chat keeps its SSE channel
            # across turns (issue #18 §15.1).
            if current.get("threadStatus") == "cancelled":
                tail = await services.agent_events.events_after(
                    task_id, context.learner_id, cursor, protocol_version=protocol_version
                )
                for event in tail:
                    cursor = event["sequence"]
                    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                    yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"
                yield (
                    "event: stream.end\ndata: "
                    + json.dumps({"status": current["status"]}, ensure_ascii=False)
                    + "\n\n"
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


@router.patch(
    "/me/learning-profile/{knowledge_point_id}", response_model=ProfileChangeResponse
)
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


@router.get("/agent-tasks/{task_id}/evidence", response_model=AgentEvidenceResponse)
async def agent_task_evidence(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """The evidence this task produced, for drilling into a node."""

    services = services_of(request)
    if await services.agent_tasks.get_task_record(task_id, context.learner_id) is None:
        raise not_found()
    return {"evidence": await services.agent_events.evidence_for_task(task_id)}


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
            events = await services.conversation.events_after(session_id, context.learner_id, cursor)
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
