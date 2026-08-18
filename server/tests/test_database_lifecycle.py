"""Transaction/session lifecycle coverage for the split store (issue #56).

Every repository method owns a short transaction: the connection returns to
the pool as soon as the method exits, so a graph run never holds a database
session across model latency.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from lingxilearn.config import Settings
from lingxilearn.store.database import Database
from lingxilearn.store.learner import LearnerRepository
from lingxilearn.store.repositories.agent_tasks import AgentTaskRepository
from lingxilearn.store.repositories.runtime import RuntimeRepository
from lingxilearn.store.repositories.sessions import SessionRepository
from lingxilearn.store.repositories.work_ledger import WorkLedgerRepository


def _checked_out(db: Database) -> int:
    checked_out = getattr(db.engine.pool, "checkedout", None)
    return int(checked_out()) if callable(checked_out) else 0


def _settings(suffix: str) -> Settings:
    return Settings(
        _env_file="",
        database_url=f"sqlite+aiosqlite:///./var/test-lifecycle-{suffix}.sqlite3",
    )


@pytest.fixture
def file_db() -> Iterator[tuple[Database, str]]:
    """A file-backed Database whose sqlite file is removed in sync teardown."""

    suffix = uuid4().hex
    yield Database(_settings(suffix)), suffix
    Path("var", f"test-lifecycle-{suffix}.sqlite3").unlink(missing_ok=True)


def test_agent_event_sequence_lock_lives_with_the_event_log_owner() -> None:
    """The append lock moved with the event log, off the Database infra type."""

    db = Database(Settings(_env_file="", database_url="sqlite+aiosqlite:///:memory:"))
    assert not hasattr(db, "agent_event_lock")
    repo = AgentTaskRepository(db)
    first = repo._event_lock("task-1")  # noqa: SLF001 - ownership contract
    assert first is repo._event_lock("task-1")  # noqa: SLF001
    assert first is not repo._event_lock("task-2")  # noqa: SLF001


@pytest.mark.asyncio
async def test_session_context_manager_releases_the_connection(file_db) -> None:
    db, _suffix = file_db
    await db.create_all()
    assert _checked_out(db) == 0
    async with db.session() as session:
        await session.execute(select(1))
        assert _checked_out(db) == 1
    assert _checked_out(db) == 0
    await db.dispose()


@pytest.mark.asyncio
async def test_repository_methods_do_not_hold_sessions_after_returning(file_db) -> None:
    """Each domain repository releases its connection before the caller resumes."""

    db, suffix = file_db
    learner = LearnerRepository(db)
    tasks = AgentTaskRepository(db)
    runtime = RuntimeRepository(db)
    ledger = WorkLedgerRepository(db)
    sessions = SessionRepository(db)
    learner_id = f"learner-{suffix}"
    task_id = f"task-{suffix}"
    session_id = f"session-{suffix}"
    try:
        await db.create_all()
        calls = [
            lambda: learner.ensure_learner(learner_id),
            lambda: learner.ensure_workspace(learner_id),
            lambda: learner.mastery_for(learner_id),
            lambda: learner.mastery_detail(learner_id),
            lambda: learner.save_mastery(learner_id, {"concept-a": 0.5}),
            lambda: tasks.create_agent_task(
                id=task_id,
                learner_id=learner_id,
                prompt="解释 TCP",
                graph_version="test@v2",
                status="queued",
            ),
            lambda: tasks.get_agent_task(task_id),
            lambda: tasks.append_agent_events(
                task_id, [{"kind": "node.started", "agent": "coordinator", "payload": {}}]
            ),
            lambda: tasks.agent_events_after(task_id),
            lambda: runtime.create_agent_execution(
                execution_id="exec-1",
                task_id=task_id,
                learner_id=learner_id,
                graph_version="test@v2",
            ),
            lambda: runtime.get_agent_execution("exec-1"),
            lambda: runtime.pending_interaction_continuations(),
            lambda: ledger.append_command(
                task_id=task_id,
                kind="message",
                payload={"message": "继续"},
                idempotency_key="message-1",
            ),
            lambda: ledger.latest_turn(task_id),
            lambda: ledger.pending_outbox(),
            lambda: sessions.create_session(
                id=session_id,
                learner_id=learner_id,
                pack_id="pack",
                pack_version="1",
                mission_id="mission",
                status="running",
            ),
            lambda: sessions.get_session(session_id),
            lambda: sessions.append_events(session_id, [{"kind": "run.started", "payload": {}}]),
            lambda: sessions.set_status(session_id, "done"),
        ]
        for call in calls:
            await call()
            assert _checked_out(db) == 0
    finally:
        await db.dispose()
