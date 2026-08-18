"""Shared declarative base and ORM helpers.

Every domain model module imports :data:`Base` from here so the whole schema
shares a single ``Base.metadata`` — the one Alembic targets.  Keeping the
base in its own module is what lets the domain modules stay import-cycle-free:
cross-table foreign keys reference table names as strings, never classes.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass
