"""Add the V2 turn, command inbox, work ledger and outbox primitives."""

from alembic import op
import sqlalchemy as sa

revision = "0016_orchestration_v2_ledger"
down_revision = "0015_agent_hold_board"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # V2 has one execution path.  Remove the pre-V2 sidecar table when
    # upgrading an existing database; no sidecar state is migrated.
    op.drop_table("agent_task_sidecars", if_exists=True)
    op.create_table(
        "agent_turns",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("phase", sa.String(32), nullable=False, server_default="interpreting"),
        sa.Column("goal_status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("execution_mode", sa.String(32), nullable=False, server_default="normal"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "turn_index", name="uq_agent_turns_task_index"),
    )
    op.create_index("ix_agent_turns_task_status", "agent_turns", ["task_id", "status"])
    op.create_table(
        "command_inbox",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("turn_id", sa.String(128), sa.ForeignKey("agent_turns.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(192), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "idempotency_key", name="uq_command_inbox_task_key"),
    )
    op.create_index("ix_command_inbox_task_pending", "command_inbox", ["task_id", "consumed_at", "sequence"])
    op.create_table(
        "work_items",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("turn_id", sa.String(128), sa.ForeignKey("agent_turns.id"), nullable=False),
        sa.Column("work_key", sa.String(160), nullable=False),
        sa.Column("plan_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_id", sa.String(128), nullable=False),
        sa.Column("capability", sa.String(96), nullable=False),
        sa.Column("skill_id", sa.String(160), nullable=False, server_default=""),
        sa.Column("skill_version", sa.String(48), nullable=False, server_default=""),
        sa.Column("skill_checksum", sa.String(128), nullable=False, server_default=""),
        sa.Column("provider", sa.String(96), nullable=False, server_default=""),
        sa.Column("knowledge_point_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("input_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(192), nullable=False, unique=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("confirmation_digest", sa.String(128)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("result_id", sa.String(128)),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_heavy", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_wall_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("turn_id", "work_key", name="uq_work_items_turn_key"),
    )
    op.create_index("ix_work_items_claimable", "work_items", ["status", "lease_until"])
    op.create_index("ix_work_items_task_revision", "work_items", ["task_id", "plan_revision"])
    op.create_table(
        "work_dependencies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_id", sa.String(128), sa.ForeignKey("work_items.id"), nullable=False),
        sa.Column("depends_on_id", sa.String(128), sa.ForeignKey("work_items.id"), nullable=False),
        sa.UniqueConstraint("work_id", "depends_on_id", name="uq_work_dependency"),
    )
    op.create_table(
        "work_results",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("work_id", sa.String(128), sa.ForeignKey("work_items.id"), nullable=False, unique=True),
        sa.Column("schema_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("safe_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("artifact_refs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("usage", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("output_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "budget_ledger",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("turn_id", sa.String(128), sa.ForeignKey("agent_turns.id"), nullable=False),
        sa.Column("plan_revision", sa.Integer(), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_heavy", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_heavy", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_wall_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_wall_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "turn_id", "plan_revision", name="uq_budget_ledger_revision"),
    )
    op.create_table(
        "transactional_outbox",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("event_key", sa.String(192), nullable=False, unique=True),
        sa.Column("task_id", sa.String(96), nullable=False),
        sa.Column("turn_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("plan_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("safe_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transactional_outbox_pending", "transactional_outbox", ["published_at", "created_at"])
    op.create_table(
        "candidate_snapshots",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("turn_id", sa.String(128), sa.ForeignKey("agent_turns.id"), nullable=False),
        sa.Column("plan_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_id", sa.String(128), nullable=False),
        sa.Column("capability", sa.String(96), nullable=False),
        sa.Column("knowledge_point_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("skill_id", sa.String(160), nullable=False, server_default=""),
        sa.Column("skill_version", sa.String(48), nullable=False, server_default=""),
        sa.Column("skill_checksum", sa.String(128), nullable=False, server_default=""),
        sa.Column("provider", sa.String(96), nullable=False, server_default=""),
        sa.Column("registry_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "turn_id", "plan_revision", "candidate_id", name="uq_candidate_snapshot_binding"),
    )
    op.create_index("ix_candidate_snapshots_task_id", "candidate_snapshots", ["task_id"])
    op.create_index("ix_candidate_snapshots_turn_id", "candidate_snapshots", ["turn_id"])
    op.create_index("ix_candidate_snapshots_candidate_id", "candidate_snapshots", ["candidate_id"])
    op.create_table(
        "fact_snapshots",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("turn_id", sa.String(128), sa.ForeignKey("agent_turns.id"), nullable=False),
        sa.Column("plan_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("facts", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("artifact_refs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "turn_id", "plan_revision", name="uq_fact_snapshot_revision"),
    )
    op.create_index("ix_fact_snapshots_task_id", "fact_snapshots", ["task_id"])
    op.create_index("ix_fact_snapshots_turn_id", "fact_snapshots", ["turn_id"])
    op.create_table(
        "projection_cursors",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("projection", sa.String(96), nullable=False),
        sa.Column("last_event_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("learner_id", "projection", name="uq_projection_cursor"),
    )


def downgrade() -> None:
    for table in (
        "projection_cursors", "fact_snapshots", "candidate_snapshots", "transactional_outbox", "budget_ledger",
        "work_results", "work_dependencies", "work_items", "command_inbox", "agent_turns",
    ):
        op.drop_table(table)
