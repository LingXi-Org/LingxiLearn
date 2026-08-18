"""Structured tables inside the workspace (the Sim table/grid projection)."""

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
