"""identity mappings and canonical learner data

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identity_users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issuer", sa.String(256), nullable=False),
        sa.Column("subject", sa.String(256), nullable=False),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_identity_users_issuer_subject"),
        sa.UniqueConstraint("learner_id", name="uq_identity_users_learner"),
    )
    op.create_index("ix_identity_users_learner_id", "identity_users", ["learner_id"])

    op.create_table(
        "learner_profiles",
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), primary_key=True),
        sa.Column("locale", sa.String(32), nullable=False, server_default="zh-CN"),
        sa.Column("level", sa.String(64), nullable=False, server_default="undergraduate"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "misconceptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("tag", sa.String(128), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("learner_id", "tag", name="uq_misconceptions_learner_tag"),
    )
    op.create_index("ix_misconceptions_learner_id", "misconceptions", ["learner_id"])

    op.create_table(
        "learning_evidence",
        sa.Column("id", sa.String(192), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("evidence_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("source", sa.String(256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("locator", sa.JSON(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("digest", sa.String(128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "evidence_id", name="uq_learning_evidence_session_id"),
    )
    op.create_index("ix_learning_evidence_learner_id", "learning_evidence", ["learner_id"])
    op.create_index("ix_learning_evidence_session_id", "learning_evidence", ["session_id"])
    op.create_index(
        "ix_learning_evidence_learner_created",
        "learning_evidence",
        ["learner_id", "created_at"],
    )

    op.create_table(
        "learning_preferences",
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "learning_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("event_type", sa.String(96), nullable=False),
        sa.Column("idempotency_key", sa.String(192), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "learner_id",
            "idempotency_key",
            name="uq_learning_events_learner_idempotency",
        ),
    )
    op.create_index("ix_learning_events_learner_id", "learning_events", ["learner_id"])
    op.create_index("ix_learning_events_session_id", "learning_events", ["session_id"])
    op.create_index(
        "ix_learning_events_learner_created",
        "learning_events",
        ["learner_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("learning_events")
    op.drop_table("learning_preferences")
    op.drop_table("learning_evidence")
    op.drop_table("misconceptions")
    op.drop_table("learner_profiles")
    op.drop_table("identity_users")
