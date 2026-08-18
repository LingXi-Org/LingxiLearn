"""SQLite quick-start upgrade tests (issue #18 §16).

The project supports a zero-setup SQLite database that is repaired in place on
restart.  ``create_all`` never alters an existing table, so every column a
migration adds to an existing table must also be listed in the compatibility
DDL — otherwise an older local file breaks the moment the new ORM metadata
creates an index over the missing column, and the Alembic marker is written
back to the wrong revision.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text

from lingxilearn.config import Settings
from lingxilearn.store.database import Database
from lingxilearn.store.repositories.agent_tasks import AgentTaskRepository
from lingxilearn.store.repositories.runtime import RuntimeRepository
from lingxilearn.store.sqlite_compat import SQLITE_SCHEMA_HEAD

REPO_ROOT = Path(__file__).resolve().parents[2]

# The exact shape of the tables 0018 touches, as they existed at 0017.  Written
# by hand on purpose: a fresh ``create_all`` would already have the new columns
# and could never catch the upgrade bug this test exists for.
_0017_SCHEMA = """
CREATE TABLE learners (
    id VARCHAR(64) NOT NULL PRIMARY KEY,
    display_name VARCHAR(120) NOT NULL DEFAULT '',
    created_at DATETIME
);
CREATE TABLE agent_tasks (
    id VARCHAR(96) NOT NULL PRIMARY KEY,
    learner_id VARCHAR(64) NOT NULL,
    prompt TEXT NOT NULL DEFAULT '',
    status VARCHAR(24) NOT NULL DEFAULT 'queued',
    error TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    is_pinned BOOLEAN NOT NULL DEFAULT 0,
    is_unread BOOLEAN NOT NULL DEFAULT 0,
    deleted_at DATETIME,
    resources JSON NOT NULL DEFAULT '[]',
    graph_version VARCHAR(32) NOT NULL DEFAULT 'difficult_knowledge.v2',
    intent JSON NOT NULL DEFAULT '{}',
    lecture_result JSON NOT NULL DEFAULT '{}',
    visual_result JSON NOT NULL DEFAULT '{}',
    deck_result JSON NOT NULL DEFAULT '{}',
    quiz_result JSON NOT NULL DEFAULT '{}',
    adaptive_result JSON NOT NULL DEFAULT '{}',
    handoff_result JSON NOT NULL DEFAULT '{}',
    user_messages JSON NOT NULL DEFAULT '[]',
    current_execution_id VARCHAR(128),
    latest_execution_id VARCHAR(128),
    create_idempotency_key VARCHAR(192),
    create_payload_digest VARCHAR(64),
    created_at DATETIME,
    updated_at DATETIME
);
CREATE TABLE agent_task_events (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    task_id VARCHAR(96) NOT NULL,
    sequence INTEGER NOT NULL,
    kind VARCHAR(64) NOT NULL,
    agent VARCHAR(96) NOT NULL DEFAULT '',
    payload JSON NOT NULL DEFAULT '{}',
    execution_id VARCHAR(128),
    runtime JSON NOT NULL DEFAULT '{}',
    created_at DATETIME
);
CREATE TABLE agent_executions (
    id VARCHAR(128) NOT NULL PRIMARY KEY,
    task_id VARCHAR(96) NOT NULL,
    learner_id VARCHAR(64) NOT NULL,
    graph_version VARCHAR(32) NOT NULL DEFAULT '',
    trigger VARCHAR(32) NOT NULL DEFAULT '',
    status VARCHAR(24) NOT NULL DEFAULT 'running',
    error TEXT NOT NULL DEFAULT '',
    workflow_state JSON NOT NULL DEFAULT '{}',
    trace_spans JSON NOT NULL DEFAULT '[]',
    event_count INTEGER NOT NULL DEFAULT 0,
    schedule_id VARCHAR(128),
    scheduled_for DATETIME,
    created_at DATETIME,
    ended_at DATETIME
);
CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
INSERT INTO alembic_version (version_num) VALUES ('0017_agent_task_create_idempotency');
"""


@pytest_asyncio.fixture
async def legacy_sqlite_db():
    """A database file shaped like a pre-0018 local checkout, with data in it."""

    suffix = uuid4().hex
    path = REPO_ROOT / "var" / f"test-0017-{suffix}.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    settings = Settings(
        _env_file="",
        database_url=f"sqlite+aiosqlite:///./var/{path.name}",
    )
    database = Database(settings)
    async with database.engine.begin() as conn:
        for statement in filter(None, (s.strip() for s in _0017_SCHEMA.split(";"))):
            await conn.execute(text(statement))
        await conn.execute(
            text(
                "INSERT INTO learners (id, display_name) VALUES ('learner_legacy', '老用户')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO agent_tasks (id, learner_id, prompt, status)"
                " VALUES ('task_legacy', 'learner_legacy', '什么是量子叠加？', 'completed')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO agent_task_events (task_id, sequence, kind, agent, payload)"
                " VALUES ('task_legacy', 1, 'run.started', 'coordinator', '{}')"
            )
        )
    try:
        yield database, path
    finally:
        await database.dispose()
        path.unlink(missing_ok=True)


async def test_existing_0017_sqlite_file_upgrades_without_data_loss(legacy_sqlite_db) -> None:
    database, _path = legacy_sqlite_db

    await database.ensure_sqlite_schema()

    async with database.engine.begin() as conn:
        columns = {
            row[1]
            for row in (await conn.exec_driver_sql("PRAGMA table_info('agent_tasks')")).fetchall()
        }
        assert "thread_status" in columns
        event_columns = {
            row[1]
            for row in (
                await conn.exec_driver_sql("PRAGMA table_info('agent_task_events')")
            ).fetchall()
        }
        assert {"protocol_version", "turn_id", "agent_run_id", "skill_run_id"} <= event_columns
        execution_columns = {
            row[1]
            for row in (
                await conn.exec_driver_sql("PRAGMA table_info('agent_executions')")
            ).fetchall()
        }
        assert {"turn_id", "parent_execution_id", "resumes_execution_id"} <= execution_columns

        # New 0018 tables exist too, and the learner's data survived.
        tables = {
            row[0]
            for row in (
                await conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        assert {"agent_runs", "skill_runs", "agent_interactions", "agent_interaction_answers"} <= tables
        preserved = (
            await conn.exec_driver_sql("SELECT prompt FROM agent_tasks WHERE id = 'task_legacy'")
        ).scalar()
        assert preserved == "什么是量子叠加？"

        marker = (await conn.exec_driver_sql("SELECT version_num FROM alembic_version")).scalar()
        assert marker == SQLITE_SCHEMA_HEAD == "0018_mothership_protocol_v1"


async def test_repaired_file_accepts_v1_events_and_agent_runs(legacy_sqlite_db) -> None:
    """The repair is only real if the new protocol rows actually write."""

    database, _path = legacy_sqlite_db
    await database.ensure_sqlite_schema()
    agent_task_repository = AgentTaskRepository(database)
    runtime_repository = RuntimeRepository(database)

    await agent_task_repository.set_agent_thread_status("task_legacy", "running")
    await runtime_repository.create_agent_run(
        agent_run_id="ar_upgrade",
        task_id="task_legacy",
        execution_id="exec_upgrade",
        turn_id="turn_upgrade",
        provider_id="answer_user",
        agent_display_name="知识点答疑",
        presentation_role="primary",
        started=True,
    )
    await runtime_repository.create_skill_run(
        skill_run_id="sr_upgrade",
        agent_run_id="ar_upgrade",
        task_id="task_legacy",
        execution_id="exec_upgrade",
        skill_id="knowledge-qa",
        display_name="知识点答疑",
    )
    await agent_task_repository.append_agent_events(
        "task_legacy",
        [
            {
                "kind": "v1.turn",
                "agent": "",
                "payload": {"v": 1, "seq": 0, "type": "turn", "payload": {"turnId": "turn_upgrade"}},
                "protocol_version": 1,
                "turn_id": "turn_upgrade",
                "agent_run_id": "ar_upgrade",
                "skill_run_id": "sr_upgrade",
                "runtime": {},
            }
        ],
    )

    runs = await runtime_repository.agent_runs_for_task("task_legacy")
    assert [run["id"] for run in runs] == ["ar_upgrade"]
    events = await agent_task_repository.agent_events_after("task_legacy")
    v1_events = [event for event in events if int(event.get("protocol_version") or 0) == 1]
    assert len(v1_events) == 1
    assert v1_events[0]["turn_id"] == "turn_upgrade"
    assert json.dumps(v1_events[0]["payload"], ensure_ascii=False)


@pytest.mark.parametrize("table", ["agent_tasks", "agent_task_events", "agent_executions"])
def test_compat_columns_cover_every_0018_existing_table_column(table: str) -> None:
    """Guards the next migration: 0018's added columns must all be repairable."""

    from lingxilearn.store.sqlite_compat import SQLITE_COMPAT_COLUMNS

    expected = {
        "agent_tasks": {"thread_status"},
        "agent_task_events": {"protocol_version", "turn_id", "agent_run_id", "skill_run_id"},
        "agent_executions": {"turn_id", "parent_execution_id", "resumes_execution_id"},
    }[table]
    assert expected <= set(SQLITE_COMPAT_COLUMNS[table])
