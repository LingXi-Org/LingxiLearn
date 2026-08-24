"""Workspace API routes split by resource family."""

from fastapi import APIRouter

from .workspace_route_shared import (
    UTC,
    AgentExecution,
    Any,
    Depends,
    LearnerContext,
    Request,
    StreamingResponse,
    _utc_datetime,
    _workspace_for_id,
    csv,
    current_learner_context,
    datetime,
    io,
    json,
    not_found,
    services_of,
    utcnow,
)

router = APIRouter(prefix="/api")


@router.get("/logs")
async def list_logs(
    request: Request,
    workspaceId: str = "lingxi",
    limit: int = 50,
    cursor: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _workspace_for_id(request, workspaceId, context)
    repository = services_of(request).logs
    tasks = await repository.list_tasks(context.learner_id, limit)
    execution_ids = [str(task.latest_execution_id) for task in tasks if task.latest_execution_id]
    executions: dict[str, AgentExecution] = {}
    if execution_ids:
        executions = await repository.executions_by_ids(context.learner_id, execution_ids)

    logs = [
        {
            "id": task.id,
            "executionId": task.latest_execution_id or task.id,
            "workflowId": "lingxi-agent",
            "workflowName": "LingxiGraph · Sim runtime",
            "deploymentVersionId": None,
            "deploymentVersion": None,
            "deploymentVersionName": None,
            "executionOrigin": None,
            "level": "error" if task.status == "failed" else "info",
            "status": "completed"
            if task.status in {"completed", "partial", "handed_off"}
            else task.status,
            "duration": str(
                max(
                    0,
                    int(
                        (
                            (_utc_datetime(execution.ended_at) or utcnow())
                            - (_utc_datetime(execution.started_at) or utcnow())
                        ).total_seconds()
                        * 1000
                    ),
                )
                if (execution := executions.get(str(task.latest_execution_id))) is not None
                else 0
            ),
            "trigger": "agent-task",
            "createdAt": (
                execution.started_at.isoformat()
                if execution is not None and execution.started_at
                else task.created_at.isoformat()
                if task.created_at
                else ""
            ),
            "workflow": {"id": "lingxi-agent", "name": "LingxiGraph · Sim runtime"},
            "jobTitle": task.title or None,
            "cost": {"total": 0},
            "pauseSummary": {
                "status": "awaiting_user" if task.status == "awaiting_user" else None,
                "total": 1 if task.status == "awaiting_user" else 0,
                "resumed": 0,
            },
            "hasPendingPause": task.status == "awaiting_user",
        }
        for task in tasks
    ]
    return {"success": True, "data": logs, "nextCursor": None}


@router.get("/logs/stats")
async def log_stats(
    request: Request,
    workspaceId: str = "lingxi",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _workspace_for_id(request, workspaceId, context)
    total, failed, executions = await services_of(request).logs.stats(context.learner_id)
    now_dt = datetime.now(UTC)
    normalized_rows = [
        (_utc_datetime(row.started_at), _utc_datetime(row.ended_at)) for row in executions
    ]
    durations = [
        max(0, int(((ended or now_dt) - started).total_seconds() * 1000))
        for started, ended in normalized_rows
        if started
    ]
    starts = [started for started, _ended in normalized_rows if started]
    ends = [ended or now_dt for started, ended in normalized_rows if started]
    now = now_dt.isoformat()
    return {
        "workflows": [],
        "aggregateSegments": [],
        "totalRuns": int(total),
        "totalErrors": int(failed),
        "avgLatency": int(sum(durations) / len(durations)) if durations else 0,
        "timeBounds": {
            "start": min(starts).isoformat() if starts else now,
            "end": max(ends).isoformat() if ends else now,
        },
        "segmentMs": max(durations) if durations else 0,
    }


@router.get("/logs/export")
async def export_logs(
    request: Request,
    format: str = "json",
    context: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    tasks = await services_of(request).logs.list_tasks(context.learner_id)
    records = [
        {
            "id": task.id,
            "status": task.status,
            "prompt": task.prompt,
            "createdAt": task.created_at.isoformat() if task.created_at else None,
            "updatedAt": task.updated_at.isoformat() if task.updated_at else None,
        }
        for task in tasks
    ]
    if format.lower() == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer, fieldnames=["id", "status", "prompt", "createdAt", "updatedAt"]
        )
        writer.writeheader()
        writer.writerows(records)
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=lingxi-logs.csv"},
        )
    return StreamingResponse(
        iter([json.dumps(records, ensure_ascii=False)]), media_type="application/json"
    )


@router.get("/logs/by-execution/{execution_id}")
async def log_by_execution(
    execution_id: str,
    request: Request,
    workspaceId: str = "lingxi",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _workspace_for_id(request, workspaceId, context)
    services = services_of(request)
    try:
        snapshot = await services.agent_events.agent_execution_snapshot(
            execution_id, context.learner_id
        )
    except KeyError as exc:
        raise not_found() from exc
    task_id = snapshot["taskId"]
    events = await services.logs.events(task_id, execution_id)
    metadata = snapshot["executionMetadata"]
    started_at = metadata.get("startedAt") or datetime.now(UTC).isoformat()
    detail = {
        "id": execution_id,
        "executionId": execution_id,
        "workflowId": "lingxi-agent",
        "workflowName": "LingxiGraph · Sim runtime",
        "deploymentVersionId": None,
        "deploymentVersion": None,
        "deploymentVersionName": None,
        "executionOrigin": None,
        "level": "error" if snapshot["status"] == "failed" else "info",
        "status": snapshot["status"],
        "duration": str(metadata.get("totalDurationMs") or 0),
        "trigger": metadata.get("trigger"),
        "createdAt": started_at,
        "workflow": {"id": "lingxi-agent", "name": "LingxiGraph · Sim runtime"},
        "jobTitle": None,
        "cost": {"total": 0},
        "pauseSummary": {
            "status": "awaiting_user" if snapshot["status"] == "awaiting_user" else None,
            "total": 1 if snapshot["status"] == "awaiting_user" else 0,
            "resumed": 0,
        },
        "hasPendingPause": snapshot["status"] == "awaiting_user",
        "executionData": {
            "totalDuration": metadata.get("totalDurationMs"),
            "enhanced": True,
            "traceSpans": snapshot["traceSpans"],
            "trajectory": snapshot.get("trajectory"),
            "runtimeEvents": [
                {
                    "sequence": event.sequence,
                    "kind": event.kind,
                    "agent": event.agent,
                    "runtime": event.runtime or {},
                    "createdAt": event.created_at.isoformat() if event.created_at else None,
                }
                for event in events
            ],
            "workflowInput": {"taskId": task_id},
            "trigger": metadata.get("trigger"),
        },
        "files": None,
        "events": [
            {
                "id": event.sequence,
                "sequence": event.sequence,
                "type": event.kind,
                "kind": event.kind,
                "payload": event.payload,
                "runtime": event.runtime or {},
                "createdAt": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ],
        "error": None,
    }
    return {"success": True, "data": detail}


@router.get("/logs/execution/{execution_id}")
async def execution_snapshot(
    execution_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        snapshot = await services_of(request).agent_events.agent_execution_snapshot(
            execution_id, context.learner_id
        )
        metadata = snapshot.get("executionMetadata") or {}
        metadata["startedAt"] = metadata.get("startedAt") or datetime.now(UTC).isoformat()
        snapshot["executionMetadata"] = metadata
        return snapshot
    except KeyError as exc:
        raise not_found() from exc


@router.get("/logs/{log_id}")
async def log_detail(
    log_id: str,
    request: Request,
    workspaceId: str = "lingxi",
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    await _workspace_for_id(request, workspaceId, context)
    services = services_of(request)
    repository = services.logs
    task = await repository.task(context.learner_id, log_id)
    if task is None:
        raise not_found()
    events = await repository.events(task.id)
    started_at = task.created_at.isoformat() if task.created_at else datetime.now(UTC).isoformat()
    task_snapshot = None
    if task.latest_execution_id:
        try:
            task_snapshot = await services.agent_events.agent_execution_snapshot(
                task.latest_execution_id, context.learner_id
            )
        except KeyError:
            task_snapshot = None
    detail = {
        "id": task.id,
        "executionId": task.latest_execution_id or task.id,
        "workflowId": "lingxi-agent",
        "workflowName": "LingxiGraph · Sim runtime",
        "deploymentVersionId": None,
        "deploymentVersion": None,
        "deploymentVersionName": None,
        "executionOrigin": None,
        "level": "error" if task.status == "failed" else "info",
        "status": task.status,
        "duration": str(
            (task_snapshot or {}).get("executionMetadata", {}).get("totalDurationMs") or 0
        ),
        "trigger": "agent-task",
        "createdAt": started_at,
        "workflow": {"id": "lingxi-agent", "name": "LingxiGraph · Sim runtime"},
        "jobTitle": task.title or None,
        "cost": {"total": 0},
        "pauseSummary": {
            "status": "awaiting_user" if task.status == "awaiting_user" else None,
            "total": 1 if task.status == "awaiting_user" else 0,
            "resumed": 0,
        },
        "hasPendingPause": task.status == "awaiting_user",
        "executionData": {
            "totalDuration": 0,
            "enhanced": True,
            "traceSpans": (task_snapshot or {}).get("traceSpans") or [],
            "trajectory": (task_snapshot or {}).get("trajectory"),
            "runtimeEvents": [
                {
                    "sequence": event.sequence,
                    "kind": event.kind,
                    "agent": event.agent,
                    "runtime": event.runtime or {},
                    "createdAt": event.created_at.isoformat() if event.created_at else None,
                }
                for event in events
            ],
            "workflowInput": {"taskId": task.id, "prompt": task.prompt},
            "trigger": "agent-task",
        },
        "files": None,
        "events": [
            {
                "id": event.sequence,
                "sequence": event.sequence,
                "type": event.kind,
                "kind": event.kind,
                "payload": event.payload,
                "executionId": event.execution_id,
                "runtime": event.runtime or {},
                "createdAt": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ],
        "error": task.error or None,
    }
    return {"success": True, "data": detail}
