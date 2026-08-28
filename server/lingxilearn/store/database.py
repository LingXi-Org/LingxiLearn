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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import Settings
from .models import registry as _model_registry  # noqa: F401


class Database:
    def __init__(self, settings: Settings) -> None:
        url = settings.resolved_database_url
        if not url.startswith(("postgresql+asyncpg://", "postgresql+psycopg://")):
            raise ValueError("Database requires an explicit PostgreSQL async URL")
        kwargs: dict[str, Any] = {
            "pool_pre_ping": True,
            "pool_size": max(1, settings.db_pool_size),
            "max_overflow": max(0, settings.db_max_overflow),
        }
        self.engine = create_async_engine(url, **kwargs)

        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.factory() as session:
            yield session

    async def ping(self) -> bool:
        async with self.engine.connect() as conn:
            await conn.execute(select(1))
        return True

    async def dispose(self) -> None:
        await self.engine.dispose()
