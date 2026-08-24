"""Workspace, folder, and pin response mapping."""

from __future__ import annotations

from typing import Any

from .constants import PUBLIC_WORKSPACE_ID


def workspace_response(row: Any) -> dict[str, Any]:
    return {
        "id": PUBLIC_WORKSPACE_ID,
        "workspaceId": PUBLIC_WORKSPACE_ID,
        "name": row.name,
        "ownerId": row.learner_id,
        "organizationId": None,
        "slug": PUBLIC_WORKSPACE_ID,
        "workspaceMode": "personal",
        "role": "admin",
        "membershipId": f"membership:{row.learner_id}",
        "permissions": "admin",
        "appearance": row.appearance or {},
        "ownerBilling": {"plan": "internal", "isPaid": False, "isPro": False},
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def folder_response(row: Any, workspace_id: str) -> dict[str, Any]:
    return {
        "id": row.id,
        "workspaceId": PUBLIC_WORKSPACE_ID,
        "userId": workspace_id,
        "name": row.name,
        "parentId": row.parent_id,
        "path": row.name,
        "sortOrder": 0,
        "deletedAt": row.updated_at.isoformat() if row.archived and row.updated_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def pinned_item_response(row: Any, learner_id: str) -> dict[str, Any]:
    return {
        "id": row.id,
        "userId": learner_id,
        "workspaceId": PUBLIC_WORKSPACE_ID,
        "resourceType": row.resource_type,
        "resourceId": row.resource_id,
        "pinnedAt": row.pinned_at.isoformat() if row.pinned_at else None,
    }
