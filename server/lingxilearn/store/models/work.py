"""Work item and orchestration models.

Contains models for work items, dependencies, results, and orchestration state.
"""

from __future__ import annotations

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


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
    """Dependency relationships between work items."""
    __tablename__ = "work_dependencies"
    __table_args__ = (UniqueConstraint("work_id", "depends_on_id", name="uq_work_dependency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_id: Mapped[str] = mapped_column(String(128), ForeignKey("work_items.id"), index=True)
    depends_on_id: Mapped[str] = mapped_column(String(128), ForeignKey("work_items.id"), index=True)


class WorkResult(Base):
    """Results from completed work items."""
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
    """Budget tracking for agent execution."""
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


class SessionState(Base):
    """Undoable goal stack state for one session."""
    __tablename__ = "session_state"
    __table_args__ = (UniqueConstraint("session_id", name="uq_session_state_session"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"), index=True)
    goal_stack: Mapped[list] = mapped_column(JSON, default=list)
    active_goal_index: Mapped[int] = mapped_column(Integer, default=0)
    route_state: Mapped[dict] = mapped_column(JSON, default=dict)
    # For tracking which turn/execution created the current stack, and null identity links.
    protocol_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    turn_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    skill_run_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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