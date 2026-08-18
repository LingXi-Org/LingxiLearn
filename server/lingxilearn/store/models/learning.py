"""Learning and mastery-related models.

Contains models for learner mastery, evidence tracking, and learning profiles.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
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
    """One row per (learner, knowledge point) — the learner-visible study recommendation."""
    __tablename__ = "learning_profiles"
    __table_args__ = (
        UniqueConstraint("learner_id", "knowledge_point", name="uq_learning_profiles_learner_kp"),
    )

    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    knowledge_point: Mapped[str] = mapped_column(String(160), primary_key=True)
    last_evidence_seq: Mapped[int] = mapped_column(Integer, default=0)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


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