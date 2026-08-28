"""Agent-produced Artifact use cases."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from typing import Any

from ..agents.contracts import quiz_public
from ..domain.artifact import Artifact
from .ports.artifact import (
    ArtifactRepositoryPort,
    ArtifactStoragePort,
    GeneratedArtifactSourcePort,
)
from .workspaces import WorkspaceService


class ArtifactResourceService:
    def __init__(
        self,
        *,
        agent_task_repository: Any,
        repository: ArtifactRepositoryPort,
        storage: ArtifactStoragePort,
        source: GeneratedArtifactSourcePort,
        workspaces: WorkspaceService,
    ) -> None:
        self._agent_tasks = agent_task_repository
        self._repository = repository
        self._storage = storage
        self._source = source
        self._workspaces = workspaces
        self._projection_lock = asyncio.Lock()

    async def project_agent_artifacts(self, learner_id: str, task_id: str | None = None) -> int:
        async with self._projection_lock:
            workspace = await self._workspaces.resolve(learner_id)
            tasks: list[dict[str, Any]] = []
            for scope in ("active", "archived"):
                for item in await self._agent_tasks.list_agent_tasks(learner_id, scope=scope):
                    if task_id is None or item["id"] == task_id:
                        tasks.append(item)
            projected = 0
            for task in tasks:
                task_key = str(task["id"])
                title = str(task.get("title") or task_key)
                for kind in ("lesson-intro", "lecture-deck", "visual"):
                    generated = self._source.read(task_key, kind)
                    if generated is None:
                        continue
                    digest = hashlib.sha256(generated.content).hexdigest()
                    current = await self._repository.find_generated(workspace.id, task_key, kind)
                    current_metadata = current.metadata or {} if current else {}
                    if current_metadata.get("contentHash") == digest:
                        continue
                    storage_key = f"{learner_id}/{uuid.uuid4().hex}"
                    metadata = {
                        "taskTitle": title,
                        "contentHash": digest,
                        "generation": int(current_metadata.get("generation") or 0) + 1,
                    }
                    artifact = Artifact(
                        id=current.id if current else f"artifact_{uuid.uuid4().hex}",
                        workspace_id=workspace.id,
                        name=generated.filename,
                        mime_type=generated.mime_type,
                        size=len(generated.content),
                        storage_key=storage_key,
                        path=f"tasks/{task_key}/{generated.filename}",
                        source="agent",
                        task_id=task_key,
                        kind=kind,
                        metadata=metadata,
                    )
                    self._storage.write(learner_id, storage_key, generated.content)
                    try:
                        _saved, previous_key = await self._repository.save_generated(artifact)
                    except Exception:
                        self._storage.delete(learner_id, storage_key)
                        raise
                    if previous_key and previous_key != storage_key:
                        self._storage.delete(learner_id, previous_key)
                    projected += 1
            return projected

    async def agent_artifact(
        self, task_id: str, kind: str, learner_id: str
    ) -> tuple[bytes, str, str]:
        record = await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        artifact = self._source.read(task_id, kind)
        if artifact is None:
            raise KeyError("artifact_not_ready")
        return artifact.content, artifact.mime_type, artifact.filename

    async def project_task_artifact_resource(
        self, learner_id: str, task_id: str, artifact_kind: str
    ) -> dict[str, Any] | None:
        if artifact_kind not in {"lesson-intro", "lecture-deck", "visual"}:
            return None
        await self.project_agent_artifacts(learner_id, task_id)
        workspace = await self._workspaces.resolve(learner_id)
        artifact = await self._repository.find_generated(workspace.id, task_id, artifact_kind)
        if artifact is None:
            return None
        return {
            "id": artifact.id,
            "title": artifact.name,
            "path": artifact.path,
            "artifact_kind": artifact_kind,
        }

    async def artifact_snapshot(self, record: Any) -> dict[str, Any]:
        found: dict[str, Any] = {
            "lesson_intro": {"available": False, "url": ""},
            "lecture_deck": {"available": False, "url": ""},
            "quiz": {"available": False, "data": None},
            "visual": {"available": False, "url": ""},
        }
        for kind in ("lesson-intro", "lecture-deck", "visual"):
            if self._source.read(record.id, kind) is not None:
                found[kind.replace("-", "_")] = {
                    "available": True,
                    "url": f"/api/agent-tasks/{record.id}/artifacts/{kind}",
                }
        if record.quiz_result:
            found["quiz"] = {
                "available": True,
                "data": quiz_public(record.quiz_result),
            }
        return found

    def restore_task_outputs(self, record: Any) -> tuple[dict[str, Any], tuple[str, ...]]:
        result_columns = (
            ("intent", "intent"),
            ("lecture_hook", "lecture_result"),
            ("interactive_lecture_deck", "deck_result"),
            ("quiz_generator", "quiz_result"),
            ("adaptive_pedagogy", "adaptive_result"),
            ("handoff", "handoff_result"),
            ("visual_explainer", "visual_result"),
        )
        results = {
            key: dict(value)
            for key, column in result_columns
            if isinstance(value := getattr(record, column, None), dict) and value
        }
        for item in list(getattr(record, "user_messages", None) or [])[-20:]:
            if isinstance(item, dict) and item.get("agent"):
                results[str(item["agent"])] = dict(item)
        artifacts = [
            kind
            for kind in ("lesson-intro", "lecture-deck", "visual")
            if self._source.read(record.id, kind) is not None
        ]
        if isinstance(record.quiz_result, dict) and record.quiz_result:
            artifacts.append("quiz")
        return results, tuple(dict.fromkeys(artifacts))
