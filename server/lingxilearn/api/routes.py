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

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from lingxi_identity import Principal  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field

from ..auth import get_principal
from ..learner import LearnerContext
from ..service import Service
from ..tools.net import sim

router = APIRouter(prefix="/api")

TERMINAL = {"done", "failed", "cancelled"}
AGENT_TERMINAL = {"completed", "partial", "failed"}


def service_of(request: Request) -> Service:
    svc: Service | None = getattr(request.app.state, "service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="service_unavailable")
    return svc


async def current_learner_context(
    request: Request, principal: Principal = Depends(get_principal)
) -> LearnerContext:
    svc = service_of(request)
    try:
        return await svc.learners.get_learner_context(principal)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="invalid_identity") from exc


def not_found() -> HTTPException:
    """Use one response for missing and not-owned persistent resources."""

    return HTTPException(status_code=404, detail="resource_not_found")


# --------------------------------------------------------------------------
# Health & catalogue
# --------------------------------------------------------------------------


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    svc = service_of(request)
    try:
        db_ok = await svc.db.ping()
    except Exception:  # noqa: BLE001 - health must answer even when the DB is down
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "brain": svc.brain.name if svc.brain else "unconfigured",
        "agent": {
            "configured": svc.settings.agents_configured,
            "model": svc.settings.agent_model,
        },
        "packs": sorted(svc.packs),
        "tools": len(svc.registry.specs),
    }


@router.get("/packs")
async def list_packs(request: Request) -> dict[str, Any]:
    svc = service_of(request)
    return {
        "packs": [
            {
                "id": pack.id,
                "title": pack.title,
                "version": pack.version,
                "description": pack.description,
                "concepts": [
                    {"id": c.id, "title": c.title, "summary": c.summary, "requires": c.requires}
                    for c in pack.concepts.values()
                ],
                "missions": [
                    {
                        "id": m.id,
                        "title": m.title,
                        "subtitle": m.subtitle,
                        "summary": m.summary,
                        "why_not_chat": m.why_not_chat,
                        "concepts": list(m.concepts),
                        "estimated_minutes": m.estimated_minutes,
                        "steps": len(m.steps),
                    }
                    for m in pack.missions.values()
                ],
            }
            for pack in svc.packs.values()
        ]
    }


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------


class CreateSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: str
    pack_id: str = "computer-networks"


class AnswerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: Any


class CreateAgentTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=4000)


@router.post("/sessions", status_code=201)
async def create_session(
    body: CreateSession,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    session_id = f"s-{uuid.uuid4().hex[:16]}"
    try:
        created = await svc.create_session(
            session_id=session_id,
            learner_id=context.learner_id,
            pack_id=body.pack_id,
            mission_id=body.mission_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return created


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    if await svc.repo.get_session_for_learner(session_id, context.learner_id) is None:
        raise not_found()
    try:
        return await svc.snapshot(session_id, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/sessions/{session_id}/answer", status_code=202)
async def answer(
    session_id: str,
    body: AnswerBody,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    record = await svc.repo.get_session_for_learner(session_id, context.learner_id)
    if record is None:
        raise not_found()
    if record.status == "running":
        raise HTTPException(status_code=409, detail="run_in_progress")
    if record.status in TERMINAL:
        raise HTTPException(status_code=409, detail=f"session_{record.status}")
    await svc.answer(session_id, body.answer, learner_id=context.learner_id)
    return {"status": "accepted"}


# --------------------------------------------------------------------------
# Intent-driven Agent Tasks
# --------------------------------------------------------------------------


@router.post("/agent-tasks", status_code=202)
async def create_agent_task(
    body: CreateAgentTask,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    task_id = f"t-{uuid.uuid4().hex[:20]}"
    try:
        created = await svc.create_agent_task(
            task_id=task_id,
            learner_id=context.learner_id,
            prompt=body.prompt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return created


@router.get("/agent-tasks/{task_id}")
async def get_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    try:
        return await svc.agent_task_snapshot(task_id, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.get("/agent-tasks/{task_id}/artifacts/{kind}")
async def get_agent_artifact(
    task_id: str,
    kind: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> Response:
    svc = service_of(request)
    try:
        content, media_type, filename = await svc.agent_artifact(
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


@router.get("/agent-tasks/{task_id}/events")
async def stream_agent_events(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    svc = service_of(request)
    try:
        await svc.agent_task_snapshot(task_id, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc

    header = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    try:
        cursor = int(header) if header else 0
    except ValueError:
        cursor = 0
    heartbeat = svc.settings.sse_heartbeat_seconds

    async def generate():  # noqa: ANN202
        nonlocal cursor
        waiter = svc.agent_waiter(task_id)
        while True:
            if await request.is_disconnected():
                return
            events = await svc.repo.agent_events_after_for_learner(
                task_id, context.learner_id, cursor
            )
            for event in events:
                cursor = event["sequence"]
                payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"

            current = await svc.agent_task_snapshot(task_id, learner_id=context.learner_id)
            if current["status"] in AGENT_TERMINAL:
                tail = await svc.repo.agent_events_after_for_learner(
                    task_id, context.learner_id, cursor
                )
                for event in tail:
                    cursor = event["sequence"]
                    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                    yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"
                yield "event: stream.end\ndata: " + json.dumps(
                    {"status": current["status"]}, ensure_ascii=False
                ) + "\n\n"
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


@router.get("/sessions/{session_id}/report")
async def get_report(
    session_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    if await svc.repo.get_session_for_learner(session_id, context.learner_id) is None:
        raise not_found()
    stored = await svc.repo.get_report_for_learner(session_id, context.learner_id)
    if stored is not None:
        return stored
    try:
        snapshot = await svc.snapshot(session_id, learner_id=context.learner_id)
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
    svc = service_of(request)
    record = await svc.repo.get_session_for_learner(session_id, context.learner_id)
    if record is None:
        raise not_found()
    pack = svc.packs.get(record.pack_id)
    mission = pack.missions.get(record.mission_id) if pack else None
    artifact = mission.artifacts.get(artifact_id) if mission else None
    if artifact is None or not Path(artifact.path).exists():  # noqa: ASYNC240
        raise HTTPException(status_code=404, detail="unknown_artifact")
    return FileResponse(
        artifact.path, media_type="application/vnd.tcpdump.pcap", filename=Path(artifact.path).name
    )


@router.get("/me/context")
async def me_context(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    return context.public_dict()


@router.get("/me/mastery")
async def me_mastery(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    return {
        "mastery": await svc.learners.get_mastery(context),
        "sessions": await svc.repo.list_sessions(context.learner_id),
    }


@router.get("/me/preferences")
async def get_preferences(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    return {"preferences": context.preferences}


@router.patch("/me/preferences")
async def patch_preferences(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    try:
        preference = await svc.learners.update_preference(context, body)
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
    svc = service_of(request)
    record = await svc.repo.get_session_for_learner(session_id, context.learner_id)
    if record is None:
        raise not_found()

    header = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    try:
        cursor = int(header) if header else 0
    except ValueError:
        cursor = 0

    heartbeat = svc.settings.sse_heartbeat_seconds

    async def generate():  # noqa: ANN202
        nonlocal cursor
        waiter = svc.waiter(session_id)
        while True:
            if await request.is_disconnected():
                return
            events = await svc.repo.events_after_for_learner(
                session_id, context.learner_id, cursor
            )
            for event in events:
                cursor = event["sequence"]
                payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"

            current = await svc.repo.get_session_for_learner(
                session_id, context.learner_id
            )
            status = current.status if current else "failed"
            # Only a terminal status closes the stream. `awaiting_learner` means
            # the session is alive and will emit again the moment the learner
            # answers, so the connection is held open with heartbeats instead.
            if status in TERMINAL:
                # Drain anything appended between the query and the status read.
                tail = await svc.repo.events_after_for_learner(
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


# --------------------------------------------------------------------------
# Interactive simulator
# --------------------------------------------------------------------------


class SimInit(BaseModel):
    scenario: str = "single-loss"
    seed: int = 7


class SimStep(BaseModel):
    state: dict[str, Any]
    action: dict[str, Any]


@router.get("/sim/scenarios")
async def sim_scenarios() -> dict[str, Any]:
    return {
        "scenarios": [
            {"id": key, "title": spec["title"], "brief": spec["brief"],
             "segments": spec["segments"], "window": spec["window"],
             "loss_percent": spec["loss_percent"]}
            for key, spec in sim.SCENARIOS.items()
        ]
    }


@router.post("/sim/init")
async def sim_initialize(body: SimInit) -> dict[str, Any]:
    try:
        return sim.init(body.scenario, body.seed)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown_scenario") from exc


@router.post("/sim/step")
async def sim_advance(body: SimStep) -> dict[str, Any]:
    """Advance the console one tick.

    Purely for interactivity — grading never trusts this. The learner's action
    log is replayed server-side from the seed when the step is submitted.
    """
    if body.state.get("scenario") not in sim.SCENARIOS:
        raise HTTPException(status_code=400, detail="bad_state")
    return sim.step(body.state, body.action)
