from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))


@pytest.fixture(scope="session")
def registry():
    from lingxilearn.tools.registry import load_builtin_tools

    return load_builtin_tools()


@pytest_asyncio.fixture
async def state_db() -> AsyncIterator[tuple[object, object, str]]:
    """A unique learner against the migrated PostgreSQL test database."""

    from sqlalchemy import text

    from lingxilearn.config import Settings
    from lingxilearn.store.database import Database
    from lingxilearn.store.learner import LearnerRepository
    from lingxilearn.store.models.base import Base
    from lingxilearn.store.runtime_state import RuntimeStateRepository

    suffix = uuid4().hex
    database_url = os.environ.get("LINGXILEARN_TEST_DATABASE_URL", "")
    if not database_url.startswith(("postgresql+asyncpg://", "postgresql+psycopg://")):
        pytest.fail("LINGXILEARN_TEST_DATABASE_URL must target PostgreSQL")
    settings = Settings(
        _env_file="",
        database_url=database_url,
    )
    database = Database(settings)
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    async with database.engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    learner_id = f"learner-{suffix}"
    await LearnerRepository(database).ensure_learner(learner_id)
    try:
        yield database, RuntimeStateRepository(database), learner_id
    finally:
        async with database.engine.begin() as connection:
            await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
        await database.dispose()
