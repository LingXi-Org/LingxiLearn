"""Persist the runtime hold and serial artifact delivery board."""

from alembic import op
import sqlalchemy as sa

revision = "0015_agent_hold_board"
down_revision = "0014_conversation_interjections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "session_state",
        sa.Column("board", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("session_state", "board")
