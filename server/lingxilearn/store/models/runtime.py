"""Multi-agent runtime models: executions, runs, skill runs and HITL.

Issue #18 identity tables — every actual provider attempt gets its own
AgentRun/SkillRun identity, plus the durable structured interactions that let
a HITL question survive a refresh.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


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
    execution_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    timeline_spans: Mapped[list] = mapped_column(JSON, default=list)
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
