"""Project runtime events into learner-owned Workspace Tables.

The graph/event tables are the authoritative audit store. Workspace Tables are
the learner-facing projection, so every runtime event is inspectable in the
product's table area without asking the browser to replay or re-submit it.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Workspace, WorkspaceTable, WorkspaceTableColumn, WorkspaceTableRow

RUNTIME_TABLE_VERSION = "lingxi-runtime.v1"

RUNTIME_TABLES: dict[str, dict[str, str]] = {
    "evidence": {"name": "学习证据", "description": "LingxiGraph 学习证据运行记录"},
    "mastery": {"name": "掌握度变化", "description": "Learner State 掌握度变化记录"},
    "assessment": {"name": "学习测评", "description": "题目、作答与评分运行记录"},
    "tool": {"name": "工具调用", "description": "LingxiGraph 工具调用运行记录"},
    "interaction": {"name": "学习交互", "description": "学习者与教学系统的交互记录"},
    "node": {"name": "节点执行", "description": "图节点、Agent 和 Sidecar 执行记录"},
    "run": {"name": "学习运行", "description": "未归类的学习运行事件"},
}

RUNTIME_COLUMNS: tuple[tuple[str, str], ...] = (
    ("record_key", "string"),
    ("learner_id", "string"),
    ("session_id", "string"),
    ("task_id", "string"),
    ("execution_id", "string"),
    ("sequence", "number"),
    ("event_kind", "string"),
    ("agent", "string"),
    ("payload", "json"),
    ("runtime", "json"),
    ("recorded_at", "date"),
)


def runtime_category(kind: str) -> str:
    """Return the stable learner-facing table category for an event kind."""

    normalized = kind.strip().casefold()
    if normalized in {"evidence.added", "learning.evidence", "evidence.recorded"}:
        return "evidence"
    if normalized in {
        "mastery.updated",
        "learner_state.updated",
        "learner_state.proposal",
        "state.updated",
    }:
        return "mastery"
    if normalized.startswith("assessment.") or normalized.startswith("quiz."):
        return "assessment"
    if normalized.startswith("tool."):
        return "tool"
    if normalized in {
        "learner.action",
        "learner.answer",
        "assistant.delta",
        "assistant.message",
        "message",
        "user.message",
    }:
        return "interaction"
    if (
        normalized.startswith("node.")
        or normalized.startswith("agent.")
        or normalized.startswith("sidecar.")
        or normalized.startswith("artifact.")
    ):
        return "node"
    return "run"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


async def ensure_workspace(session: AsyncSession, learner_id: str) -> Workspace:
    """Get or create the learner's private workspace in the current session."""

    workspace = await session.scalar(
        select(Workspace).where(Workspace.learner_id == learner_id)
    )
    if workspace is None:
        workspace = Workspace(
            id=f"ws_{uuid4().hex}",
            learner_id=learner_id,
            name="灵犀智学",
            appearance={},
        )
        session.add(workspace)
        await session.flush()
    return workspace


async def _runtime_table(
    session: AsyncSession,
    workspace_id: str,
    category: str,
) -> WorkspaceTable:
    definition = RUNTIME_TABLES[category]
    table = await session.scalar(
        select(WorkspaceTable).where(
            WorkspaceTable.workspace_id == workspace_id,
            WorkspaceTable.name == definition["name"],
            WorkspaceTable.archived.is_(False),
        )
    )
    if table is None:
        table = WorkspaceTable(
            id=f"table_{uuid4().hex}",
            workspace_id=workspace_id,
            name=definition["name"],
            description=definition["description"],
            metadata_payload={
                "source": "lingxi-runtime",
                "category": category,
                "schema_version": RUNTIME_TABLE_VERSION,
            },
        )
        session.add(table)
        await session.flush()

    existing = {
        column.key
        for column in (
            await session.execute(
                select(WorkspaceTableColumn).where(
                    WorkspaceTableColumn.table_id == table.id
                )
            )
        ).scalars()
    }
    for position, (key, column_type) in enumerate(RUNTIME_COLUMNS):
        if key in existing:
            continue
        session.add(
            WorkspaceTableColumn(
                id=f"col_{uuid4().hex}",
                table_id=table.id,
                key=key,
                name=key,
                type=column_type,
                position=position,
                options={},
            )
        )
    return table


async def ensure_runtime_tables(session: AsyncSession, workspace_id: str) -> list[WorkspaceTable]:
    """Materialize the complete runtime table catalog for the Tables surface."""
    return [await _runtime_table(session, workspace_id, category) for category in RUNTIME_TABLES]


async def project_runtime_events(
    session: AsyncSession,
    *,
    learner_id: str,
    records: Iterable[Mapping[str, Any]],
    workspace: Workspace | None = None,
) -> list[dict[str, Any]]:
    """Upsert runtime records into category-specific workspace tables."""

    workspace = workspace or await ensure_workspace(session, learner_id)
    tables: dict[str, WorkspaceTable] = {}
    projected: list[dict[str, Any]] = []
    for raw in records:
        kind = str(raw.get("kind") or raw.get("event_kind") or "runtime")
        category = runtime_category(kind)
        table = tables.get(category)
        if table is None:
            table = await _runtime_table(session, workspace.id, category)
            tables[category] = table

        sequence = int(raw.get("sequence") or 0)
        record_key = str(raw.get("record_key") or "").strip()
        if not record_key:
            raise ValueError("runtime record_key is required")
        payload = _json_safe(raw.get("payload") or {})
        runtime = _json_safe(raw.get("runtime") or {})
        values = {
            "record_key": record_key,
            "learner_id": learner_id,
            "session_id": str(raw.get("session_id") or ""),
            "task_id": str(raw.get("task_id") or ""),
            "execution_id": str(
                raw.get("execution_id")
                or runtime.get("execution_id")
                or payload.get("execution_id")
                or ""
            ),
            "sequence": sequence,
            "event_kind": kind,
            "agent": str(raw.get("agent") or ""),
            "payload": payload,
            "runtime": runtime,
            "recorded_at": str(
                raw.get("recorded_at") or datetime.now(UTC).isoformat()
            ),
        }
        existing = await session.scalar(
            select(WorkspaceTableRow).where(
                WorkspaceTableRow.table_id == table.id,
                WorkspaceTableRow.values["record_key"].as_string() == record_key,
            )
        )
        if existing is None:
            session.add(
                WorkspaceTableRow(
                    id=f"row_{uuid4().hex}",
                    table_id=table.id,
                    values=values,
                    position=sequence,
                )
            )
            action = "inserted"
        else:
            existing.values = values
            action = "updated"
        projected.append(
            {
                "record_key": record_key,
                "category": category,
                "table": RUNTIME_TABLES[category]["name"],
                "action": action,
            }
        )
    return projected
