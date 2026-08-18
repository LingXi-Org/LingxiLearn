"""Small shared helpers for the domain repositories."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..models.agent import CommandInbox


def utc_datetime(value: datetime) -> datetime:
    """Normalize SQLite's naive DateTime round-trip to UTC for comparisons."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def command_dict(row: CommandInbox) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "turn_id": row.turn_id,
        "sequence": int(row.sequence or 0),
        "kind": row.kind,
        "idempotency_key": row.idempotency_key,
        "payload": dict(row.payload or {}),
        "consumed_at": row.consumed_at.isoformat() if row.consumed_at else None,
    }
