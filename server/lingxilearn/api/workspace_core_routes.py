"""Workspace API routes split by resource family."""

from fastapi import APIRouter

from ..application.workspace_errors import WorkspaceDomainError
from .workspace_route_shared import (
    UTC,
    Any,
    Depends,
    HTTPException,
    LearnerContext,
    MessageResponse,
    PinnedItemResponse,
    PinnedItemsResponse,
    Request,
    SuccessResponse,
    WorkspaceListResponse,
    WorkspaceMembersResponse,
    WorkspacePermissionsResponse,
    WorkspaceResponse,
    _pinned_item_public,
    _public_workspace,
    _workspace,
    _workspace_for_id,
    current_learner_context,
    datetime,
    services_of,
)

router = APIRouter(prefix="/api")


@router.get("/workspaces", response_model=WorkspaceListResponse)
async def list_workspaces(
    request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    row = await _workspace(request, context)
    return {
        "workspaces": [_public_workspace(row)],
        "lastActiveWorkspaceId": "lingxi",
        "pinnedWorkspaceIds": [],
        "creationPolicy": None,
    }


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    row = await _workspace_for_id(request, workspace_id, context)
    return {"workspace": _public_workspace(row), "data": _public_workspace(row)}


@router.get("/workspaces/{workspace_id}/members", response_model=WorkspaceMembersResponse)
async def list_workspace_members(
    workspace_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    await _workspace_for_id(request, workspace_id, context)
    return {
        "members": [
            {
                "userId": context.learner_id,
                "name": str(context.profile.get("displayName") or "学习者"),
                "image": None,
            }
        ]
    }


@router.get("/workspaces/{workspace_id}/permissions", response_model=WorkspacePermissionsResponse)
async def get_workspace_permissions(
    workspace_id: str, request: Request, context: LearnerContext = Depends(current_learner_context)
) -> dict[str, Any]:
    await _workspace_for_id(request, workspace_id, context)
    user = {
        "userId": context.learner_id,
        "email": f"{context.learner_id}@lingxilearn.local",
        "name": str(context.profile.get("displayName") or "学习者"),
        "image": None,
        "permissionType": "admin",
        "isExternal": False,
        "joinedAt": datetime.now(UTC).isoformat(),
        "roleSource": "owner",
        "isBilledAccount": True,
    }
    return {
        "users": [user],
        "total": 1,
        "viewer": {"userId": context.learner_id, "isAdmin": True, "permissionType": "admin"},
    }


@router.patch("/workspaces/{workspace_id}/permissions", response_model=MessageResponse)
async def update_workspace_permissions(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, str]:
    """Acknowledge the shared write contract at the personal-workspace boundary.

    Lingxi workspaces have exactly one identity-owned member. There is no
    second organization permission store to mutate, but keeping this endpoint
    available prevents the reused settings shell from probing a removed route.
    The canonical membership representation remains the GET response above.
    """

    await _workspace_for_id(request, workspace_id, context)
    updates = body.get("updates")
    if not isinstance(updates, list) or not updates:
        raise HTTPException(status_code=422, detail="updates_required")
    return {"message": "Lingxi personal workspace permissions are identity-managed"}


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    row = await services_of(request).workspaces.update(
        context.learner_id, workspace_id, body
    )
    return {"workspace": _public_workspace(row), "data": _public_workspace(row)}


# Pins ----------------------------------------------------------------------


@router.get("/pinned-items", response_model=PinnedItemsResponse)
async def list_pinned_items(
    request: Request,
    workspaceId: str,
    resourceType: str | None = None,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        rows = await services_of(request).workspaces.list_pins(
            context.learner_id, workspaceId, resourceType
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return {"pinnedItems": [_pinned_item_public(row, context.learner_id) for row in rows]}


@router.post("/pinned-items", response_model=PinnedItemResponse)
async def create_pinned_item(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        row = await services_of(request).workspaces.create_pin(context.learner_id, body)
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return {"pinnedItem": _pinned_item_public(row, context.learner_id)}


@router.delete("/pinned-items/{resource_type}/{resource_id}", response_model=SuccessResponse)
async def delete_pinned_item(
    resource_type: str,
    resource_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        await services_of(request).workspaces.delete_pin(
            context.learner_id, resource_type, resource_id
        )
    except WorkspaceDomainError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return {"success": True}


# Folders and files ----------------------------------------------------------
