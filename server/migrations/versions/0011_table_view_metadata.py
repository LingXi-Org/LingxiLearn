"""Persist the metadata required by the shared table-view contract."""

from alembic import op
import sqlalchemy as sa

revision = "0011_table_view_metadata"
down_revision = "0010_knowledge_tag_slots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspace_table_views",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "workspace_table_views",
        sa.Column("created_by", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspace_table_views", "created_by")
    op.drop_column("workspace_table_views", "is_default")
