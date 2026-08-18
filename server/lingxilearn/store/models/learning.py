"""Learning domain models: sessions, mastery, evidence, profile and decisions.

These tables own what must outlive a single run: who the learner is and what
they have demonstrated (``mastery``), and a durable, monotonically sequenced
event log per session, which is what makes the SSE stream resumable rather
than a fire-and-forget pipe.
"""

from __future__ import annotations

from datetime import datetime
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
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


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
