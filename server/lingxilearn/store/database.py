"""Engine, session factory and database lifecycle.

One rule worth stating because breaking it is the classic scaling mistake:
**never hold a database session open across a graph run.**  Resolve what you
need, release the connection, then stream.  A pool of 10 gated on model latency
caps you at 10 concurrent learners for no reason.

Domain persistence lives in :mod:`lingxilearn.store.repositories` and
:class:`~lingxilearn.store.learner.LearnerRepository`; this module stays
infrastructure-only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import Settings

# Register every domain model on the shared metadata: ``create_all`` and the
# SQLite quick-start must materialise the complete schema no matter which
# subset of models the importing module happens to query.
from .models import registry as _model_registry  # noqa: F401
from .models.base import Base
from .sqlite_compat import repair_sqlite_schema


class Database:
    def __init__(self, settings: Settings) -> None:
        url = settings.resolved_database_url
        kwargs: dict[str, Any] = {"pool_pre_ping": True}
        if url.startswith("postgresql"):
            kwargs.update(
                pool_size=max(1, settings.db_pool_size),
                max_overflow=max(0, settings.db_max_overflow),
            )
        else:
            kwargs["connect_args"] = {"timeout": 30}
        self.engine = create_async_engine(url, **kwargs)

        if url.startswith("sqlite"):
            # A run streams events from a background task while the API reads
            # status and SSE replays the log. Rollback-journal SQLite serialises
            # those against each other and throws "database is locked"; WAL lets
            # readers proceed during a write, which is exactly our access shape.
            @event.listens_for(self.engine.sync_engine, "connect")
            def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=10000")
                cursor.close()

        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
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
            await conn.run_sync(repair_sqlite_schema)

    async def ping(self) -> bool:
        async with self.engine.connect() as conn:
            await conn.execute(select(1))
        return True

    async def dispose(self) -> None:
        await self.engine.dispose()
