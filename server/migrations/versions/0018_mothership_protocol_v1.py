"""Canonical execution identities for the Mothership Stream V1 protocol (issue #18).

Adds AgentRun / SkillRun / AgentInteraction tables, links AgentExecution to
AgentTurn with resume relations, adds V1 identity columns to the event log, and
introduces the long-lived ``thread_status`` on AgentTask alongside the legacy
one-shot ``status``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_mothership_protocol_v1"
down_revision = "0017_agent_task_create_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_tasks",
        sa.Column("thread_status", sa.String(24), nullable=False, server_default="open"),
    )
    op.create_index("ix_agent_tasks_thread_status", "agent_tasks", ["thread_status"])

    op.add_column(
        "agent_executions", sa.Column("turn_id", sa.String(128), nullable=True)
    )
    op.add_column(
        "agent_executions", sa.Column("parent_execution_id", sa.String(128), nullable=True)
    )
    op.add_column(
        "agent_executions", sa.Column("resumes_execution_id", sa.String(128), nullable=True)
    )
    op.create_index("ix_agent_executions_turn_created", "agent_executions", ["turn_id", "created_at"])

    op.add_column(
        "agent_task_events",
        sa.Column("protocol_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("agent_task_events", sa.Column("turn_id", sa.String(128), nullable=True))
    op.add_column("agent_task_events", sa.Column("agent_run_id", sa.String(128), nullable=True))
    op.add_column("agent_task_events", sa.Column("skill_run_id", sa.String(160), nullable=True))
    op.create_index(
        "ix_agent_task_events_turn_id", "agent_task_events", ["turn_id"]
    )
    op.create_index(
        "ix_agent_task_events_agent_run_id", "agent_task_events", ["agent_run_id"]
    )
    op.create_index(
        "ix_agent_task_events_skill_run_id", "agent_task_events", ["skill_run_id"]
    )
    op.create_index(
        "ix_agent_task_events_task_protocol",
        "agent_task_events",
        ["task_id", "protocol_version", "sequence"],
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("turn_id", sa.String(128), nullable=True),
        sa.Column("execution_id", sa.String(128), nullable=False),
        sa.Column("work_item_id", sa.String(128), nullable=True),
        sa.Column(
            "parent_agent_run_id", sa.String(128), sa.ForeignKey("agent_runs.id"), nullable=True
        ),
        sa.Column("provider_id", sa.String(96), nullable=False),
        sa.Column("agent_display_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("execution_kind", sa.String(24), nullable=False, server_default="model"),
        sa.Column("capability", sa.String(96), nullable=False, server_default=""),
        sa.Column(
            "presentation_role", sa.String(24), nullable=False, server_default="supporting"
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_sequence", sa.Integer(), nullable=True),
        sa.Column("end_sequence", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_runs_task_id", "agent_runs", ["task_id"])
    op.create_index("ix_agent_runs_turn_id", "agent_runs", ["turn_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_execution", "agent_runs", ["execution_id", "start_sequence"])
    op.create_index("ix_agent_runs_task_turn", "agent_runs", ["task_id", "turn_id"])
    op.create_index("ix_agent_runs_work_item", "agent_runs", ["work_item_id"])

    op.create_table(
        "skill_runs",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column(
            "agent_run_id", sa.String(128), sa.ForeignKey("agent_runs.id"), nullable=False
        ),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("turn_id", sa.String(128), nullable=True),
        sa.Column("execution_id", sa.String(128), nullable=False),
        sa.Column("skill_id", sa.String(160), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("version", sa.String(48), nullable=False, server_default=""),
        sa.Column("checksum", sa.String(128), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_skill_runs_agent_run", "skill_runs", ["agent_run_id"])
    op.create_index("ix_skill_runs_task_id", "skill_runs", ["task_id"])
    op.create_index("ix_skill_runs_turn_id", "skill_runs", ["turn_id"])
    op.create_index("ix_skill_runs_status", "skill_runs", ["status"])
    op.create_index("ix_skill_runs_execution", "skill_runs", ["execution_id"])
    op.create_index("ix_skill_runs_task_turn", "skill_runs", ["task_id", "turn_id"])

    op.create_table(
        "agent_interactions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("turn_id", sa.String(128), nullable=True),
        sa.Column("execution_id", sa.String(128), nullable=True),
        sa.Column("agent_run_id", sa.String(128), nullable=True),
        sa.Column("purpose", sa.String(32), nullable=False, server_default="clarification"),
        sa.Column("presentation", sa.String(24), nullable=False, server_default="question"),
        sa.Column("blocking", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("request_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("reason_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_interactions_task_id", "agent_interactions", ["task_id"])
    op.create_index("ix_agent_interactions_turn_id", "agent_interactions", ["turn_id"])
    op.create_index("ix_agent_interactions_execution_id", "agent_interactions", ["execution_id"])
    op.create_index("ix_agent_interactions_agent_run_id", "agent_interactions", ["agent_run_id"])
    op.create_index("ix_agent_interactions_status", "agent_interactions", ["status"])
    op.create_index("ix_agent_interactions_task_turn", "agent_interactions", ["task_id", "turn_id"])

    op.create_table(
        "agent_interaction_answers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "interaction_id",
            sa.String(128),
            sa.ForeignKey("agent_interactions.id"),
            nullable=False,
        ),
        sa.Column("answers", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("idempotency_key", sa.String(192), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "interaction_id", "idempotency_key", name="uq_interaction_answer_key"
        ),
    )
    op.create_index(
        "ix_agent_interaction_answers_interaction_id",
        "agent_interaction_answers",
        ["interaction_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_interaction_answers_interaction_id", table_name="agent_interaction_answers"
    )
    op.drop_table("agent_interaction_answers")
    op.drop_index("ix_agent_interactions_status", table_name="agent_interactions")
    op.drop_index("ix_agent_interactions_task_turn", table_name="agent_interactions")
    op.drop_index("ix_agent_interactions_agent_run_id", table_name="agent_interactions")
    op.drop_index("ix_agent_interactions_execution_id", table_name="agent_interactions")
    op.drop_index("ix_agent_interactions_turn_id", table_name="agent_interactions")
    op.drop_index("ix_agent_interactions_task_id", table_name="agent_interactions")
    op.drop_table("agent_interactions")
    op.drop_index("ix_skill_runs_task_turn", table_name="skill_runs")
    op.drop_index("ix_skill_runs_execution", table_name="skill_runs")
    op.drop_index("ix_skill_runs_status", table_name="skill_runs")
    op.drop_index("ix_skill_runs_turn_id", table_name="skill_runs")
    op.drop_index("ix_skill_runs_task_id", table_name="skill_runs")
    op.drop_index("ix_skill_runs_agent_run", table_name="skill_runs")
    op.drop_table("skill_runs")
    op.drop_index("ix_agent_runs_work_item", table_name="agent_runs")
    op.drop_index("ix_agent_runs_task_turn", table_name="agent_runs")
    op.drop_index("ix_agent_runs_execution", table_name="agent_runs")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_turn_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_task_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_agent_task_events_task_protocol", table_name="agent_task_events")
    op.drop_index("ix_agent_task_events_skill_run_id", table_name="agent_task_events")
    op.drop_index("ix_agent_task_events_agent_run_id", table_name="agent_task_events")
    op.drop_index("ix_agent_task_events_turn_id", table_name="agent_task_events")
    op.drop_column("agent_task_events", "skill_run_id")
    op.drop_column("agent_task_events", "agent_run_id")
    op.drop_column("agent_task_events", "turn_id")
    op.drop_column("agent_task_events", "protocol_version")
    op.drop_index("ix_agent_executions_turn_created", table_name="agent_executions")
    op.drop_column("agent_executions", "resumes_execution_id")
    op.drop_column("agent_executions", "parent_execution_id")
    op.drop_column("agent_executions", "turn_id")
    op.drop_index("ix_agent_tasks_thread_status", table_name="agent_tasks")
    op.drop_column("agent_tasks", "thread_status")
