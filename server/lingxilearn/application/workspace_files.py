from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from .workspace_errors import WorkspaceDomainError, WorkspaceResourceNotFound


def safe_leaf_name(value: str, fallback: str = "untitled") -> str:
    candidate = str(value).strip().replace("\x00", "")
    if not candidate or candidate in {".", ".."} or "/" in candidate or "\\" in candidate:
        if not candidate and fallback:
            return fallback
        raise WorkspaceDomainError("invalid_file_name")
    return candidate[:255] or fallback


def validated_mime_type(name: str, supplied: Any) -> str:
    value = str(supplied or mimetypes.guess_type(name)[0] or "application/octet-stream").strip()
    if not value or len(value) > 160 or any(ord(char) < 32 for char in value):
        raise WorkspaceDomainError("invalid_mime_type")
    return value


class WorkspaceFileStorage:
    """Learner-scoped filesystem gateway with traversal and symlink protection."""

    def __init__(self, var_dir: Path) -> None:
        self._var_dir = var_dir

    def root(self, learner_id: str) -> Path:
        root = self._var_dir / "workspaces" / learner_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def target(self, learner_id: str, storage_key: str) -> Path:
        prefix = f"{learner_id}/"
        parts = Path(storage_key.replace("\\", "/")).parts
        if not storage_key.startswith(prefix) or ".." in parts or len(parts) != 2:
            raise WorkspaceResourceNotFound("resource_not_found")
        root = self.root(learner_id).resolve()
        target = (root / parts[1]).resolve()
        if target.parent != root:
            raise WorkspaceResourceNotFound("resource_not_found")
        return target
