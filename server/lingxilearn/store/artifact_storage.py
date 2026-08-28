"""Learner-scoped local object-storage adapter."""

from __future__ import annotations

from pathlib import Path

from ..application.workspace_errors import WorkspaceResourceNotFound


class LocalArtifactStorage:
    def __init__(self, var_dir: Path) -> None:
        self._root = var_dir / "artifacts"

    def _target(self, learner_id: str, storage_key: str) -> Path:
        prefix = f"{learner_id}/"
        normalized = storage_key.replace("\\", "/")
        parts = Path(normalized).parts
        if not normalized.startswith(prefix) or len(parts) != 2 or ".." in parts:
            raise WorkspaceResourceNotFound("resource_not_found")
        learner_root = (self._root / learner_id).resolve()
        target = (learner_root / parts[1]).resolve()
        if target.parent != learner_root:
            raise WorkspaceResourceNotFound("resource_not_found")
        return target

    def write(self, learner_id: str, storage_key: str, content: bytes) -> None:
        target = self._target(learner_id, storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def read(self, learner_id: str, storage_key: str) -> bytes:
        target = self._target(learner_id, storage_key)
        if not target.is_file():
            raise WorkspaceResourceNotFound("resource_not_found")
        return target.read_bytes()

    def delete(self, learner_id: str, storage_key: str) -> None:
        target = self._target(learner_id, storage_key)
        target.unlink(missing_ok=True)
