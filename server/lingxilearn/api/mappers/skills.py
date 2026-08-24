"""Personal skill response mapping."""

from __future__ import annotations

from typing import Any


def skill_response(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "display_name": row.name,
        "description": row.description,
        "content": row.content,
        "version": row.version,
        "source": "personal",
        "is_system": False,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
