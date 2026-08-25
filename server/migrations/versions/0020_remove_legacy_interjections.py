"""Remove the legacy SessionState mid-turn input queue.

Revision ID: 0020_remove_legacy_interjections
Revises: 0019_task_event_protocol
"""

import sqlalchemy as sa
from alembic import op

revision = "0020_remove_legacy_interjections"
down_revision = "0019_task_event_protocol"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("session_state", "interjections")


def downgrade() -> None:
    op.add_column(
        "session_state",
        sa.Column("interjections", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
