"""Remove the retired Knowledge Graph persistence layer."""

from alembic import op

revision = "0013_remove_knowledge_graph"
down_revision = "0012_multi_agent_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop children first because the graph tables use foreign keys.
    for table in (
        "knowledge_graph_events",
        "knowledge_graph_learner_overlay",
        "knowledge_graph_edges",
        "knowledge_graph_nodes",
        "knowledge_graphs",
    ):
        op.drop_table(table, if_exists=True)


def downgrade() -> None:
    # This feature is intentionally removed and has no downgrade contract.
    pass

