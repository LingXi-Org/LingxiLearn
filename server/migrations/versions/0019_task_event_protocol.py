"""Assign one authoritative event reader protocol per AgentTask.

Revision ID: 0019_task_event_protocol
Revises: 0018_mothership_protocol_v1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_task_event_protocol"
down_revision = "0018_mothership_protocol_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_tasks",
        sa.Column("event_protocol_version", sa.Integer(), nullable=False, server_default="1"),
    )
    # Only tasks with no canonical event history need the read-only V0 reader.
    # Newly created tasks keep the column default of 1 before their first row.
    op.execute(
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


def downgrade() -> None:
    op.drop_column("agent_tasks", "event_protocol_version")
