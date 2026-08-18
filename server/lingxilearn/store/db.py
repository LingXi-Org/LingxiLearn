"""Database engine and session factory.

DB infrastructure only. Domain persistence has been moved to repositories/
modules. Use from lingxilearn.store.repositories import Repository for backward
compatibility during migration.

One rule worth stating because breaking it is the classic scaling mistake:
**never hold a database session open across a graph run.**  Resolve what you
need, release the connection, then stream.  A pool of 10 gated on model latency
caps you at 10 concurrent learners for no reason.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import Settings
from .models import Base


__all__ = ["Database"]


logger = logging.getLogger(__name__)


# SQLite is the supported zero-setup development database.  Older local
# checkouts were created with ``Base.metadata.create_all`` before the latest
# migrations were added, so ``create_all`` alone cannot repair them.  Keep the
# compatibility DDL explicit and small: production PostgreSQL still uses the
# normal Alembic chain, while a local SQLite restart upgrades the existing
# file in place without discarding learner data.
_SQLITE_SCHEMA_HEAD = "0018_mothership_protocol_v1"
_SQLITE_COMPAT_COLUMNS: dict[str, dict[str, str]] = {
    "agent_tasks": {
        "create_idempotency_key": "VARCHAR(192)",
        "create_payload_digest": "VARCHAR(64)",
        "title": "TEXT NOT NULL DEFAULT ''",
        "is_pinned": "BOOLEAN NOT NULL DEFAULT 0",
        "is_unread": "BOOLEAN NOT NULL DEFAULT 0",
        "deleted_at": "DATETIME",
        "resources": "JSON NOT NULL DEFAULT '[]'",
        "graph_version": "VARCHAR(32) NOT NULL DEFAULT 'difficult_knowledge.v2'",
        "deck_result": "JSON NOT NULL DEFAULT '{}'",
        "quiz_result": "JSON NOT NULL DEFAULT '{}'",
        "adaptive_result": "JSON NOT NULL DEFAULT '{}'",
        "handoff_result": "JSON NOT NULL DEFAULT '{}'",
        "user_messages": "JSON NOT NULL DEFAULT '[]'",
        "current_execution_id": "VARCHAR(128)",
        "latest_execution_id": "VARCHAR(128)",
        # 0018: the long-lived thread status alongside the legacy one-shot one.
        "thread_status": "VARCHAR(24) NOT NULL DEFAULT 'open'",
    },
    "agent_task_events": {
        "execution_id": "VARCHAR(128)",
        "runtime": "JSON NOT NULL DEFAULT '{}'",
        # 0018: protocol version + canonical identity on the event log.
        "protocol_version": "INTEGER NOT NULL DEFAULT 0",
        "turn_id": "VARCHAR(128)",
        "agent_run_id": "VARCHAR(128)",
        "skill_run_id": "VARCHAR(160)",
    },
    "agent_executions": {
        # 0018: link an execution to its turn and to the execution it resumes.
        "turn_id": "VARCHAR(128)",
        "parent_execution_id": "VARCHAR(128)",
        "resumes_execution_id": "VARCHAR(128)",
    },
    "workspace_knowledge_tags": {
        "tag_slot": "VARCHAR(32) NOT NULL DEFAULT ''",
    },
    "workspace_table_views": {
        "is_default": "BOOLEAN NOT NULL DEFAULT 0",
        "created_by": "VARCHAR(64)",
    },
    "learning_evidence": {
        "task_id": "VARCHAR(96)",
        "knowledge_point": "VARCHAR(160) NOT NULL DEFAULT ''",
        "signal": "VARCHAR(48) NOT NULL DEFAULT ''",
        "source_agent": "VARCHAR(96) NOT NULL DEFAULT ''",
        "payload": "JSON NOT NULL DEFAULT '{}'",
        "seq": "INTEGER NOT NULL DEFAULT 0",
        "observed_at": "DATETIME",
    },
    "session_state": {
        "board": "JSON NOT NULL DEFAULT '{}'",
    },
    "work_items": {
        "reserved_tokens": "INTEGER NOT NULL DEFAULT 0",
        "reserved_heavy": "INTEGER NOT NULL DEFAULT 0",
        "reserved_wall_ms": "INTEGER NOT NULL DEFAULT 0",
    },
}


def _repair_sqlite_schema(connection: Any) -> None:
    """Repair SQLite schema for compatibility with older checkouts."""
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    repaired: list[str] = []

    for table_name, columns in _SQLITE_COMPAT_COLUMNS.items():
        if table_name not in existing_tables:
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, ddl in columns.items():
            if column_name in existing_columns:
                continue
            connection.exec_driver_sql(
                f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {ddl}'
            )
            repaired.append(f"{table_name}.{column_name}")

    # ``create_all`` does not create indexes for columns added above.  Let
    # SQLAlchemy create every declared index after the column repair; existing
    # indexes are left untouched.
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            index.create(connection, checkfirst=True)

    # A create_all-created SQLite file has no migration marker.  Once the
    # current model schema has been materialised, mark it at the same head as
    # Alembic so a later explicit ``alembic upgrade head`` is a no-op rather
    # than replaying migrations over already-existing tables.
    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS alembic_version (version VARCHAR(32) NOT NULL)"
    )
    connection.exec_driver_sql(
        f"INSERT OR IGNORE INTO alembic_version (version) VALUES ('{_SQLITE_SCHEMA_HEAD}')"
    )

    if repaired:
        logger.info("Repaired SQLite schema: %s", ", ".join(repaired))


class Database:
    """Database engine and session factory only.

    Does not contain domain persistence logic - that is in repository modules.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = create_async_engine(
            settings.resolved_database_url,
            pool_pre_ping=True,
            echo=settings.database_echo,
        )

        # SQLite WAL mode for better concurrency in development
        if self.engine.url.drivername.startswith("sqlite"):
            @event.listens_for(self.engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        # Event producers include the graph stream and lifecycle
        # handlers. They may append to one task concurrently. Serialise the
        # sequence allocation in-process; PostgreSQL row locking below covers
        # separate workers as well.
        self._agent_event_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def agent_event_lock(self, task_id: str) -> asyncio.Lock:
        """Get lock for serializing event sequence allocation within a task."""
        return self._agent_event_locks[task_id]

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Provide a database session for use in a transaction."""
        async with self.factory() as session:
            yield session

    async def create_all(self) -> None:
        """Only for tests and the SQLite quick-start; production runs Alembic."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def ensure_sqlite_schema(self) -> None:
        """Create or repair the local SQLite schema without dropping data."""
        if not self.engine.url.drivername.startswith("sqlite"):
            return
        await self.create_all()
        async with self.engine.begin() as conn:
            await conn.run_sync(_repair_sqlite_schema)

    async def ping(self) -> bool:
        """Check if database connection is alive."""
        async with self.engine.connect() as conn:
            await conn.execute(select(1))
        return True

    async def dispose(self) -> None:
        """Dispose of the database engine and all connections."""
        await self.engine.dispose()