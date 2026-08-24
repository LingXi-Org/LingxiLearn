"""File response mapping."""

from __future__ import annotations

from typing import Any

from .constants import PUBLIC_WORKSPACE_ID


def file_response(row: Any, workspace_id: str) -> dict[str, Any]:
    """Map a file record; ``workspace_id`` remains for the established call contract."""
    del workspace_id
    metadata = row.metadata_payload or {}
    return {
        "id": row.id,
        "workspaceId": PUBLIC_WORKSPACE_ID,
        "name": row.name,
        "key": row.storage_key,
        "path": row.path or row.name,
        "url": f"/api/files/serve/{row.storage_key}",
        "size": row.size,
        "type": row.mime_type,
        "mimeType": row.mime_type,
        "width": row.width,
        "height": row.height,
        "uploadedBy": metadata.get("uploadedBy"),
        "folderId": row.folder_id,
        "deletedAt": row.updated_at.isoformat() if row.archived and row.updated_at else None,
        "uploadedAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        "storageContext": "workspace",
        "context": "workspace",
        "readOnly": bool(metadata.get("readOnly")),
        "metadata": metadata,
    }
