"""Close persisted executions over the native LingxiLearn contracts.

Revision ID: 0022_native_execution_snapshots
Revises: 0021_command_delivery_identity
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_native_execution_snapshots"
down_revision = "0021_command_delivery_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Deterministically discard pre-native projections instead of translating them."""

    op.alter_column(
        "agent_executions",
        "workflow_state",
        new_column_name="execution_snapshot",
        existing_type=sa.JSON(),
        existing_nullable=False,
    )
    op.alter_column(
        "agent_executions",
        "trace_spans",
        new_column_name="timeline_spans",
        existing_type=sa.JSON(),
        existing_nullable=False,
    )
    executions = sa.table(
        "agent_executions",
        sa.column("id", sa.String()),
        sa.column("task_id", sa.String()),
        sa.column("graph_version", sa.String()),
        sa.column("status", sa.String()),
        sa.column("execution_snapshot", sa.JSON()),
        sa.column("timeline_spans", sa.JSON()),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(
            executions.c.id,
            executions.c.task_id,
            executions.c.graph_version,
            executions.c.status,
        )
    ).mappings().all()
    for row in rows:
        status = str(row["status"] or "running")
        terminal = status in {
            "completed",
            "failed",
            "cancelled",
            "timed_out",
            "budget_exceeded",
        }
        snapshot = {
            "schemaVersion": "lingxilearn.execution.v1",
            "executionId": str(row["id"]),
            "taskId": str(row["task_id"]),
            "graphVersion": str(row["graph_version"] or ""),
            "status": status,
            "paused": status == "paused",
            "terminal": terminal,
            "nodes": {},
            "dependencies": [],
            "variables": {},
            "groups": {"loops": {}, "parallels": {}},
            "metadata": {"migration": "native-contract-reset"},
        }
        connection.execute(
            executions.update()
            .where(executions.c.id == row["id"])
            .values(execution_snapshot=snapshot, timeline_spans=[])
        )


def downgrade() -> None:
    # The legacy editor/trace projections were intentionally removed and cannot
    # be reconstructed from the native reset without replaying the event log.
    op.alter_column(
        "agent_executions",
        "timeline_spans",
        new_column_name="trace_spans",
        existing_type=sa.JSON(),
        existing_nullable=False,
    )
    op.alter_column(
        "agent_executions",
        "execution_snapshot",
        new_column_name="workflow_state",
        existing_type=sa.JSON(),
        existing_nullable=False,
    )
