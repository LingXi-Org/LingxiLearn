"""Artifact → workspace/resource projection and attachment storage.

Owns the boundary between the graph's audit files under ``agent_task_dir``
and the learner-facing read-only Workspace Files, plus the upload path for
learner attachments.  The underlying storage algorithm stays in
:class:`~lingxilearn.agents.artifact_store.ArtifactStore`; this service only
decides *when* and *where* artifacts become resources.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import mimetypes
import secrets
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select

from ..agents.artifact_store import ArtifactError, ArtifactStore
from ..agents.contracts import quiz_public
from ..config import Settings
from ..store.database import Database
from ..store.models.workspace import Workspace, WorkspaceFile
from ..store.repositories.agent_tasks import AgentTaskRepository

logger = logging.getLogger(__name__)


class ArtifactResourceService:
    """Project completed agent artifacts into stable workspace resources."""

    def __init__(
        self,
        *,
        db: Database,
        agent_task_repository: AgentTaskRepository,
        artifact_store: ArtifactStore,
        settings: Settings,
    ) -> None:
        self._db = db
        self._agent_tasks = agent_task_repository
        self._artifacts = artifact_store
        self._settings = settings
        self._workspace_projection_lock = asyncio.Lock()

    async def project_agent_artifacts(self, learner_id: str, task_id: str | None = None) -> int:
        """Project completed LingxiGraph artifacts into read-only Workspace Files.

        The graph keeps its original audit files under ``agent_task_dir``. A
        second immutable copy in the learner workspace gives native Files a
        stable resource identity without making the graph output editable or
        coupling file deletion to task-audit retention.
        """

        async with self._workspace_projection_lock:
            async with self._db.session() as session:
                workspace = await session.scalar(
                    select(Workspace).where(Workspace.learner_id == learner_id)
                )
                if workspace is None:
                    workspace = Workspace(
                        id=f"ws_{secrets.token_urlsafe(18)}",
                        learner_id=learner_id,
                        name="灵犀智学",
                        appearance={},
                    )
                    session.add(workspace)
                    await session.flush()

                tasks = []
                for scope in ("active", "archived"):
                    for item in await self._agent_tasks.list_agent_tasks(learner_id, scope=scope):
                        if task_id is None or item["id"] == task_id:
                            tasks.append(item)
                projected = 0
                for task in tasks:
                    task_key = str(task["id"])
                    title = str(
                        task.get("title") or task.get("intent", {}).get("topic") or task_key
                    )
                    candidates = (
                        (self._artifacts.lesson_intro_path(task_key), "lesson-intro.html"),
                        (self._artifacts.deck_path(task_key), "lecture.html"),
                        (self._artifacts.html_path(task_key), "visual-explainer.html"),
                    )
                    for source, filename in candidates:
                        if not source.is_file():
                            continue
                        path = f"学习产物/{task_key}/{filename}"
                        existing = await session.scalar(
                            select(WorkspaceFile).where(
                                WorkspaceFile.workspace_id == workspace.id,
                                WorkspaceFile.path == path,
                            )
                        )
                        raw = source.read_bytes()
                        content_hash = hashlib.sha256(raw).hexdigest()
                        if existing is not None:
                            # A task id is a long-lived thread: a later turn can
                            # regenerate the same artifact kind.  Keep the stable
                            # resource identity but refresh its backing version,
                            # so "产物已完成" never opens the previous turn's copy
                            # (issue #18 §12.2).
                            metadata = dict(existing.metadata_payload or {})
                            if metadata.get("contentHash") == content_hash:
                                continue
                            storage_key = f"{learner_id}/{secrets.token_urlsafe(24)}"
                            target_root = self._settings.var_dir / "workspaces" / learner_id
                            target_root.mkdir(parents=True, exist_ok=True)
                            (target_root / storage_key.split("/", 1)[1]).write_bytes(raw)
                            metadata.update(
                                {
                                    "source": "lingxigraph",
                                    "taskId": task_key,
                                    "taskTitle": title,
                                    "readOnly": True,
                                    "contentHash": content_hash,
                                    "generation": int(metadata.get("generation") or 1) + 1,
                                }
                            )
                            existing.storage_key = storage_key
                            existing.size = len(raw)
                            existing.metadata_payload = metadata
                            projected += 1
                            continue
                        storage_key = f"{learner_id}/{secrets.token_urlsafe(24)}"
                        target_root = self._settings.var_dir / "workspaces" / learner_id
                        target_root.mkdir(parents=True, exist_ok=True)
                        target = target_root / storage_key.split("/", 1)[1]
                        target.write_bytes(raw)
                        session.add(
                            WorkspaceFile(
                                id=f"file_{uuid.uuid4().hex}",
                                workspace_id=workspace.id,
                                name=filename,
                                mime_type=mimetypes.guess_type(filename)[0]
                                or "application/octet-stream",
                                size=len(raw),
                                storage_key=storage_key,
                                path=path,
                                metadata_payload={
                                    "source": "lingxigraph",
                                    "taskId": task_key,
                                    "taskTitle": title,
                                    "readOnly": True,
                                    "contentHash": content_hash,
                                    "generation": 1,
                                },
                            )
                        )
                        projected += 1
                if projected or workspace not in session.new:
                    await session.commit()
                return projected

    async def agent_artifact(
        self, task_id: str, kind: str, learner_id: str | None = None
    ) -> tuple[bytes, str, str]:
        record = (
            await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
            if learner_id is not None
            else await self._agent_tasks.get_agent_task(task_id)
        )
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        if kind == "lecture-deck":
            try:
                return (
                    self._artifacts.deck_path(task_id).read_bytes(),
                    "text/html; charset=utf-8",
                    "lecture.html",
                )
            except OSError as exc:
                raise KeyError("lecture deck is not ready") from exc
        if kind == "lesson-intro":
            try:
                return (
                    self._artifacts.lesson_intro_path(task_id).read_bytes(),
                    "text/html; charset=utf-8",
                    "lesson-intro.html",
                )
            except OSError as exc:
                raise KeyError("lesson intro is not ready") from exc
        if kind == "visual":
            try:
                return (
                    self._artifacts.read_html(task_id),
                    "text/html; charset=utf-8",
                    "visual-explainer.html",
                )
            except ArtifactError as exc:
                raise KeyError(str(exc)) from exc
        raise KeyError(f"unknown artifact kind: {kind}")

    async def project_task_artifact_resource(
        self, learner_id: str, task_id: str, artifact_kind: str
    ) -> dict[str, Any] | None:
        """Resolve one artifact to its stable WorkspaceFile resource identity.

        Runs the idempotent workspace projection first, then returns the
        descriptor the V1 ``resource.upsert`` event should carry.  Unknown
        artifact kinds and not-yet-written files return None — the projector
        then falls back to the synthetic identity.
        """

        filenames = {
            "lesson-intro": "lesson-intro.html",
            "lecture-deck": "lecture.html",
            "visual": "visual-explainer.html",
        }
        filename = filenames.get(artifact_kind)
        if not filename:
            return None
        try:
            await self.project_agent_artifacts(learner_id, task_id)
            async with self._db.session() as session:
                workspace = await session.scalar(
                    select(Workspace).where(Workspace.learner_id == learner_id)
                )
                if workspace is None:
                    return None
                row = await session.scalar(
                    select(WorkspaceFile).where(
                        WorkspaceFile.workspace_id == workspace.id,
                        WorkspaceFile.path == f"学习产物/{task_id}/{filename}",
                    )
                )
                if row is None:
                    return None
                return {
                    "id": row.id,
                    "title": row.name,
                    "path": row.path,
                    "artifact_kind": artifact_kind,
                }
        except Exception:  # noqa: BLE001 - projection must not fail the run
            logger.exception("artifact resource projection failed: %s/%s", task_id, artifact_kind)
            return None

    async def artifact_snapshot(self, record: Any) -> dict[str, Any]:
        """The artifacts this task actually produced, read from disk.

        Derived rather than declared: an artifact kind that a provider stops
        producing disappears from the response instead of lingering as a key
        that is permanently ``available: false``.
        """

        found: dict[str, Any] = {
            "lesson_intro": {"available": False, "url": ""},
            "lecture_deck": {"available": False, "url": ""},
            "quiz": {"available": False, "data": None},
            "visual": {"available": False, "url": ""},
        }
        for kind, exists in (
            ("lesson-intro", self._artifacts.lesson_intro_path(record.id).exists()),
            ("lecture-deck", self._artifacts.deck_path(record.id).exists()),
            ("visual", self._artifacts.html_path(record.id).exists()),
        ):
            if exists:
                key = kind.replace("-", "_")
                found[key] = {
                    "available": True,
                    "url": f"/api/agent-tasks/{record.id}/artifacts/{kind}",
                }
        if record.quiz_result:
            found["quiz"] = {"available": True, "data": quiz_public(record.quiz_result)}
        return found

    def restore_task_outputs(self, record: Any) -> tuple[dict[str, Any], tuple[str, ...]]:
        """Restore provider outputs and artifacts when a task is resumed.

        AgentTask keeps each provider result in a dedicated JSON column for
        backwards-compatible reads.  The runtime dispatcher, however, uses a
        single result map keyed by ``persist_as`` and a set of artifact names.
        Keep that translation in one place so a restarted task can continue
        from durable state instead of starting with an empty context.
        """

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
        messages = list(getattr(record, "user_messages", None) or [])
        for item in messages[-20:]:
            if isinstance(item, dict) and item.get("agent"):
                results[str(item["agent"])] = dict(item)

        artifact_paths = (
            ("lesson-intro", self._artifacts.lesson_intro_path(record.id)),
            ("lecture-deck", self._artifacts.deck_path(record.id)),
            ("visual", self._artifacts.html_path(record.id)),
        )
        artifacts = [name for name, path in artifact_paths if path.exists()]
        if isinstance(record.quiz_result, dict) and record.quiz_result:
            artifacts.append("quiz")
        return results, tuple(dict.fromkeys(artifacts))

    async def recover_lesson_intro_draft(self, task_id: str) -> dict[str, Any] | None:
        """Recover an interrupted lesson-intro draft, if one was written."""

        return await self._artifacts.recover_lesson_intro_draft(task_id)

    async def recover_deck_draft(self, task_id: str) -> dict[str, Any] | None:
        """Recover an interrupted lecture-deck draft, if one was written."""

        return await self._artifacts.recover_deck_draft(task_id)

    async def upload_attachment(
        self, *, learner_id: str, filename: str, media_type: str, size: int, encoded: str
    ) -> dict[str, Any]:
        if size > 20 * 1024 * 1024:
            raise ValueError("attachment too large")
        try:
            content = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("invalid attachment data") from exc
        if len(content) != size:
            raise ValueError("attachment size mismatch")
        attachment_id = uuid.uuid4().hex
        root = self._settings.agent_task_dir / "uploads" / learner_id
        root.mkdir(parents=True, exist_ok=True)
        path = root / attachment_id
        path.write_bytes(content)
        return {
            "key": f"{learner_id}/{attachment_id}",
            "path": f"/api/attachments/{learner_id}/{attachment_id}",
            "filename": filename,
            "media_type": media_type,
            "size": size,
        }

    def attachment_path(self, learner_id: str, attachment_id: str) -> tuple[Path, str, str]:
        if not attachment_id.isalnum() or len(attachment_id) != 32:
            raise KeyError("unknown attachment")
        path = (self._settings.agent_task_dir / "uploads" / learner_id / attachment_id).resolve()
        root = (self._settings.agent_task_dir / "uploads" / learner_id).resolve()
        if root not in path.parents or not path.is_file():
            raise KeyError("unknown attachment")
        return path, "application/octet-stream", attachment_id
