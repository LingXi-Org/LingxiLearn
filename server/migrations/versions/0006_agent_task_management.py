"""native chat metadata for Lingxi agent tasks

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_tasks", sa.Column("title", sa.Text(), nullable=False, server_default=""))
    op.add_column("agent_tasks", sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("agent_tasks", sa.Column("is_unread", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("agent_tasks", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_tasks", sa.Column("resources", sa.JSON(), nullable=False, server_default="[]"))
    op.create_index("ix_agent_tasks_deleted_at", "agent_tasks", ["deleted_at"])
    op.create_index("ix_agent_tasks_is_pinned", "agent_tasks", ["is_pinned"])


def downgrade() -> None:
    op.drop_index("ix_agent_tasks_is_pinned", table_name="agent_tasks")
    op.drop_index("ix_agent_tasks_deleted_at", table_name="agent_tasks")
    op.drop_column("agent_tasks", "resources")
    op.drop_column("agent_tasks", "deleted_at")
    op.drop_column("agent_tasks", "is_unread")
    op.drop_column("agent_tasks", "is_pinned")
    op.drop_column("agent_tasks", "title")
