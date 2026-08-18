"""Agent task aggregate: tasks, turns, work ledger and the durable event log.

Everything the V2 coordinator needs to outlive a single graph invocation:
the task thread itself, its immutable turns, the command inbox, work items
and their budgets, and the monotonically sequenced SSE projection log.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class AgentTask(Base):
    """A one-shot intent-routing task and its specialist outputs."""

    __tablename__ = "agent_tasks"
    __table_args__ = (
        Index(
            "uq_agent_tasks_learner_create_key",
            "learner_id",
            "create_idempotency_key",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    create_idempotency_key: Mapped[str | None] = mapped_column(
        String(192), nullable=True
    )
    create_payload_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, default="")
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_unread: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    resources: Mapped[list] = mapped_column(JSON, default=list)
    graph_version: Mapped[str] = mapped_column(String(32), default="difficult_knowledge.v2")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    intent: Mapped[dict] = mapped_column(JSON, default=dict)
    lecture_result: Mapped[dict] = mapped_column(JSON, default=dict)
    deck_result: Mapped[dict] = mapped_column(JSON, default=dict)
    quiz_result: Mapped[dict] = mapped_column(JSON, default=dict)
    adaptive_result: Mapped[dict] = mapped_column(JSON, default=dict)
    handoff_result: Mapped[dict] = mapped_column(JSON, default=dict)
    user_messages: Mapped[list] = mapped_column(JSON, default=list)
    # Kept for backwards-compatible reads of tasks created before the subgraph
    # refactor. New code never creates or renders this artifact.
    visual_result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    current_execution_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    latest_execution_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # Long-lived thread state, separate from the legacy one-shot ``status``.
    # ``status`` keeps its historical per-run terminal semantics until every
    # caller has moved to the thread model (issue #18 Stage 4).
    thread_status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AgentTurn(Base):
    """Immutable interaction turn owned by the V2 coordinator."""

    __tablename__ = "agent_turns"
    __table_args__ = (
        UniqueConstraint("task_id", "turn_index", name="uq_agent_turns_task_index"),
        Index("ix_agent_turns_task_status", "task_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    turn_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    phase: Mapped[str] = mapped_column(String(32), default="interpreting")
    goal_status: Mapped[str] = mapped_column(String(24), default="open")
    execution_mode: Mapped[str] = mapped_column(String(32), default="normal")
    revision: Mapped[int] = mapped_column(Integer, default=0)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CandidateSnapshot(Base):
    """The exact registry binding used by a plan revision."""

    __tablename__ = "candidate_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "turn_id",
            "plan_revision",
            "candidate_id",
            name="uq_candidate_snapshot_binding",
        ),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    turn_id: Mapped[str] = mapped_column(String(128), ForeignKey("agent_turns.id"), index=True)
    plan_revision: Mapped[int] = mapped_column(Integer, default=0)
    candidate_id: Mapped[str] = mapped_column(String(128), index=True)
    capability: Mapped[str] = mapped_column(String(96))
    knowledge_point_id: Mapped[str] = mapped_column(String(128), default="")
    skill_id: Mapped[str] = mapped_column(String(160), default="")
    skill_version: Mapped[str] = mapped_column(String(48), default="")
    skill_checksum: Mapped[str] = mapped_column(String(128), default="")
    provider: Mapped[str] = mapped_column(String(96), default="")
    registry_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommandInbox(Base):
    """Ordered, idempotent learner command queue."""

    __tablename__ = "command_inbox"
    __table_args__ = (
        UniqueConstraint("task_id", "idempotency_key", name="uq_command_inbox_task_key"),
        Index("ix_command_inbox_task_pending", "task_id", "consumed_at", "sequence"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    turn_id: Mapped[str] = mapped_column(String(128), ForeignKey("agent_turns.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(192))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkItem(Base):
    """Durable unit of provider work; replaces in-memory results."""

    __tablename__ = "work_items"
    __table_args__ = (
        UniqueConstraint("turn_id", "work_key", name="uq_work_items_turn_key"),
        Index("ix_work_items_claimable", "status", "lease_until"),
        Index("ix_work_items_task_revision", "task_id", "plan_revision"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    turn_id: Mapped[str] = mapped_column(String(128), ForeignKey("agent_turns.id"), index=True)
    work_key: Mapped[str] = mapped_column(String(160))
    plan_revision: Mapped[int] = mapped_column(Integer, default=0)
    candidate_id: Mapped[str] = mapped_column(String(128))
    capability: Mapped[str] = mapped_column(String(96))
    skill_id: Mapped[str] = mapped_column(String(160), default="")
    skill_version: Mapped[str] = mapped_column(String(48), default="")
    skill_checksum: Mapped[str] = mapped_column(String(128), default="")
    provider: Mapped[str] = mapped_column(String(96), default="")
    knowledge_point_id: Mapped[str] = mapped_column(String(128), default="")
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(192), unique=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reserved_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reserved_heavy: Mapped[int] = mapped_column(Integer, default=0)
    reserved_wall_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkDependency(Base):
    __tablename__ = "work_dependencies"
    __table_args__ = (UniqueConstraint("work_id", "depends_on_id", name="uq_work_dependency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_id: Mapped[str] = mapped_column(String(128), ForeignKey("work_items.id"), index=True)
    depends_on_id: Mapped[str] = mapped_column(String(128), ForeignKey("work_items.id"), index=True)


class WorkResult(Base):
    __tablename__ = "work_results"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    work_id: Mapped[str] = mapped_column(String(128), ForeignKey("work_items.id"), unique=True)
    schema_id: Mapped[str] = mapped_column(String(128), default="")
    safe_summary: Mapped[str] = mapped_column(Text, default="")
    artifact_refs: Mapped[list] = mapped_column(JSON, default=list)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    output_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FactSnapshot(Base):
    """Immutable facts used by completion evaluation after a run resumes."""

    __tablename__ = "fact_snapshots"
    __table_args__ = (
        UniqueConstraint("task_id", "turn_id", "plan_revision", name="uq_fact_snapshot_revision"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    turn_id: Mapped[str] = mapped_column(String(128), ForeignKey("agent_turns.id"), index=True)
    plan_revision: Mapped[int] = mapped_column(Integer, default=0)
    facts: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    artifact_refs: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BudgetLedger(Base):
    __tablename__ = "budget_ledger"
    __table_args__ = (
        UniqueConstraint("task_id", "turn_id", "plan_revision", name="uq_budget_ledger_revision"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    turn_id: Mapped[str] = mapped_column(String(128), ForeignKey("agent_turns.id"), index=True)
    plan_revision: Mapped[int] = mapped_column(Integer)
    reserved_tokens: Mapped[int] = mapped_column(Integer, default=0)
    used_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reserved_heavy: Mapped[int] = mapped_column(Integer, default=0)
    used_heavy: Mapped[int] = mapped_column(Integer, default=0)
    reserved_wall_ms: Mapped[int] = mapped_column(Integer, default=0)
    used_wall_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TransactionalOutbox(Base):
    __tablename__ = "transactional_outbox"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_transactional_outbox_event_key"),
        Index("ix_transactional_outbox_pending", "published_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_key: Mapped[str] = mapped_column(String(192))
    task_id: Mapped[str] = mapped_column(String(96), index=True)
    turn_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    plan_revision: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(64))
    safe_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProjectionCursor(Base):
    __tablename__ = "projection_cursors"
    __table_args__ = (UniqueConstraint("learner_id", "projection", name="uq_projection_cursor"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    projection: Mapped[str] = mapped_column(String(96))
    last_event_id: Mapped[str] = mapped_column(String(128), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class QuizSubmission(Base):
    """The single durable submission allowed for one AgentTask."""

    __tablename__ = "quiz_submissions"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_quiz_submissions_task"),
        UniqueConstraint("submission_id", name="uq_quiz_submissions_submission"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    submission_id: Mapped[str] = mapped_column(String(128))
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    per_question: Mapped[list] = mapped_column(JSON, default=list)
    total_score: Mapped[float] = mapped_column(Float, default=0)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    handoff_reason: Mapped[str] = mapped_column(String(64), default="quiz_completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentTaskEvent(Base):
    """Durable SSE projection log for Agent Tasks."""

    __tablename__ = "agent_task_events"
    __table_args__ = (
        UniqueConstraint("task_id", "sequence", name="uq_agent_task_events_sequence"),
        Index("ix_agent_task_events_task_sequence", "task_id", "sequence"),
        Index("ix_agent_task_events_execution", "execution_id", "sequence"),
        Index(
            "ix_agent_task_events_task_protocol",
            "task_id",
            "protocol_version",
            "sequence",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(64))
    agent: Mapped[str] = mapped_column(String(64), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    runtime: Mapped[dict] = mapped_column(JSON, default=dict)
    # --- Mothership Stream V1 identity columns (issue #18) ------------------
    # V1 events always populate these; legacy V0 rows keep protocol_version=0
    # and null identity links.
    protocol_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    turn_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    skill_run_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentSchedule(Base):
    """Agent-proposed, learner-approved immutable schedule revision."""

    __tablename__ = "agent_schedules"
    __table_args__ = (Index("ix_agent_schedules_due", "status", "next_run_at"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    source_task_id: Mapped[str | None] = mapped_column(
        String(96), ForeignKey("agent_tasks.id"), nullable=True, index=True
    )
    proposal_id: Mapped[str] = mapped_column(String(128), unique=True)
    prompt: Mapped[str] = mapped_column(Text)
    cron: Mapped[str] = mapped_column(String(128))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    inputs_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    resources_snapshot: Mapped[list] = mapped_column(JSON, default=list)
    graph_version: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(24), default="proposed", index=True)
    approval_scope: Mapped[str | None] = mapped_column(String(24), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AgentScheduleRun(Base):
    """Deduplicated scheduler trigger record."""

    __tablename__ = "agent_schedule_runs"
    __table_args__ = (
        UniqueConstraint("schedule_id", "scheduled_for", name="uq_agent_schedule_runs_slot"),
        Index("ix_agent_schedule_runs_schedule", "schedule_id", "scheduled_for"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schedule_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("agent_schedules.id"), index=True
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    execution_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("agent_executions.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), default="claimed", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
