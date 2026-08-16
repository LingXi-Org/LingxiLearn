"""Persist create-request idempotency for agent tasks."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_agent_task_create_idempotency"
down_revision = "0016_orchestration_v2_ledger"
branch_labels = None
depends_on = None


def _ensure_alembic_version_capacity() -> None:
    """Allow descriptive revision ids longer than Alembic's default 32 chars.

    PostgreSQL enforces the VARCHAR length on ``alembic_version.version_num``.
    This revision id is 34 characters, so the schema changes can succeed and
    still fail when Alembic records the new head unless the version column is
    widened first. SQLite does not enforce VARCHAR lengths and needs no change.
    """

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(length=32),
            type_=sa.String(length=64),
            existing_nullable=False,
        )


def upgrade() -> None:
    _ensure_alembic_version_capacity()
    op.add_column(
        "agent_tasks",
        sa.Column("create_idempotency_key", sa.String(192), nullable=True),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("create_payload_digest", sa.String(64), nullable=True),
    )
    op.create_index(
        "uq_agent_tasks_learner_create_key",
        "agent_tasks",
        ["learner_id", "create_idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_agent_tasks_learner_create_key", table_name="agent_tasks")
    op.drop_column("agent_tasks", "create_payload_digest")
    op.drop_column("agent_tasks", "create_idempotency_key")
