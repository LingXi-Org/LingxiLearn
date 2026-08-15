"""Persist learner messages received while a runtime task is executing."""

from alembic import op
import sqlalchemy as sa

revision = "0014_conversation_interjections"
down_revision = "0013_remove_knowledge_graph"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "session_state",
        sa.Column("interjections", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("session_state", "interjections")
