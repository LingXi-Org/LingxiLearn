"""Artifact → WorkspaceFile resource versioning (issue #18 §12.2).

A task id is a long-lived thread, so a later turn can regenerate the same
artifact kind.  The workspace projection must keep one stable resource identity
per artifact and refresh its backing content — never report "产物已完成" while
the resource still opens the previous turn's copy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest_asyncio
from sqlalchemy import select

from lingxilearn.config import Settings
from lingxilearn.service import Service
from lingxilearn.store.models.workspace import Workspace, WorkspaceFile


@pytest_asyncio.fixture
async def service_with_task(tmp_path: Path):
    suffix = uuid4().hex
    settings = Settings(
        _env_file="",
        database_url=f"sqlite+aiosqlite:///./var/artifact-version-{suffix}.sqlite3",
        agent_task_dir=tmp_path / "tasks",
        var_dir=tmp_path / "var",
    )
    service = Service(settings)
    await service.db.create_all()
    learner_id = f"learner-{suffix}"
    task_id = f"task-{suffix}"
    await service.repo.ensure_learner(learner_id)
    await service.repo.create_agent_task(
        id=task_id,
        learner_id=learner_id,
        prompt="讲清量子叠加，并给我一个可视化",
        graph_version="test@1",
        status="running",
    )
    try:
        yield service, learner_id, task_id
    finally:
        await service.db.dispose()


async def _workspace_file(service: Service, learner_id: str, path: str) -> Any:
    async with service.db.session() as session:
        workspace = await session.scalar(
            select(Workspace).where(Workspace.learner_id == learner_id)
        )
        assert workspace is not None
        return await session.scalar(
            select(WorkspaceFile).where(
                WorkspaceFile.workspace_id == workspace.id, WorkspaceFile.path == path
            )
        )


def _write_visual(service: Service, task_id: str, body: str) -> None:
    target = service.agent_artifacts.html_path(task_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"<!doctype html><html lang='zh-CN'><head><title>可视化</title></head>"
        f"<body>{body}</body></html>",
        encoding="utf-8",
    )


async def test_second_turn_regenerates_the_same_resource_with_new_content(
    service_with_task,
) -> None:
    service, learner_id, task_id = service_with_task
    path = f"学习产物/{task_id}/visual-explainer.html"

    _write_visual(service, task_id, "第一轮：双缝干涉")
    first_descriptor = await service._project_task_artifact_resource(learner_id, task_id, "visual")
    assert first_descriptor is not None
    first_row = await _workspace_file(service, learner_id, path)
    assert first_row is not None
    assert "第一轮：双缝干涉" in Path(
        service.settings.var_dir / "workspaces" / learner_id / first_row.storage_key.split("/", 1)[1]
    ).read_text(encoding="utf-8")

    # Turn 2 regenerates the same artifact kind on the same thread.
    _write_visual(service, task_id, "第二轮：测量与坍缩")
    second_descriptor = await service._project_task_artifact_resource(learner_id, task_id, "visual")
    assert second_descriptor is not None

    second_row = await _workspace_file(service, learner_id, path)
    assert second_row is not None
    assert second_row.id == first_row.id, "the resource identity stays stable across turns"
    assert second_descriptor["id"] == first_descriptor["id"]
    body = Path(
        service.settings.var_dir
        / "workspaces"
        / learner_id
        / second_row.storage_key.split("/", 1)[1]
    ).read_text(encoding="utf-8")
    assert "第二轮：测量与坍缩" in body, "resource.upsert must not open the previous turn's copy"
    assert "第一轮" not in body
    assert int((second_row.metadata_payload or {}).get("generation") or 0) == 2


async def test_unchanged_artifact_is_not_rewritten(service_with_task) -> None:
    service, learner_id, task_id = service_with_task
    _write_visual(service, task_id, "同一份内容")
    assert await service.project_agent_artifacts(learner_id, task_id) == 1
    # Re-running the idempotent projection with identical bytes is a no-op.
    assert await service.project_agent_artifacts(learner_id, task_id) == 0
