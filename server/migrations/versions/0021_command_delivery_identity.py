"""Persist command delivery identity and disposition.

Revision ID: 0021_command_delivery_identity
Revises: 0020_remove_legacy_interjections
"""

import sqlalchemy as sa
from alembic import op

revision = "0021_command_delivery_identity"
down_revision = "0020_remove_legacy_interjections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "command_inbox",
        sa.Column("delivery_mode", sa.String(length=24), nullable=False, server_default="command"),
    )
    op.add_column(
        "command_inbox",
        sa.Column("disposition", sa.String(length=24), nullable=False, server_default="pending"),
    )
    op.add_column(
        "command_inbox",
        sa.Column("delivery_execution_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "command_inbox",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_command_inbox_delivery_mode", "command_inbox", ["delivery_mode"], unique=False
    )
    op.create_index(
        "ix_command_inbox_disposition", "command_inbox", ["disposition"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_command_inbox_disposition", table_name="command_inbox")
    op.drop_index("ix_command_inbox_delivery_mode", table_name="command_inbox")
    op.drop_column("command_inbox", "delivered_at")
    op.drop_column("command_inbox", "delivery_execution_id")
    op.drop_column("command_inbox", "disposition")
    op.drop_column("command_inbox", "delivery_mode")
