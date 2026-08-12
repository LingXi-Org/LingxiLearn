"""agent task persistence

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("intent", sa.JSON(), nullable=False),
        sa.Column("lecture_result", sa.JSON(), nullable=False),
        sa.Column("visual_result", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_tasks_learner_id", "agent_tasks", ["learner_id"])
    op.create_index("ix_agent_tasks_status", "agent_tasks", ["status"])

    op.create_table(
        "agent_task_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("agent", sa.String(64), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "sequence", name="uq_agent_task_events_sequence"),
    )
    op.create_index("ix_agent_task_events_task_id", "agent_task_events", ["task_id"])
    op.create_index(
        "ix_agent_task_events_task_sequence",
        "agent_task_events",
        ["task_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_table("agent_task_events")
    op.drop_table("agent_tasks")
