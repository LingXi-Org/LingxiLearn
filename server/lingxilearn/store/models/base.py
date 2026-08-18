"""Database base and shared utilities.

All domain models share a single declarative Base to ensure Alembic metadata
remains the single source of truth for migrations.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """Get current UTC timestamp for ORM defaults."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models.
    
    All models across different domain modules inherit from this Base,
    ensuring they all contribute to the same metadata registry for
    Alembic autogenerate and migrations.
    """
    pass