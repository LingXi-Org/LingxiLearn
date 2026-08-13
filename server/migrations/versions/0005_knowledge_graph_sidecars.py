"""durable learner knowledge graphs and agent sidecars

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_tasks",
        # Existing rows retain the former graph; Service explicitly marks new
        # tasks as knowledge_deep_dive.v1.
        sa.Column("graph_version", sa.String(32), nullable=False, server_default="difficult_knowledge.v2"),
    )
    op.add_column("agent_tasks", sa.Column("adaptive_result", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table(
        "agent_task_sidecars",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "kind", name="uq_agent_task_sidecars_task_kind"),
    )
    op.create_index("ix_agent_task_sidecars_task_id", "agent_task_sidecars", ["task_id"])
    op.create_index("ix_agent_task_sidecars_learner_id", "agent_task_sidecars", ["learner_id"])
    op.create_index("ix_agent_task_sidecars_status", "agent_task_sidecars", ["status"])
    op.create_index(
        "ix_agent_task_sidecars_task_status",
        "agent_task_sidecars",
        ["task_id", "status"],
    )

    op.create_table(
        "knowledge_graphs",
        sa.Column("graph_id", sa.String(128), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("domain", sa.String(120), nullable=False, server_default=""),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("learner_id", "graph_id", name="uq_knowledge_graphs_learner_graph"),
    )
    op.create_index("ix_knowledge_graphs_learner_id", "knowledge_graphs", ["learner_id"])
    op.create_index(
        "ix_knowledge_graphs_learner_updated",
        "knowledge_graphs",
        ["learner_id", "updated_at"],
    )

    op.create_table(
        "knowledge_graph_nodes",
        sa.Column("graph_id", sa.String(128), sa.ForeignKey("knowledge_graphs.graph_id"), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("position", sa.JSON(), nullable=True),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("graph_id", "node_id"),
    )
    op.create_index("ix_knowledge_graph_nodes_graph_id", "knowledge_graph_nodes", ["graph_id"])

    op.create_table(
        "knowledge_graph_edges",
        sa.Column("graph_id", sa.String(128), sa.ForeignKey("knowledge_graphs.graph_id"), nullable=False),
        sa.Column("edge_id", sa.String(128), nullable=False),
        sa.Column("source_node_id", sa.String(128), nullable=False),
        sa.Column("target_node_id", sa.String(128), nullable=False),
        sa.Column("relation", sa.String(48), nullable=False),
        sa.Column("relation_label", sa.String(20), nullable=False),
        sa.Column("directed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("importance", sa.Float(), nullable=True),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("graph_id", "edge_id"),
        sa.UniqueConstraint(
            "graph_id",
            "source_node_id",
            "target_node_id",
            "relation",
            name="uq_knowledge_graph_edges_semantic",
        ),
    )
    op.create_index("ix_knowledge_graph_edges_graph_id", "knowledge_graph_edges", ["graph_id"])

    op.create_table(
        "knowledge_graph_learner_overlay",
        sa.Column("graph_id", sa.String(128), sa.ForeignKey("knowledge_graphs.graph_id"), nullable=False),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("learning_state", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("graph_id", "node_id"),
    )
    op.create_index(
        "ix_knowledge_graph_learner_overlay_learner_id",
        "knowledge_graph_learner_overlay",
        ["learner_id"],
    )

    op.create_table(
        "knowledge_graph_events",
        sa.Column("event_id", sa.String(160), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("graph_id", sa.String(128), nullable=False),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=True),
        sa.Column("new_revision", sa.Integer(), nullable=True),
        sa.Column("patch", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_graph_events_learner_id", "knowledge_graph_events", ["learner_id"])
    op.create_index("ix_knowledge_graph_events_graph_id", "knowledge_graph_events", ["graph_id"])
    op.create_index("ix_knowledge_graph_events_task_id", "knowledge_graph_events", ["task_id"])


def downgrade() -> None:
    op.drop_table("knowledge_graph_events")
    op.drop_table("knowledge_graph_learner_overlay")
    op.drop_table("knowledge_graph_edges")
    op.drop_table("knowledge_graph_nodes")
    op.drop_table("knowledge_graphs")
    op.drop_table("agent_task_sidecars")
    op.drop_column("agent_tasks", "adaptive_result")
    op.drop_column("agent_tasks", "graph_version")
