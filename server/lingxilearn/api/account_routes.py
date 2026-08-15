"""Account, billing, and settings surfaces for Lingxi.

LingxiIdentity remains authoritative for authentication, profile verification,
passwords, email changes, and device sessions. This module owns the small
learner-local settings document and exposes the shared billing contracts as
read-only/no-op responses: the private Lingxi workspace has no Stripe customer,
team seats, invitations, or paid plan.
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from ..learner import LearnerContext
from ..store.models import AgentTask, Learner, LearnerProfile, Workspace, WorkspaceFile
from .routes import current_learner_context, not_found, service_of

router = APIRouter(prefix="/api")

_BILLING_SOURCES = {
    "workflow",
    "wand",
    "sim-chat",
    "mcp_copilot",
    "mothership_block",
    "knowledge-base",
    "voice-input",
    "enrichment",
    "voice-output",
}

_TELEMETRY_CATEGORIES = {
    "page_view",
    "feature_usage",
    "performance",
    "error",
    "workflow",
    "consent",
    "batch",
}


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


def _billing_data() -> dict[str, Any]:
    now = datetime.now(UTC)
    period_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    days_remaining = max(0, (next_month - now).days)
    usage = {
        "current": 0,
        "limit": 0,
        "percentUsed": 0,
        "isWarning": False,
        "isExceeded": False,
        "billingPeriodStart": period_start.isoformat(),
        "billingPeriodEnd": next_month.isoformat(),
        "lastPeriodCost": 0,
        "lastPeriodCopilotCost": 0,
        "daysRemaining": days_remaining,
        "copilotCost": 0,
    }
    return {
        "type": "individual",
        "plan": "internal",
        "currentUsage": 0,
        "usageLimit": 0,
        "percentUsed": 0,
        "isWarning": False,
        "isExceeded": False,
        "daysRemaining": days_remaining,
        "creditBalance": 0,
        "billingInterval": "month",
        "isPaid": False,
        "isPro": False,
        "isTeam": False,
        "isEnterprise": False,
        "isOrgScoped": False,
        "organizationId": None,
        "status": "inactive",
        "seats": None,
        "metadata": {"provider": "lingxilearn", "placeholder": True},
        "stripeSubscriptionId": None,
        "periodEnd": next_month.isoformat(),
        "cancelAtPeriodEnd": False,
        "usage": usage,
        "billingBlocked": False,
        "billingBlockedReason": None,
        "blockedByOrgOwner": False,
        "upgradeWorkspaceId": None,
    }


def _profile_public(context: LearnerContext) -> dict[str, Any]:
    subject = context.subject or context.learner_id
    safe_id = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:16]
    payload = context.profile or {}
    return {
        "id": subject,
        "name": str(payload.get("name") or subject),
        "email": str(payload.get("email") or f"learner-{safe_id}@lingxilearn.local"),
        "image": payload.get("avatar") if isinstance(payload.get("avatar"), str) else None,
        "emailVerified": False,
    }


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


@router.get("/settings/allowed-integrations")
async def allowed_integrations(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Keep the shared Sim capability query on the native API boundary."""

    return {"allowedIntegrations": None, "integrationAvailability": []}


@router.post("/telemetry")
async def record_telemetry(
    body: dict[str, Any],
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, bool]:
    """Accept the shared telemetry contract without creating a second sink.

    The local LingxiLearn deployment has no analytics database or forwarding
    service. Acknowledging the validated envelope keeps reused settings UI
    deterministic while ``forwarded=false`` makes the local behavior explicit.
    """

    category = body.get("category")
    action = body.get("action")
    if category not in _TELEMETRY_CATEGORIES or not isinstance(action, str) or not action.strip():
        raise HTTPException(status_code=422, detail="invalid_telemetry_event")
    return {"success": True, "forwarded": False}


@router.get("/settings/allowed-providers")
async def allowed_providers(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, list[str]]:
    """Expose the empty local provider blacklist expected by shared Sim hooks."""

    return {"blacklistedProviders": []}


@router.get("/settings/voice")
async def voice_settings(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, bool]:
    # LingxiLearn has no server-side STT provider configured in the local
    # runtime, so the reused input control can hide its microphone affordance.
    return {"sttAvailable": False}


@router.get("/users/me/profile")
async def get_user_profile(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    return {"user": _profile_public(context)}


@router.patch("/users/me/profile")
async def update_user_profile(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    if "name" not in body and "image" not in body:
        raise HTTPException(status_code=422, detail="profile_change_required")
    name = body.get("name")
    image = body.get("image")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise HTTPException(status_code=422, detail="invalid_profile_name")
    if image is not None:
        if not isinstance(image, str) or not (
            image.startswith("http://") or image.startswith("https://") or image.startswith("/api/")
        ):
            raise HTTPException(status_code=422, detail="invalid_profile_image")
    svc = service_of(request)
    async with svc.db.session() as session:
        learner = await session.get(Learner, context.learner_id)
        profile = await session.get(LearnerProfile, context.learner_id)
        if learner is None or profile is None:
            raise not_found()
        payload = dict(profile.payload or {})
        if name is not None:
            learner.display_name = name.strip()[:128]
            payload["name"] = learner.display_name
        if "image" in body:
            payload["avatar"] = image
        profile.payload = payload
        await session.commit()
    public = _profile_public(context)
    if name is not None:
        public["name"] = name.strip()[:128]
    if "image" in body:
        public["image"] = image
    return {"success": True, "user": public}


@router.get("/users/me/settings")
async def get_user_settings(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    return {"data": _settings_public(context)}


@router.get("/organizations")
async def list_organizations(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Return the native organization-list shape without enabling teams.

    The private Lingxi workspace is intentionally not an organization. Native
    upgrade/account hooks can therefore render an empty, stable list instead
    of probing a team-membership store that this deployment does not have.
    """

    return {"organizations": [], "isMemberOfAnyOrg": False}


@router.patch("/users/me/settings")
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
    await service_of(request).learners.update_preference(context, patch)
    context.preferences = {**(context.preferences or {}), **patch}
    return {"success": True, "data": _settings_public(context)}


@router.get("/billing")
async def get_billing(
    request: Request,
    context: str = Query("user"),
    id: str | None = None,
    includeOrg: bool = False,
    learner: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    if context not in {"user", "organization"}:
        raise HTTPException(status_code=400, detail="invalid_billing_context")
    if context == "organization":
        # Lingxi workspaces are intentionally private singletons. Keep the
        # response contract available for native settings, but expose no
        # members, invitations, or organization mutation surface.
        organization_id = id or "lingxi"
        if organization_id != "lingxi":
            raise not_found()
        data = {
            "organizationId": organization_id,
            "organizationName": "灵犀智学（个人工作区）",
            "subscriptionState": "free",
            "hasSubscription": False,
            "subscriptionPlan": "internal",
            "subscriptionStatus": None,
            "creditBalance": 0,
            "billingInterval": "month",
            "cancelAtPeriodEnd": False,
            "totalSeats": 1,
            "usedSeats": 1,
            "seatsCount": 1,
            "totalCurrentUsage": 0,
            "totalUsageLimit": 0,
            "minimumBillingAmount": 0,
            "averageUsagePerMember": 0,
            "billingPeriodStart": None,
            "billingPeriodEnd": None,
            "members": [],
            "billingBlocked": False,
            "billingBlockedReason": None,
            "blockedByOrgOwner": False,
            "upgradeWorkspaceId": None,
        }
        return {
            "success": True,
            "context": "organization",
            "data": data,
            "userRole": "owner",
            "billingBlocked": False,
            "billingBlockedReason": None,
            "blockedByOrgOwner": False,
        }
    return {"success": True, "context": "user", "data": _billing_data()}


@router.get("/usage")
async def get_usage(
    context: str = Query("user"),
    learner: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    if context != "user":
        raise HTTPException(status_code=404, detail="organization_usage_unavailable")
    return {
        "success": True,
        "context": "user",
        "userId": learner.learner_id,
        "organizationId": None,
        "data": {
            "currentLimit": 0,
            "canEdit": False,
            "minimumLimit": 0,
            "plan": "internal",
            "updatedAt": None,
            "scope": "user",
            "organizationId": None,
        },
    }


@router.put("/usage")
async def update_usage(
    body: dict[str, Any],
    context: str = Query("user"),
    learner: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    if context != "user" or body.get("context", "user") != "user":
        raise HTTPException(status_code=404, detail="organization_usage_unavailable")
    return {
        "success": True,
        "context": "user",
        "userId": learner.learner_id,
        "organizationId": None,
        "data": {
            "currentLimit": 0,
            "canEdit": False,
            "minimumLimit": 0,
            "plan": "internal",
            "updatedAt": None,
            "scope": "user",
            "organizationId": None,
        },
        "message": "个人工作区不启用计费额度修改",
    }


@router.get("/billing/invoices")
async def list_invoices() -> dict[str, Any]:
    return {"success": True, "invoices": [], "hasMore": False}


@router.post("/billing/portal")
async def billing_portal() -> dict[str, str]:
    return {"url": "/workspace/lingxi/settings/billing?placeholder=portal"}


@router.post("/billing/credits")
async def purchase_credits() -> dict[str, Any]:
    return {"success": False, "message": "LingxiLearn 当前不启用在线充值"}


@router.post("/billing/switch-plan")
async def switch_plan() -> dict[str, Any]:
    return {
        "success": True,
        "plan": "internal",
        "interval": "month",
        "message": "个人工作区使用内部学习额度，暂不支持套餐切换",
    }


@router.post("/billing/update-cost")
async def update_cost(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid_billing_payload") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="invalid_billing_payload")
    for field in ("userId", "model", "idempotencyKey"):
        if not isinstance(body.get(field), str) or not body[field].strip():
            raise HTTPException(status_code=422, detail=f"{field}_required")
    cost = body.get("cost")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0:
        raise HTTPException(status_code=422, detail="invalid_cost")
    request_id = request.headers.get("x-billing-request-id") or str(uuid.uuid4())
    try:
        uuid.UUID(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid_billing_request_id") from exc
    return {
        "success": True,
        "message": "billing disabled",
        "data": {
            "userId": body["userId"],
            "cost": 0,
            "billingEnabled": False,
            "processedAt": datetime.now(UTC).isoformat(),
            "requestId": request_id,
        },
    }


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
    if source and source not in _BILLING_SOURCES:
        raise HTTPException(status_code=422, detail="invalid_usage_source")
    start, end = _period_bounds(period, start_date, end_date)
    if source and source != "sim-chat":
        return [], False, None
    offset = 0
    if cursor:
        try:
            offset = max(0, int(cursor))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="invalid_usage_cursor") from exc
    async with service_of(request).db.session() as session:
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
            "source": "sim-chat",
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
        "summary": {"totalCredits": 0, "bySourceCredits": {"sim-chat": 0}},
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
        headers={"Content-Disposition": "attachment; filename=lingxi-credit-usage.csv"},
    )


@router.post("/users/me/subscription/{subscription_id}/transfer")
async def transfer_subscription(subscription_id: str, body: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, "message": "LingxiLearn 个人工作区不支持订阅转移"}


@router.get("/v2/billing/status")
async def v2_billing_status(
    request: Request,
    workspaceId: str | None = None,
    learner: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Read-only v2 billing status for the private Lingxi workspace.

    Sim's versioned billing contract is kept available for native hooks and
    external monitors, while payment plans and organization billing remain
    deliberately disabled.  The period is an open interval because there is
    no Stripe invoice that would reset a personal learner's allowance.
    """

    if workspaceId not in {None, "lingxi"}:
        raise not_found()
    async with service_of(request).db.session() as session:
        used_bytes = (
            await session.scalar(
                select(func.coalesce(func.sum(WorkspaceFile.size), 0))
                .join(Workspace, Workspace.id == WorkspaceFile.workspace_id)
                .where(
                    Workspace.learner_id == learner.learner_id,
                    WorkspaceFile.archived.is_(False),
                )
            )
            or 0
        )
    storage_limit = 20 * 1024 * 1024 * 100
    used = int(used_bytes)
    return {
        "data": {
            "workspaceId": "lingxi",
            "period": {
                "start": "1970-01-01T00:00:00.000Z",
                "end": "9999-12-31T23:59:59.999Z",
            },
            "plan": "internal",
            "status": "active",
            "credits": {"used": 0, "limit": 0, "remaining": 0},
            "storage": {
                "usedBytes": used,
                "limitBytes": storage_limit,
                "percentUsed": min(100, used * 100 / storage_limit),
            },
        }
    }


@router.get("/v2/billing/logs")
async def v2_billing_logs(
    request: Request,
    period: str = Query("30d"),
    startDate: str | None = None,
    endDate: str | None = None,
    source: str | None = None,
    workspaceId: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    learner: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    if workspaceId not in {None, "lingxi"}:
        raise not_found()
    rows, has_more, next_cursor = await _usage_rows(
        request,
        learner,
        period,
        startDate,
        endDate,
        source,
        limit,
        cursor,
    )
    return {
        "data": [
            {
                "id": row["id"],
                "createdAt": row["createdAt"],
                "source": row["source"],
                "workspaceId": "lingxi",
                "workflow": None,
                "runId": None,
                "creditCost": row["creditCost"],
            }
            for row in rows
        ],
        "nextCursor": next_cursor if has_more else None,
    }
