from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from lingxilearn.config import Settings
from lingxilearn.store.database import Database
from lingxilearn.store.learner import LearnerRepository
from lingxilearn.store.models.table import WorkspaceTable, WorkspaceTableRow
from lingxilearn.store.models.workspace import Workspace
from lingxilearn.store.repositories.agent_tasks import AgentTaskRepository
from lingxilearn.store.repositories.sessions import SessionRepository


@pytest.mark.asyncio
async def test_agent_event_sequence_allocation_is_safe_for_concurrent_writers() -> None:
    suffix = uuid4().hex
    settings = Settings(
        _env_file="",
        database_url=f"sqlite+aiosqlite:///./var/test-event-lock-{suffix}.sqlite3",
    )
    database = Database(settings)
    agent_task_repository = AgentTaskRepository(database)
    learner_repository = LearnerRepository(database)
    learner_id = f"learner-{suffix}"
    task_id = f"task-{suffix}"
    try:
        await database.create_all()
        await learner_repository.ensure_learner(learner_id)
        await agent_task_repository.create_agent_task(
            id=task_id,
            learner_id=learner_id,
            prompt="解释 TCP",
            status="running",
            resources=[],
            intent={},
            lecture_result={},
            deck_result={},
            quiz_result={},
            adaptive_result={},
            handoff_result={},
            user_messages=[],
            visual_result={},
        )
        await asyncio.gather(
            *(
                agent_task_repository.append_agent_events(
                    task_id,
                    [{"kind": "node.appeared", "agent": "orchestrator", "payload": {}}],
                )
                for _ in range(12)
            )
        )
        events = await agent_task_repository.agent_events_after(task_id)
        assert [event["sequence"] for event in events] == list(range(1, 13))
    finally:
        await database.dispose()
        (Path("var") / f"test-event-lock-{suffix}.sqlite3").unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_agent_and_session_runtime_events_are_projected_to_tables() -> None:
    suffix = uuid4().hex
    settings = Settings(
        _env_file="",
        database_url=f"sqlite+aiosqlite:///./var/test-runtime-{suffix}.sqlite3",
    )
    database = Database(settings)
    await database.create_all()
    agent_task_repository = AgentTaskRepository(database)
    session_repository = SessionRepository(database)
    learner_repository = LearnerRepository(database)
    learner_id = f"learner-{suffix}"
    task_id = f"task-{suffix}"
    session_id = f"session-{suffix}"
    try:
        await learner_repository.ensure_learner(learner_id)
        await agent_task_repository.create_agent_task(
            id=task_id,
            learner_id=learner_id,
            prompt="解释 TCP",
            status="queued",
            resources=[],
            intent={},
            lecture_result={},
            deck_result={},
            quiz_result={},
            adaptive_result={},
            handoff_result={},
            user_messages=[],
            visual_result={},
        )
        await agent_task_repository.append_agent_events(
            task_id,
            [
                {
                    "kind": "node.started",
                    "agent": "coordinator",
                    "execution_id": "exec-1",
                    "payload": {"node": "recognize_intent"},
                },
                {
                    "kind": "tool.result",
                    "agent": "web_search",
                    "execution_id": "exec-1",
                    "payload": {"count": 2},
                },
            ],
        )
        submission = await agent_task_repository.create_quiz_submission(
            task_id=task_id,
            submission_id="submission-1",
            answers={"q01": "A"},
            per_question=[{"id": "q01", "correct": True}],
            total_score=1,
            total_points=1,
        )
        await session_repository.project_runtime_event(
            learner_id=learner_id,
            record_key=f"assessment:{task_id}:submission-1",
            task_id=task_id,
            kind="assessment.submitted",
            payload=submission,
        )
        await session_repository.create_session(
            id=session_id,
            learner_id=learner_id,
            pack_id="pack",
            pack_version="1",
            mission_id="mission",
            status="running",
        )
        await session_repository.append_events(
            session_id,
            [{"kind": "evidence.added", "node": "judge", "payload": {"id": "ev_1"}}],
        )

        async with database.session() as session:
            workspace = await session.scalar(
                select(Workspace).where(Workspace.learner_id == learner_id)
            )
            assert workspace is not None
            tables = (
                (
                    await session.execute(
                        select(WorkspaceTable).where(
                            WorkspaceTable.workspace_id == workspace.id,
                            WorkspaceTable.archived.is_(False),
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert {table.name for table in tables} == {
                "节点执行",
                "工具调用",
                "学习证据",
                "练习测评",
            }
            rows = (
                (
                    await session.execute(
                        select(WorkspaceTableRow).where(
                            WorkspaceTableRow.table_id.in_([table.id for table in tables])
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert {row.values["record_key"] for row in rows} == {
                f"task:{task_id}:1",
                f"task:{task_id}:2",
                f"session:{session_id}:1",
                f"assessment:{task_id}:submission-1",
            }
            assert all(row.values["learner_id"] == learner_id for row in rows)

        # Replaying through the public projection path updates the same row.
        result = await session_repository.project_runtime_event(
            learner_id=learner_id,
            record_key=f"task:{task_id}:1",
            task_id=task_id,
            sequence=1,
            kind="node.started",
            agent="coordinator",
            payload={"node": "updated"},
        )
        assert result["action"] == "updated"
        async with database.session() as session:
            count = await session.scalar(
                select(WorkspaceTableRow).where(
                    WorkspaceTableRow.values["record_key"].as_string() == f"task:{task_id}:1"
                )
            )
            assert count is not None
            assert count.values["payload"] == {"node": "updated"}
    finally:
        await database.dispose()
