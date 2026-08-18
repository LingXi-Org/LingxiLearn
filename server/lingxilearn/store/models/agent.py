"""Agent task and planning-related models.

Contains models for agent tasks, turns, candidate snapshots, and decision tracking.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
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