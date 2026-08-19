"""Public AgentTask event history, streaming, and evidence routes.

The stream is backed by the durable event log, so reconnects can resume from
``Last-Event-ID`` without depending on an in-process run.  A long-lived thread
stays connected between turns and closes only when it is cancelled.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, StreamingResponse

from ..contracts.rest_models import AgentEvidenceResponse, AgentTaskEventsResponse
from ..learner import LearnerContext
from .dependencies import current_learner_context, not_found, services_of

router = APIRouter(prefix="/api")


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
        replay_protocol = await services.agent_events.replay_protocol(
            task_id, context.learner_id
        )
        events = await services.agent_events.events_after(
            task_id,
            context.learner_id,
            cursor,
            protocol_version=protocol_version,
        )
        return Response(
            content=json.dumps(
                {
                    "events": events,
                    "protocol": "v1" if replay_protocol == 1 else "legacy-v0",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
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

            current = await services.agent_tasks.agent_task_snapshot(
                task_id, learner_id=context.learner_id
            )
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
