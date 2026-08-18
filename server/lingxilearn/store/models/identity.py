"""Learner identity: who the learner is and how they authenticate."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


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
