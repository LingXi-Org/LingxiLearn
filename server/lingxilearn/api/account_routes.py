"""Learner-local settings and usage-audit routes.

Authentication and profile management belong exclusively to LingxiIdentity. This
module only exposes state that LingxiLearn persists itself: learner preferences
and an audit view over real agent tasks.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ..contracts.rest_models import UserSettingsResponse, UserSettingsUpdateResponse
from ..learner import LearnerContext
from ..store.models.agent import AgentTask
from .dependencies import current_learner_context, not_found, services_of

router = APIRouter(prefix="/api")

_USAGE_SOURCES = {"agent-task"}


def _period_bounds(
    period: str, start_date: str | None, end_date: str | None
) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    if period == "1d":
        return now - timedelta(days=1), now
    if period == "7d":
        return now - timedelta(days=7), now
    if period == "all":
        return datetime(1970, 1, 1, tzinfo=UTC), now
    if period == "custom":
        if not start_date:
            raise HTTPException(status_code=422, detail="startDate is required for custom period")
        try:
            start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end = datetime.fromisoformat((end_date or now.isoformat()).replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="invalid_usage_period") from exc
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        if end < start:
            raise HTTPException(status_code=422, detail="usage_period_end_before_start")
        return start, end
    return now - timedelta(days=30), now


def _settings_public(context: LearnerContext) -> dict[str, Any]:
    values = dict(context.preferences or {})
    return {
        "theme": values.get("theme", "system"),
        "autoConnect": bool(values.get("autoConnect", True)),
        "telemetryEnabled": bool(values.get("telemetryEnabled", True)),
        "emailPreferences": dict(values.get("emailPreferences") or {}),
        "billingUsageNotificationsEnabled": bool(
            values.get("billingUsageNotificationsEnabled", True)
        ),
        "superUserModeEnabled": False,
        "mothershipEnvironment": "default",
        "errorNotificationsEnabled": bool(values.get("errorNotificationsEnabled", True)),
        "snapToGridSize": float(values.get("snapToGridSize", 0) or 0),
        "showActionBar": bool(values.get("showActionBar", True)),
        "copilotAutoAllowedTools": list(values.get("copilotAutoAllowedTools") or []),
        "timezone": values.get("timezone"),
        "lastActiveWorkspaceId": values.get("lastActiveWorkspaceId"),
    }


@router.get("/users/me/settings", response_model=UserSettingsResponse)
async def get_user_settings(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    return {"data": _settings_public(context)}


@router.patch("/users/me/settings", response_model=UserSettingsUpdateResponse)
async def update_user_settings(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    allowed = {
        "theme",
        "autoConnect",
        "telemetryEnabled",
        "emailPreferences",
        "billingUsageNotificationsEnabled",
        "errorNotificationsEnabled",
        "snapToGridSize",
        "showActionBar",
        "copilotAutoAllowedTools",
        "timezone",
        "lastActiveWorkspaceId",
    }
    patch = {key: value for key, value in body.items() if key in allowed}
    if "theme" in patch and patch["theme"] not in {"system", "light", "dark"}:
        raise HTTPException(status_code=422, detail="invalid_theme")
    boolean_fields = {
        "autoConnect",
        "telemetryEnabled",
        "billingUsageNotificationsEnabled",
        "errorNotificationsEnabled",
        "showActionBar",
    }
    for key in boolean_fields:
        if key in patch and not isinstance(patch[key], bool):
            raise HTTPException(status_code=422, detail=f"invalid_{key}")
    if "emailPreferences" in patch:
        preferences = patch["emailPreferences"]
        if not isinstance(preferences, dict) or any(
            key
            not in {
                "unsubscribeAll",
                "unsubscribeMarketing",
                "unsubscribeUpdates",
                "unsubscribeNotifications",
            }
            or not isinstance(value, bool)
            for key, value in preferences.items()
        ):
            raise HTTPException(status_code=422, detail="invalid_email_preferences")
    if "copilotAutoAllowedTools" in patch:
        tools = patch["copilotAutoAllowedTools"]
        if not isinstance(tools, list) or any(not isinstance(tool, str) for tool in tools):
            raise HTTPException(status_code=422, detail="invalid_copilot_tools")
    if "timezone" in patch and patch["timezone"] is not None:
        timezone = patch["timezone"]
        if not isinstance(timezone, str):
            raise HTTPException(status_code=422, detail="invalid_timezone")
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(timezone)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="invalid_timezone") from exc
    if "lastActiveWorkspaceId" in patch and patch["lastActiveWorkspaceId"] not in {
        None,
        "lingxi",
    }:
        raise HTTPException(status_code=404, detail="workspace_not_found")
    if "snapToGridSize" in patch:
        try:
            value = float(patch["snapToGridSize"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="invalid_snap_to_grid_size") from exc
        if value < 0 or value > 50:
            raise HTTPException(status_code=422, detail="invalid_snap_to_grid_size")
        patch["snapToGridSize"] = value
    await services_of(request).learners.update_preference(context, patch)
    context.preferences = {**(context.preferences or {}), **patch}
    return {"success": True, "data": _settings_public(context)}


async def _usage_rows(
    request: Request,
    learner: LearnerContext,
    period: str,
    start_date: str | None,
    end_date: str | None,
    source: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], bool, str | None]:
    if period not in {"1d", "7d", "30d", "all", "custom"}:
        raise HTTPException(status_code=422, detail="invalid_usage_period")
    if source and source not in _USAGE_SOURCES:
        raise HTTPException(status_code=422, detail="invalid_usage_source")
    start, end = _period_bounds(period, start_date, end_date)
    offset = 0
    if cursor:
        try:
            offset = max(0, int(cursor))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="invalid_usage_cursor") from exc
    async with services_of(request).db.session() as session:
        query = (
            select(AgentTask)
            .where(
                AgentTask.learner_id == learner.learner_id,
                AgentTask.created_at >= start,
                AgentTask.created_at <= end,
            )
            .order_by(AgentTask.created_at.desc(), AgentTask.id.desc())
        )
        tasks = list((await session.execute(query.offset(offset).limit(limit + 1))).scalars().all())
    has_more = len(tasks) > limit
    tasks = tasks[:limit]
    rows = [
        {
            "id": task.id,
            "createdAt": (
                task.created_at.isoformat() if task.created_at else datetime.now(UTC).isoformat()
            ),
            "source": "agent-task",
            "workflowName": None,
            "creditCost": 0,
            "hasCost": False,
        }
        for task in tasks
    ]
    next_cursor = str(offset + limit) if has_more else None
    return rows, has_more, next_cursor


@router.get("/users/me/usage-logs")
async def usage_logs(
    request: Request,
    period: str = Query("30d"),
    startDate: str | None = None,
    endDate: str | None = None,
    source: str | None = None,
    workspaceId: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    includeCredits: bool = True,
    learner: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    if workspaceId not in {None, "lingxi"}:
        raise not_found()
    rows, has_more, next_cursor = await _usage_rows(
        request, learner, period, startDate, endDate, source, limit, cursor
    )
    return {
        "success": True,
        "logs": rows,
        "summary": {"totalCredits": 0, "bySourceCredits": {"agent-task": 0}},
        "pagination": {"nextCursor": next_cursor, "hasMore": has_more},
    }


@router.get("/users/me/usage-logs/export")
async def usage_logs_export(
    request: Request,
    period: str = Query("30d"),
    startDate: str | None = None,
    endDate: str | None = None,
    source: str | None = None,
    workspaceId: str | None = None,
    learner: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    if workspaceId not in {None, "lingxi"}:
        raise not_found()
    rows, _has_more, _cursor = await _usage_rows(
        request, learner, period, startDate, endDate, source, 1000, None
    )
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["id", "createdAt", "source", "workflowName", "creditCost", "hasCost"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=lingxi-usage-audit.csv"},
    )
