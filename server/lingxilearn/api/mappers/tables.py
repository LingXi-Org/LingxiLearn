"""Table response mapping, including runtime-table visibility rules."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ...store.runtime_tables import (
    RUNTIME_COLUMN_LABELS,
    RUNTIME_COLUMNS_BY_CATEGORY,
    RUNTIME_STUDENT_COLUMNS,
)
from .constants import PUBLIC_WORKSPACE_ID


def column_response(row: Any) -> dict[str, Any]:
    opts = row.options or {}
    return {
        "id": row.id,
        "name": row.name,
        "key": row.key,
        "type": row.type,
        "position": row.position,
        "required": bool(opts.get("required", False)),
        "unique": bool(opts.get("unique", False)),
        "options": opts.get("options", []),
        "multiple": bool(opts.get("multiple", False)),
        "currencyCode": opts.get("currencyCode"),
    }


def table_response(row: Any, columns: list[Any], count: int = 0) -> dict[str, Any]:
    public_columns = [
        column_response(column) for column in sorted(columns, key=lambda item: item.position)
    ]
    metadata: dict[str, Any] = dict(row.metadata_payload or {})
    if metadata.get("source") == "lingxi-runtime":
        allowed_columns = RUNTIME_COLUMNS_BY_CATEGORY.get(
            str(metadata.get("category")), RUNTIME_STUDENT_COLUMNS
        )
        public_columns = [
            {**column, "name": RUNTIME_COLUMN_LABELS.get(column["key"], column["name"])}
            for column in public_columns
            if column["key"] in allowed_columns
        ]
    stored_locks = metadata["locks"] if isinstance(metadata.get("locks"), dict) else {}
    locks = {
        "schemaLocked": bool(stored_locks.get("schemaLocked", False)),
        "insertLocked": bool(stored_locks.get("insertLocked", False)),
        "updateLocked": bool(stored_locks.get("updateLocked", False)),
        "deleteLocked": bool(stored_locks.get("deleteLocked", False)),
    }
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "workspaceId": PUBLIC_WORKSPACE_ID,
        "folderId": metadata.get("folderId"),
        "schema": {"columns": public_columns},
        "columns": public_columns,
        "metadata": metadata,
        "rowCount": count,
        "totalRows": count,
        "createdBy": str(metadata["createdBy"]) if metadata.get("createdBy") else None,
        "locks": locks,
        "archivedAt": row.updated_at.isoformat() if row.archived and row.updated_at else None,
        "archived": row.archived,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def table_row_response(row: Any) -> dict[str, Any]:
    values = row.values or {}
    return {
        "id": row.id,
        "data": values,
        "values": values,
        "position": row.position,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def table_view_response(row: Any) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "id": row.id,
        "tableId": row.table_id,
        "name": row.name,
        "config": row.config or {},
        "isDefault": bool(row.is_default),
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat() if row.created_at else now,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else now,
    }
