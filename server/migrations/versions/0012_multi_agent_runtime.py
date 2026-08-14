"""Add the multi-agent runtime state layer.

Four tables become the system's only source of truth (learning_profile,
learning_evidence, session_state, skill_registry), plus the goal-stack undo log
and the decision trace that makes every routing choice inspectable.
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_multi_agent_runtime"
down_revision = "0011_table_view_metadata"
branch_labels = None
depends_on = None


def _json():
    return sa.JSON()


def upgrade() -> None:
    # --- learning_evidence becomes the append-only runtime ledger -----------
    op.add_column("learning_evidence", sa.Column("task_id", sa.String(96), nullable=True))
    op.add_column(
        "learning_evidence",
        sa.Column("knowledge_point", sa.String(160), nullable=False, server_default=""),
    )
    op.add_column(
        "learning_evidence",
        sa.Column("signal", sa.String(48), nullable=False, server_default=""),
    )
    op.add_column(
        "learning_evidence",
        sa.Column("source_agent", sa.String(96), nullable=False, server_default=""),
    )
    op.add_column(
        "learning_evidence",
        sa.Column("payload", _json(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "learning_evidence",
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "learning_evidence",
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_learning_evidence_task_id", "learning_evidence", ["task_id"])
    op.create_index(
        "ix_learning_evidence_knowledge_point", "learning_evidence", ["knowledge_point"]
    )
    op.create_index("ix_learning_evidence_task", "learning_evidence", ["task_id", "seq"])
    # A unique index, not a table constraint: SQLite has no ALTER TABLE ADD
    # CONSTRAINT, and this table already exists.
    op.create_index(
        "uq_learning_evidence_learner_seq",
        "learning_evidence",
        ["learner_id", "seq"],
        unique=True,
    )

    # --- learning_profile ---------------------------------------------------
    op.create_table(
        "learning_profile",
        sa.Column("id", sa.String(224), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("knowledge_point_id", sa.String(160), nullable=False),
        sa.Column("knowledge_point", sa.String(300), nullable=False, server_default=""),
        sa.Column("mastery", sa.Float(), nullable=False, server_default="0.35"),
        sa.Column("learning_state", sa.String(48), nullable=False, server_default="unknown"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("my_questions", _json(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("recent_performance", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_studied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_step", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("misconceptions", _json(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("prerequisites", _json(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("difficulty", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("review_priority", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stability", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_agent", sa.String(96), nullable=False, server_default=""),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("override_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_evidence_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "learner_id", "knowledge_point_id", name="uq_learning_profile_learner_point"
        ),
    )
    op.create_index("ix_learning_profile_learner_id", "learning_profile", ["learner_id"])
    op.create_index(
        "ix_learning_profile_learner_priority",
        "learning_profile",
        ["learner_id", "review_priority"],
    )
    op.create_index(
        "ix_learning_profile_learner_due", "learning_profile", ["learner_id", "review_due_at"]
    )

    # --- session_state ------------------------------------------------------
    op.create_table(
        "session_state",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("task_id", sa.String(96), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("runtime_status", sa.String(32), nullable=False, server_default="PLANNING"),
        sa.Column("goal_stack", _json(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("plan", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("budget", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", name="uq_session_state_task"),
    )
    op.create_index("ix_session_state_learner_id", "session_state", ["learner_id"])
    op.create_index(
        "ix_session_state_learner_status", "session_state", ["learner_id", "runtime_status"]
    )

    op.create_table(
        "session_state_events",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "session_state_id", sa.String(128), sa.ForeignKey("session_state.id"), nullable=False
        ),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("op", sa.String(32), nullable=False),
        sa.Column("before", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("after", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_state_id", "sequence", name="uq_session_state_events_seq"),
    )
    op.create_index(
        "ix_session_state_events_session_state_id", "session_state_events", ["session_state_id"]
    )

    # --- skill_registry -----------------------------------------------------
    op.create_table(
        "skill_registry",
        sa.Column("skill_id", sa.String(160), primary_key=True),
        sa.Column("learner_id", sa.String(64), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="system"),
        sa.Column("display_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("capabilities", _json(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("input_schema", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("output_schema", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("preconditions", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("cost", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("ownership", sa.String(32), nullable=False, server_default="dedicated"),
        sa.Column("provider", sa.String(96), nullable=False, server_default=""),
        sa.Column("version", sa.String(48), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("checksum", sa.String(128), nullable=False, server_default=""),
        sa.Column("metadata", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_skill_registry_learner_id", "skill_registry", ["learner_id"])
    op.create_index("ix_skill_registry_source_enabled", "skill_registry", ["source", "enabled"])

    # --- decision_trace -----------------------------------------------------
    op.create_table(
        "decision_trace",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("task_id", sa.String(96), nullable=False),
        sa.Column("execution_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("goal", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("candidates", _json(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("selected", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_ids", _json(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("profile_before", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("profile_after", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("guardrail_state", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("outcome", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("replan_of", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "step", name="uq_decision_trace_task_step"),
    )
    op.create_index("ix_decision_trace_learner_id", "decision_trace", ["learner_id"])
    op.create_index("ix_decision_trace_task_id", "decision_trace", ["task_id"])
    op.create_index("ix_decision_trace_replan_of", "decision_trace", ["replan_of"])
    op.create_index("ix_decision_trace_task_created", "decision_trace", ["task_id", "created_at"])
    op.create_index("ix_decision_trace_execution", "decision_trace", ["execution_id", "step"])


def downgrade() -> None:
    op.drop_table("decision_trace")
    op.drop_table("skill_registry")
    op.drop_table("session_state_events")
    op.drop_table("session_state")
    op.drop_table("learning_profile")

    op.drop_index("uq_learning_evidence_learner_seq", table_name="learning_evidence")
    op.drop_index("ix_learning_evidence_task", table_name="learning_evidence")
    op.drop_index("ix_learning_evidence_knowledge_point", table_name="learning_evidence")
    op.drop_index("ix_learning_evidence_task_id", table_name="learning_evidence")
    op.drop_column("learning_evidence", "observed_at")
    op.drop_column("learning_evidence", "seq")
    op.drop_column("learning_evidence", "payload")
    op.drop_column("learning_evidence", "source_agent")
    op.drop_column("learning_evidence", "signal")
    op.drop_column("learning_evidence", "knowledge_point")
    op.drop_column("learning_evidence", "task_id")
