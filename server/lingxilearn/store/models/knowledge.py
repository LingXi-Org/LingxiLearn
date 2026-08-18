"""Knowledge base and document models.

Contains models for knowledge bases, documents, chunks, and tags.
"""

from __future__ import annotations

from datetime import datetime

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


class KnowledgeBase(Base):
    """Knowledge base for storing and organizing learning content."""
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
    """Document within a knowledge base."""
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
    """Chunked content from documents for efficient retrieval."""
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
    """Tags for organizing knowledge content."""
    __tablename__ = "workspace_knowledge_tags"
    __table_args__ = (UniqueConstraint("base_id", "name", name="uq_workspace_knowledge_tag_name"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    base_id: Mapped[str] = mapped_column(
        String(96), ForeignKey("workspace_knowledge_bases.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    tag_slot: Mapped[str] = mapped_column(String(64), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)