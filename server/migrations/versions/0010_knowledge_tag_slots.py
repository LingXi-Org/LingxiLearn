"""Persist the slot used by the shared knowledge tag UI."""

from alembic import op
import sqlalchemy as sa

revision = "0010_knowledge_tag_slots"
down_revision = "0009_native_pinned_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspace_knowledge_tags",
        sa.Column("tag_slot", sa.String(32), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("workspace_knowledge_tags", "tag_slot")
