"""Native Sim non-workflow workspace projection.

The single private workspace projected for one Lingxi learner: folders and
files, pins, resumable uploads, personal skills and the activity feed.
Structured tables live in :mod:`~.table`, the knowledge base in
:mod:`~.knowledge`.
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
