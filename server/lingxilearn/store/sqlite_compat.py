"""SQLite quick-start compatibility repair.

SQLite is the supported zero-setup development database.  Older local
checkouts were created with ``Base.metadata.create_all`` before the latest
migrations were added, so ``create_all`` alone cannot repair them.  Keep the
compatibility DDL explicit and small: production PostgreSQL still uses the
normal Alembic chain, while a local SQLite restart upgrades the existing
file in place without discarding learner data.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import inspect

from .models.base import Base

logger = logging.getLogger(__name__)

SQLITE_SCHEMA_HEAD = "0022_native_execution_snapshots"
SQLITE_COMPAT_COLUMNS: dict[str, dict[str, str]] = {
    "agent_tasks": {
        "create_idempotency_key": "VARCHAR(192)",
        "create_payload_digest": "VARCHAR(64)",
        "title": "TEXT NOT NULL DEFAULT ''",
        "is_pinned": "BOOLEAN NOT NULL DEFAULT 0",
        "is_unread": "BOOLEAN NOT NULL DEFAULT 0",
        "deleted_at": "DATETIME",
        "resources": "JSON NOT NULL DEFAULT '[]'",
        "graph_version": "VARCHAR(32) NOT NULL DEFAULT 'difficult_knowledge.v2'",
        "deck_result": "JSON NOT NULL DEFAULT '{}'",
        "quiz_result": "JSON NOT NULL DEFAULT '{}'",
        "adaptive_result": "JSON NOT NULL DEFAULT '{}'",
        "handoff_result": "JSON NOT NULL DEFAULT '{}'",
        "user_messages": "JSON NOT NULL DEFAULT '[]'",
        "current_execution_id": "VARCHAR(128)",
        "latest_execution_id": "VARCHAR(128)",
        # 0018: the long-lived thread status alongside the legacy one-shot one.
        "thread_status": "VARCHAR(24) NOT NULL DEFAULT 'open'",
        # 0019: one authoritative reader; new/empty tasks default to V1.
        "event_protocol_version": "INTEGER NOT NULL DEFAULT 1",
    },
    "agent_task_events": {
        "execution_id": "VARCHAR(128)",
        "runtime": "JSON NOT NULL DEFAULT '{}'",
        # 0018: protocol version + canonical identity on the event log.
        "protocol_version": "INTEGER NOT NULL DEFAULT 0",
        "turn_id": "VARCHAR(128)",
        "agent_run_id": "VARCHAR(128)",
        "skill_run_id": "VARCHAR(160)",
    },
    "agent_executions": {
        # 0018: link an execution to its turn and to the execution it resumes.
        "turn_id": "VARCHAR(128)",
        "parent_execution_id": "VARCHAR(128)",
        "resumes_execution_id": "VARCHAR(128)",
    },
    "workspace_knowledge_tags": {
        "tag_slot": "VARCHAR(32) NOT NULL DEFAULT ''",
    },
    "workspace_table_views": {
        "is_default": "BOOLEAN NOT NULL DEFAULT 0",
        "created_by": "VARCHAR(64)",
    },
    "learning_evidence": {
        "task_id": "VARCHAR(96)",
        "knowledge_point": "VARCHAR(160) NOT NULL DEFAULT ''",
        "signal": "VARCHAR(48) NOT NULL DEFAULT ''",
        "source_agent": "VARCHAR(96) NOT NULL DEFAULT ''",
        "payload": "JSON NOT NULL DEFAULT '{}'",
        "seq": "INTEGER NOT NULL DEFAULT 0",
        "observed_at": "DATETIME",
    },
    "session_state": {
        "board": "JSON NOT NULL DEFAULT '{}'",
    },
    "work_items": {
        "reserved_tokens": "INTEGER NOT NULL DEFAULT 0",
        "reserved_heavy": "INTEGER NOT NULL DEFAULT 0",
        "reserved_wall_ms": "INTEGER NOT NULL DEFAULT 0",
    },
    "command_inbox": {
        "delivery_mode": "VARCHAR(24) NOT NULL DEFAULT 'command'",
        "disposition": "VARCHAR(24) NOT NULL DEFAULT 'pending'",
        "delivery_execution_id": "VARCHAR(128)",
        "delivered_at": "DATETIME",
    },
}


def repair_sqlite_schema(connection: Any) -> None:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    repaired: list[str] = []

    reset_execution_rows = False
    if "agent_executions" in existing_tables:
        execution_columns = {
            column["name"] for column in inspector.get_columns("agent_executions")
        }
        if "workflow_state" in execution_columns and "execution_snapshot" not in execution_columns:
            connection.exec_driver_sql(
                'ALTER TABLE "agent_executions" RENAME COLUMN "workflow_state" TO "execution_snapshot"'
            )
            repaired.append("agent_executions.execution_snapshot")
            reset_execution_rows = True
        if "trace_spans" in execution_columns and "timeline_spans" not in execution_columns:
            connection.exec_driver_sql(
                'ALTER TABLE "agent_executions" RENAME COLUMN "trace_spans" TO "timeline_spans"'
            )
            repaired.append("agent_executions.timeline_spans")
            reset_execution_rows = True
        inspector = inspect(connection)

    for table_name, columns in SQLITE_COMPAT_COLUMNS.items():
        if table_name not in existing_tables:
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, ddl in columns.items():
            if column_name in existing_columns:
                continue
            connection.exec_driver_sql(
                f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {ddl}'
            )
            repaired.append(f"{table_name}.{column_name}")

    if "agent_tasks.event_protocol_version" in repaired:
        connection.exec_driver_sql(
            """
            UPDATE agent_tasks
            SET event_protocol_version = 0
            WHERE NOT EXISTS (
                SELECT 1 FROM agent_task_events
                WHERE agent_task_events.task_id = agent_tasks.id
                  AND agent_task_events.protocol_version = 1
            )
            """
        )

    if reset_execution_rows:
        rows = connection.exec_driver_sql(
            "SELECT id, task_id, graph_version, status FROM agent_executions"
        ).mappings().all()
        for row in rows:
            status = str(row["status"] or "running")
            snapshot = {
                "schemaVersion": "lingxilearn.execution.v1",
                "executionId": str(row["id"]),
                "taskId": str(row["task_id"]),
                "graphVersion": str(row["graph_version"] or ""),
                "status": status,
                "paused": status == "paused",
                "terminal": status
                in {"completed", "failed", "cancelled", "timed_out", "budget_exceeded"},
                "nodes": {},
                "dependencies": [],
                "variables": {},
                "groups": {"loops": {}, "parallels": {}},
                "metadata": {"migration": "native-contract-reset"},
            }
            connection.exec_driver_sql(
                "UPDATE agent_executions SET execution_snapshot = ?, timeline_spans = '[]' WHERE id = ?",
                (json.dumps(snapshot, ensure_ascii=False), row["id"]),
            )

    # ``create_all`` does not create indexes for columns added above.  Let
    # SQLAlchemy create every declared index after the column repair; existing
    # indexes are left untouched.
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            index.create(connection, checkfirst=True)

    # A create_all-created SQLite file has no migration marker.  Once the
    # current model schema has been materialised, mark it at the same head as
    # Alembic so a later explicit ``alembic upgrade head`` is a no-op rather
    # than replaying migrations over already-existing tables.
    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"
    )
    connection.exec_driver_sql("DELETE FROM alembic_version")
    connection.exec_driver_sql(
        "INSERT INTO alembic_version (version_num) VALUES (?)",
        (SQLITE_SCHEMA_HEAD,),
    )
    if repaired:
        logger.info("Repaired SQLite schema columns: %s", ", ".join(repaired))
