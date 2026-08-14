"""Persist LingxiGraph runtime projections, executions and approved schedules.

The historical revision id is immutable because existing databases already
record it in ``alembic_version``; the schema is part of the single LingxiLearn
runtime and is not a second Sim backend.
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_sim_runtime_semantics"
down_revision = "0007_native_workspace"
branch_labels = None
depends_on = None


def _json():
    return sa.JSON()


def upgrade() -> None:
    op.add_column("agent_tasks", sa.Column("current_execution_id", sa.String(128), nullable=True))
    op.add_column("agent_tasks", sa.Column("latest_execution_id", sa.String(128), nullable=True))
    op.create_index("ix_agent_tasks_current_execution_id", "agent_tasks", ["current_execution_id"])
    op.create_index("ix_agent_tasks_latest_execution_id", "agent_tasks", ["latest_execution_id"])
    op.add_column("agent_task_events", sa.Column("execution_id", sa.String(128), nullable=True))
    op.add_column("agent_task_events", sa.Column("runtime", _json(), nullable=False, server_default=sa.text("'{}'")))
    op.create_index("ix_agent_task_events_execution_id", "agent_task_events", ["execution_id", "sequence"])
    op.create_table(
        "agent_executions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("trigger", sa.String(48), nullable=False, server_default="agent-task"),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("graph_version", sa.String(64), nullable=False, server_default=""),
        sa.Column("workflow_state", _json(), nullable=False),
        sa.Column("trace_spans", _json(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("schedule_id", sa.String(128), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("schedule_id", "scheduled_for", name="uq_agent_executions_schedule_slot"),
    )
    op.create_index("ix_agent_executions_task_id", "agent_executions", ["task_id"])
    op.create_index("ix_agent_executions_learner_id", "agent_executions", ["learner_id"])
    op.create_index("ix_agent_executions_schedule_id", "agent_executions", ["schedule_id"])
    op.create_index("ix_agent_executions_task_created", "agent_executions", ["task_id", "created_at"])
    op.create_index("ix_agent_executions_learner_created", "agent_executions", ["learner_id", "created_at"])
    op.create_table(
        "agent_schedules",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("source_task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=True),
        sa.Column("proposal_id", sa.String(128), nullable=False, unique=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("cron", sa.String(128), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("inputs_snapshot", _json(), nullable=False),
        sa.Column("resources_snapshot", _json(), nullable=False),
        sa.Column("graph_version", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="proposed"),
        sa.Column("approval_scope", sa.String(24), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_schedules_learner_id", "agent_schedules", ["learner_id"])
    op.create_index("ix_agent_schedules_source_task_id", "agent_schedules", ["source_task_id"])
    op.create_index("ix_agent_schedules_status", "agent_schedules", ["status"])
    op.create_index("ix_agent_schedules_due", "agent_schedules", ["status", "next_run_at"])
    op.create_table(
        "agent_schedule_runs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("schedule_id", sa.String(128), sa.ForeignKey("agent_schedules.id"), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execution_id", sa.String(128), sa.ForeignKey("agent_executions.id"), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="claimed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("schedule_id", "scheduled_for", name="uq_agent_schedule_runs_slot"),
    )
    op.create_index("ix_agent_schedule_runs_schedule_id", "agent_schedule_runs", ["schedule_id"])
    op.create_index("ix_agent_schedule_runs_status", "agent_schedule_runs", ["status"])
    op.create_index("ix_agent_schedule_runs_schedule", "agent_schedule_runs", ["schedule_id", "scheduled_for"])


def downgrade() -> None:
    op.drop_table("agent_schedule_runs")
    op.drop_table("agent_schedules")
    op.drop_table("agent_executions")
    op.drop_index("ix_agent_task_events_execution_id", table_name="agent_task_events")
    op.drop_column("agent_task_events", "runtime")
    op.drop_column("agent_task_events", "execution_id")
    op.drop_index("ix_agent_tasks_latest_execution_id", table_name="agent_tasks")
    op.drop_index("ix_agent_tasks_current_execution_id", table_name="agent_tasks")
    op.drop_column("agent_tasks", "latest_execution_id")
    op.drop_column("agent_tasks", "current_execution_id")
