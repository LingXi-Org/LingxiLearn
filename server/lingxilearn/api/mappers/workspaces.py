"""Workspace DTO mapping."""

from __future__ import annotations

from ...domain.workspace import Workspace
from .constants import PUBLIC_WORKSPACE_ID


def workspace_response(row: Workspace) -> dict[str, object]:
    return {
        "id": PUBLIC_WORKSPACE_ID,
        "name": row.name,
        "appearance": row.appearance or {},
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }
