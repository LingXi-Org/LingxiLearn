"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learners",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("pack_id", sa.String(64), nullable=False),
        sa.Column("pack_version", sa.String(32), nullable=False),
        sa.Column("mission_id", sa.String(64), nullable=False),
        sa.Column("checkpoint_ns", sa.String(128), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="created"),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_learner_id", "sessions", ["learner_id"])
    op.create_index("ix_sessions_status", "sessions", ["status"])

    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(48), nullable=False),
        sa.Column("node", sa.String(64), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "sequence", name="uq_run_events_session_sequence"),
    )
    op.create_index("ix_run_events_session_id", "run_events", ["session_id"])
    op.create_index("ix_run_events_session_sequence", "run_events", ["session_id", "sequence"])

    op.create_table(
        "mastery",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("concept", sa.String(96), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.35"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("learner_id", "concept", name="uq_mastery_learner_concept"),
    )
    op.create_index("ix_mastery_learner_id", "mastery", ["learner_id"])

    op.create_table(
        "reports",
        sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.id"), primary_key=True),
        sa.Column("learner_id", sa.String(64), nullable=False),
        sa.Column("mission_id", sa.String(64), nullable=False),
        sa.Column("probe_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("verify_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reports_learner_id", "reports", ["learner_id"])


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("mastery")
    op.drop_table("run_events")
    op.drop_table("sessions")
    op.drop_table("learners")
