"""Persist pins for the shared native workspace resource lists."""

from alembic import op
import sqlalchemy as sa

revision = "0009_native_pinned_items"
down_revision = "0008_sim_runtime_semantics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_pinned_items",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "learner_id",
            "workspace_id",
            "resource_type",
            "resource_id",
            name="uq_workspace_pinned_item",
        ),
    )
    op.create_index("ix_workspace_pinned_items_learner_id", "workspace_pinned_items", ["learner_id"])
    op.create_index("ix_workspace_pinned_items_workspace_id", "workspace_pinned_items", ["workspace_id"])
    op.create_index(
        "ix_workspace_pinned_items_workspace_type",
        "workspace_pinned_items",
        ["workspace_id", "resource_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_pinned_items_workspace_type", table_name="workspace_pinned_items")
    op.drop_index("ix_workspace_pinned_items_workspace_id", table_name="workspace_pinned_items")
    op.drop_index("ix_workspace_pinned_items_learner_id", table_name="workspace_pinned_items")
    op.drop_table("workspace_pinned_items")
