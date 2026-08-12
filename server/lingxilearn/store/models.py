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

    learner_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("learners.id"), primary_key=True
    )
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

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    intent: Mapped[dict] = mapped_column(JSON, default=dict)
    lecture_result: Mapped[dict] = mapped_column(JSON, default=dict)
    deck_result: Mapped[dict] = mapped_column(JSON, default=dict)
    quiz_result: Mapped[dict] = mapped_column(JSON, default=dict)
    handoff_result: Mapped[dict] = mapped_column(JSON, default=dict)
    user_messages: Mapped[list] = mapped_column(JSON, default=list)
    # Kept for backwards-compatible reads of tasks created before the subgraph
    # refactor. New code never creates or renders this artifact.
    visual_result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
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
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(64))
    agent: Mapped[str] = mapped_column(String(64), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
    __table_args__ = (
        UniqueConstraint("learner_id", "tag", name="uq_misconceptions_learner_tag"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    tag: Mapped[str] = mapped_column(String(128))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningEvidence(Base):
    """Canonical learner evidence; graph-local evidence ids are session-scoped."""

    __tablename__ = "learning_evidence"
    __table_args__ = (
        UniqueConstraint("session_id", "evidence_id", name="uq_learning_evidence_session_id"),
        Index("ix_learning_evidence_learner_created", "learner_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(192), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("sessions.id"), nullable=True, index=True
    )
    evidence_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text, default="")
    locator: Mapped[dict] = mapped_column(JSON, default=dict)
    value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    digest: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearningPreference(Base):
    """Per-learner preference document, shallow-merged by the service."""

    __tablename__ = "learning_preferences"

    learner_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("learners.id"), primary_key=True
    )
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

    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id"), primary_key=True
    )
    learner_id: Mapped[str] = mapped_column(String(64), index=True)
    mission_id: Mapped[str] = mapped_column(String(64))
    probe_score: Mapped[float] = mapped_column(Float, default=0.0)
    verify_score: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
