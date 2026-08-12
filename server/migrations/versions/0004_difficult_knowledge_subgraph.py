"""difficult knowledge subgraph outputs and one-shot quiz submissions

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_tasks", sa.Column("deck_result", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("agent_tasks", sa.Column("quiz_result", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("agent_tasks", sa.Column("handoff_result", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("agent_tasks", sa.Column("user_messages", sa.JSON(), nullable=False, server_default="[]"))
    op.create_table(
        "quiz_submissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("submission_id", sa.String(128), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("per_question", sa.JSON(), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("handoff_reason", sa.String(64), nullable=False, server_default="quiz_completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", name="uq_quiz_submissions_task"),
        sa.UniqueConstraint("submission_id", name="uq_quiz_submissions_submission"),
    )
    op.create_index("ix_quiz_submissions_task_id", "quiz_submissions", ["task_id"])


def downgrade() -> None:
    op.drop_table("quiz_submissions")
    for name in ("user_messages", "handoff_result", "quiz_result", "deck_result"):
        op.drop_column("agent_tasks", name)
