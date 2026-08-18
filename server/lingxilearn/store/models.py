"""Database schema.

Deliberately small.  LingxiGraph's checkpointer already owns the authoritative
run state; these tables own the things that must outlive a single run:

* who the learner is and what they have demonstrated (``mastery``),
* a durable, monotonically sequenced event log per session, which is what makes
  the SSE stream resumable rather than a fire-and-forget pipe.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Learner(Base):
    __tablename__ = "learners"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdentityUser(Base):
    """The verified LingxiIdentity subject mapped to one internal learner."""

    __tablename__ = "identity_users"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_identity_users_issuer_subject"),
        UniqueConstraint("learner_id", name="uq_identity_users_learner"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issuer: Mapped[str] = mapped_column(String(256))
    subject: Mapped[str] = mapped_column(String(256))
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearnerProfile(Base):
    """Small, extensible profile owned by LingxiLearn."""

    __tablename__ = "learner_profiles"

    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), primary_key=True)
    locale: Mapped[str] = mapped_column(String(32), default="zh-CN")
    level: Mapped[str] = mapped_column(String(64), default="undergraduate")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    pack_id: Mapped[str] = mapped_column(String(64))
    pack_version: Mapped[str] = mapped_column(String(32))
    mission_id: Mapped[str] = mapped_column(String(64))
    checkpoint_ns: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(24), default="created", index=True)
    """created | running | awaiting_learner | done | failed"""
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


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


class AgentExecution(Base):
    """Immutable-at-terminal projection of one StateGraph invocation."""

    __tablename__ = "agent_executions"
    __table_args__ = (
        Index("ix_agent_executions_task_created", "task_id", "created_at"),
        Index("ix_agent_executions_learner_created", "learner_id", "created_at"),
        Index("ix_agent_executions_turn_created", "turn_id", "created_at"),
        UniqueConstraint("schedule_id", "scheduled_for", name="uq_agent_executions_schedule_slot"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    turn_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    """The AgentTurn this invocation belongs to; null only for legacy rows."""
    parent_execution_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("agent_executions.id"), nullable=True
    )
    resumes_execution_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("agent_executions.id"), nullable=True
    )
    """Set when this execution resumes a paused one (e.g. HITL answer)."""
    trigger: Mapped[str] = mapped_column(String(48), default="agent-task")
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    graph_version: Mapped[str] = mapped_column(String(64), default="")
    workflow_state: Mapped[dict] = mapped_column(JSON, default=dict)
    trace_spans: Mapped[list] = mapped_column(JSON, default=list)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    schedule_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AgentRun(Base):
    """One real execution actor inside one execution (issue #18).

    A WorkItem is durable logical work; every actual provider attempt gets its
    own AgentRun, so a retry never reuses a previous attempt's identity.  The
    dispatcher is the single owner of this lifecycle.
    """

    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_execution", "execution_id", "start_sequence"),
        Index("ix_agent_runs_task_turn", "task_id", "turn_id"),
        Index("ix_agent_runs_work_item", "work_item_id"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    turn_id: Mapped[str] = mapped_column(String(128), nullable=True, index=True)
    execution_id: Mapped[str] = mapped_column(String(128), index=True)
    work_item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parent_agent_run_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("agent_runs.id"), nullable=True
    )
    provider_id: Mapped[str] = mapped_column(String(96))
    agent_display_name: Mapped[str] = mapped_column(String(200), default="")
    execution_kind: Mapped[str] = mapped_column(String(24), default="model")
    capability: Mapped[str] = mapped_column(String(96), default="")
    presentation_role: Mapped[str] = mapped_column(String(24), default="supporting")
    status: Mapped[str] = mapped_column(
        String(24), default="queued", index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safe_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SkillRun(Base):
    """One real use of a skill inside one AgentRun (issue #18)."""

    __tablename__ = "skill_runs"
    __table_args__ = (
        Index("ix_skill_runs_agent_run", "agent_run_id"),
        Index("ix_skill_runs_execution", "execution_id"),
        Index("ix_skill_runs_task_turn", "task_id", "turn_id"),
    )

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    agent_run_id: Mapped[str] = mapped_column(String(128), ForeignKey("agent_runs.id"), index=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    turn_id: Mapped[str] = mapped_column(String(128), nullable=True, index=True)
    execution_id: Mapped[str] = mapped_column(String(128), index=True)
    skill_id: Mapped[str] = mapped_column(String(160))
    display_name: Mapped[str] = mapped_column(String(200), default="")
    version: Mapped[str] = mapped_column(String(48), default="")
    checksum: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AgentInteraction(Base):
    """A durable structured HITL interaction (issue #18).

    The checkpoint stores only the opaque interaction id; the full structured
    request and its answers live here so ``QuestionDisplay`` and
    ``InteractionCardRecap`` can be rebuilt after refresh.
    """

    __tablename__ = "agent_interactions"
    __table_args__ = (
        Index("ix_agent_interactions_task_turn", "task_id", "turn_id"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    turn_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    execution_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    purpose: Mapped[str] = mapped_column(String(32), default="clarification")
    presentation: Mapped[str] = mapped_column(String(24), default="question")
    blocking: Mapped[bool] = mapped_column(Boolean, default=True)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    """Whitelisted InteractionRequest schema only — never checkpoint state."""
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    reason_code: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentInteractionAnswer(Base):
    """One idempotent structured answer to an interaction."""

    __tablename__ = "agent_interaction_answers"
    __table_args__ = (
        UniqueConstraint("interaction_id", "idempotency_key", name="uq_interaction_answer_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interaction_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("agent_interactions.id"), index=True
    )
    answers: Mapped[list] = mapped_column(JSON, default=list)
    idempotency_key: Mapped[str] = mapped_column(String(192))
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


class RunEvent(Base):
    """The durable projection log. SSE serves from here, never from the live run."""

    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_run_events_session_sequence"),
        Index("ix_run_events_session_sequence", "session_id", "sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(48))
    node: Mapped[str] = mapped_column(String(64), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Mastery(Base):
    """Cross-session learner model. Every score is backed by counted evidence."""

    __tablename__ = "mastery"
    __table_args__ = (UniqueConstraint("learner_id", "concept", name="uq_mastery_learner_concept"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    concept: Mapped[str] = mapped_column(String(96))
    score: Mapped[float] = mapped_column(Float, default=0.35)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Misconception(Base):
    """Aggregated misconception observations for one learner."""

    __tablename__ = "misconceptions"
    __table_args__ = (UniqueConstraint("learner_id", "tag", name="uq_misconceptions_learner_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    tag: Mapped[str] = mapped_column(String(128))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningEvidence(Base):
    """Canonical, append-only learner evidence.

    This is the *only* thing an agent may produce about a learner.  There is
    deliberately no update or delete path anywhere in the repository: the
    state_updater tracks how far it has consumed via
    ``LearningProfile.last_evidence_seq`` instead of stamping rows here, which
    is what keeps the ledger append-only in practice and not just by
    convention.

    ``seq`` is monotonic *per learner* (see ``Repository.append_learning_evidence``);
    that is the ordering state_updater needs, and it avoids depending on a
    database sequence that SQLite does not have.
    """

    __tablename__ = "learning_evidence"
    __table_args__ = (
        UniqueConstraint("session_id", "evidence_id", name="uq_learning_evidence_session_id"),
        # A unique *index* rather than a table constraint: SQLite cannot ALTER a
        # constraint in, and this is added to an existing table by migration.
        Index("uq_learning_evidence_learner_seq", "learner_id", "seq", unique=True),
        Index("ix_learning_evidence_learner_created", "learner_id", "created_at"),
        Index("ix_learning_evidence_task", "task_id", "seq"),
    )

    id: Mapped[str] = mapped_column(String(192), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("sessions.id"), nullable=True, index=True
    )
    task_id: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    evidence_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text, default="")
    locator: Mapped[dict] = mapped_column(JSON, default=dict)
    value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    digest: Mapped[str] = mapped_column(String(128), default="")
    # --- runtime evidence columns -----------------------------------------
    knowledge_point: Mapped[str] = mapped_column(String(160), default="", index=True)
    signal: Mapped[str] = mapped_column(String(48), default="")
    source_agent: Mapped[str] = mapped_column(String(96), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearningProfile(Base):
    """One row per (learner, knowledge point) — the learner-visible study record.

    Every agent may read this table.  **No agent may write it.**  The single
    writer is ``lingxilearn.state.profile_writer.ProfileWriter``, which only
    accepts changes that cite ``learning_evidence`` rows.  That rule is
    enforced by ``tests/test_profile_write_guard.py``, not by comments.
    """

    __tablename__ = "learning_profile"
    __table_args__ = (
        UniqueConstraint(
            "learner_id", "knowledge_point_id", name="uq_learning_profile_learner_point"
        ),
        Index("ix_learning_profile_learner_priority", "learner_id", "review_priority"),
        Index("ix_learning_profile_learner_due", "learner_id", "review_due_at"),
    )

    id: Mapped[str] = mapped_column(String(224), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    knowledge_point_id: Mapped[str] = mapped_column(String(160))

    # --- learner-visible columns ------------------------------------------
    knowledge_point: Mapped[str] = mapped_column(String(300), default="")
    mastery: Mapped[float] = mapped_column(Float, default=0.35)
    learning_state: Mapped[str] = mapped_column(String(48), default="unknown")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    my_questions: Mapped[list] = mapped_column(JSON, default=list)
    recent_performance: Mapped[dict] = mapped_column(JSON, default=dict)
    last_studied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_step: Mapped[dict] = mapped_column(JSON, default=dict)
    """Clickable entry point: {action_id, capability, label, params, rationale}."""

    # --- system columns ----------------------------------------------------
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    misconceptions: Mapped[list] = mapped_column(JSON, default=list)
    prerequisites: Mapped[list] = mapped_column(JSON, default=list)
    difficulty: Mapped[float] = mapped_column(Float, default=0.5)
    review_priority: Mapped[float] = mapped_column(Float, default=0.0)
    stability: Mapped[float] = mapped_column(Float, default=0.0)
    source_agent: Mapped[str] = mapped_column(String(96), default="")
    revision: Mapped[int] = mapped_column(Integer, default=0)
    override_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    last_evidence_seq: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SessionState(Base):
    """The goal stack and run state machine for one learner conversation."""

    __tablename__ = "session_state"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_session_state_task"),
        Index("ix_session_state_learner_status", "learner_id", "runtime_status"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    task_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    runtime_status: Mapped[str] = mapped_column(String(32), default="PLANNING")
    goal_stack: Mapped[list] = mapped_column(JSON, default=list)
    """Bottom-up: long-term goal → current goal → interrupt goals."""
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    budget: Mapped[dict] = mapped_column(JSON, default=dict)
    interjections: Mapped[list] = mapped_column(JSON, default=list)
    board: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SessionStateEvent(Base):
    """Undo log for goal-stack operations, so routing decisions stay revocable."""

    __tablename__ = "session_state_events"
    __table_args__ = (
        UniqueConstraint("session_state_id", "sequence", name="uq_session_state_events_seq"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_state_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("session_state.id"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    op: Mapped[str] = mapped_column(String(32))
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SkillRegistryEntry(Base):
    """What each skill can do, what it costs, and what must hold before it runs."""

    __tablename__ = "skill_registry"
    __table_args__ = (Index("ix_skill_registry_source_enabled", "source", "enabled"),)

    skill_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    learner_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    """Set only for personal/forged skills; system skills are shared by everyone."""
    source: Mapped[str] = mapped_column(String(32), default="system")
    display_name: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    preconditions: Mapped[dict] = mapped_column(JSON, default=dict)
    cost: Mapped[dict] = mapped_column(JSON, default=dict)
    ownership: Mapped[str] = mapped_column(String(32), default="dedicated")
    provider: Mapped[str] = mapped_column(String(96), default="")
    version: Mapped[str] = mapped_column(String(48), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    checksum: Mapped[str] = mapped_column(String(128), default="")
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class DecisionTrace(Base):
    """One orchestrator decision: what was considered, what won, and why."""

    __tablename__ = "decision_trace"
    __table_args__ = (
        UniqueConstraint("task_id", "step", name="uq_decision_trace_task_step"),
        Index("ix_decision_trace_task_created", "task_id", "created_at"),
        Index("ix_decision_trace_execution", "execution_id", "step"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    task_id: Mapped[str] = mapped_column(String(96), index=True)
    execution_id: Mapped[str] = mapped_column(String(128), default="")
    step: Mapped[int] = mapped_column(Integer, default=0)
    goal: Mapped[dict] = mapped_column(JSON, default=dict)
    candidates: Mapped[list] = mapped_column(JSON, default=list)
    selected: Mapped[dict] = mapped_column(JSON, default=dict)
    rationale: Mapped[str] = mapped_column(Text, default="")
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    profile_before: Mapped[dict] = mapped_column(JSON, default=dict)
    profile_after: Mapped[dict] = mapped_column(JSON, default=dict)
    guardrail_state: Mapped[dict] = mapped_column(JSON, default=dict)
    outcome: Mapped[dict] = mapped_column(JSON, default=dict)
    replan_of: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    """Non-null marks this decision as a replan of an earlier one."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearningPreference(Base):
    """Per-learner preference document, shallow-merged by the service."""

    __tablename__ = "learning_preferences"

    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class LearningEvent(Base):
    """Append-only, idempotent learning event separate from the SSE projection."""

    __tablename__ = "learning_events"
    __table_args__ = (
        UniqueConstraint(
            "learner_id", "idempotency_key", name="uq_learning_events_learner_idempotency"
        ),
        Index("ix_learning_events_learner_created", "learner_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("sessions.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(96))
    idempotency_key: Mapped[str] = mapped_column(String(192))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReportRecord(Base):
    """Finished learning reports, kept so a learner can revisit past sessions."""

    __tablename__ = "reports"

    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), index=True)
    mission_id: Mapped[str] = mapped_column(String(64))
    probe_score: Mapped[float] = mapped_column(Float, default=0.0)
    verify_score: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Native Sim non-workflow workspace projection
# ---------------------------------------------------------------------------


class Workspace(Base):
    """The single private workspace projected for one Lingxi learner."""

    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("learner_id", name="uq_workspaces_learner"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), default="灵犀智学")
    appearance: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspacePinnedItem(Base):
    """Learner-owned pins shared by the reused Sim resource lists."""

    __tablename__ = "workspace_pinned_items"
    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "workspace_id",
            "resource_type",
            "resource_id",
            name="uq_workspace_pinned_item",
        ),
        Index(
            "ix_workspace_pinned_items_workspace_type",
            "workspace_id",
            "resource_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("workspaces.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(String(255))
    pinned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkspaceFolder(Base):
    __tablename__ = "workspace_folders"
    __table_args__ = (
        UniqueConstraint("workspace_id", "parent_id", "name", name="uq_workspace_folder_name"),
        Index("ix_workspace_folders_workspace_archived", "workspace_id", "archived"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("workspaces.id"), index=True)
    parent_id: Mapped[str | None] = mapped_column(
        String(96), ForeignKey("workspace_folders.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceFile(Base):
    __tablename__ = "workspace_files"
    __table_args__ = (
        Index("ix_workspace_files_workspace_archived", "workspace_id", "archived"),
        Index("ix_workspace_files_workspace_folder", "workspace_id", "folder_id"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("workspaces.id"), index=True)
    folder_id: Mapped[str | None] = mapped_column(
        String(96), ForeignKey("workspace_folders.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(160), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    path: Mapped[str] = mapped_column(String(1024), default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceUploadSession(Base):
    """Durable metadata for a resumable local upload transfer."""

    __tablename__ = "workspace_upload_sessions"
    __table_args__ = (Index("ix_workspace_upload_sessions_learner_status", "learner_id", "status"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("workspaces.id"), index=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(160), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)
    temp_key: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(24), default="uploading", index=True)
    file_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceTable(Base):
    __tablename__ = "workspace_tables"
    __table_args__ = (Index("ix_workspace_tables_workspace_archived", "workspace_id", "archived"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceTableColumn(Base):
    __tablename__ = "workspace_table_columns"
    __table_args__ = (
        UniqueConstraint("table_id", "key", name="uq_workspace_table_column_key"),
        Index("ix_workspace_table_columns_table_position", "table_id", "position"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    table_id: Mapped[str] = mapped_column(String(96), ForeignKey("workspace_tables.id"), index=True)
    key: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(24), default="string")
    position: Mapped[int] = mapped_column(Integer, default=0)
    options: Mapped[dict] = mapped_column(JSON, default=dict)


class WorkspaceTableRow(Base):
    __tablename__ = "workspace_table_rows"
    __table_args__ = (Index("ix_workspace_table_rows_table_position", "table_id", "position"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    table_id: Mapped[str] = mapped_column(String(96), ForeignKey("workspace_tables.id"), index=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceTableView(Base):
    __tablename__ = "workspace_table_views"
    __table_args__ = (UniqueConstraint("table_id", "name", name="uq_workspace_table_view_name"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    table_id: Mapped[str] = mapped_column(String(96), ForeignKey("workspace_tables.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeBase(Base):
    __tablename__ = "workspace_knowledge_bases"
    __table_args__ = (
        Index("ix_workspace_knowledge_bases_learner_archived", "learner_id", "archived"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeDocument(Base):
    __tablename__ = "workspace_knowledge_documents"
    __table_args__ = (
        Index("ix_workspace_knowledge_documents_base_archived", "base_id", "archived"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    base_id: Mapped[str] = mapped_column(
        String(96), ForeignKey("workspace_knowledge_bases.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(160), default="text/plain")
    content: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeChunk(Base):
    __tablename__ = "workspace_knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_workspace_knowledge_chunk_ordinal"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(96), ForeignKey("workspace_knowledge_documents.id"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class KnowledgeTag(Base):
    __tablename__ = "workspace_knowledge_tags"
    __table_args__ = (UniqueConstraint("base_id", "name", name="uq_workspace_knowledge_tag_name"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    base_id: Mapped[str] = mapped_column(
        String(96), ForeignKey("workspace_knowledge_bases.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    tag_slot: Mapped[str] = mapped_column(String(32), default="")
    field_type: Mapped[str] = mapped_column(String(32), default="string")


class KnowledgeDocumentTag(Base):
    __tablename__ = "workspace_knowledge_document_tags"
    document_id: Mapped[str] = mapped_column(
        String(96), ForeignKey("workspace_knowledge_documents.id"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        String(96), ForeignKey("workspace_knowledge_tags.id"), primary_key=True
    )
    value: Mapped[str] = mapped_column(Text, default="")


class PersonalSkill(Base):
    __tablename__ = "workspace_personal_skills"
    __table_args__ = (
        UniqueConstraint("learner_id", "name", name="uq_workspace_personal_skill_name"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceActivityEvent(Base):
    __tablename__ = "workspace_activity_events"
    __table_args__ = (
        Index("ix_workspace_activity_events_learner_created", "learner_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    kind: Mapped[str] = mapped_column(String(96))
    resource_type: Mapped[str] = mapped_column(String(64), default="")
    resource_id: Mapped[str] = mapped_column(String(96), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
