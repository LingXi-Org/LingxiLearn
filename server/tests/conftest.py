from __future__ import annotations

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
    """A throwaway SQLite database with the state tables and one learner.

    ``_env_file=""`` is load-bearing: without it a developer's local ``.env``
    leaks into the test and can point it at a real database.
    """

    from lingxilearn.config import Settings
    from lingxilearn.store.db import Database, Repository
    from lingxilearn.store.runtime_state import RuntimeStateRepository

    suffix = uuid4().hex
    path = REPO_ROOT / "var" / f"test-state-{suffix}.sqlite3"
    settings = Settings(
        _env_file="",
        database_url=f"sqlite+aiosqlite:///./var/{path.name}",
    )
    database = Database(settings)
    await database.create_all()
    learner_id = f"learner-{suffix}"
    await Repository(database).ensure_learner(learner_id)
    try:
        yield database, RuntimeStateRepository(database), learner_id
    finally:
        await database.dispose()
        path.unlink(missing_ok=True)
