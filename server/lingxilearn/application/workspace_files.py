from __future__ import annotations

import base64
import binascii
import io
import mimetypes
import zipfile
from pathlib import Path
from typing import Any

from .workspace_errors import WorkspaceDomainError, WorkspaceResourceNotFound

MAX_FILE_SIZE = 20 * 1024 * 1024


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

    @staticmethod
    def decode_content(content: Any, encoding: str | None = None) -> bytes:
        if encoding == "base64" or not isinstance(content, str):
            try:
                return base64.b64decode(str(content), validate=True)
            except (ValueError, binascii.Error) as exc:
                raise WorkspaceDomainError("invalid_base64_content") from exc
        return content.encode("utf-8")

    def write(self, learner_id: str, storage_key: str, raw: bytes) -> Path:
        target = self.target(learner_id, storage_key)
        target.write_bytes(raw)
        return target

    def read(self, learner_id: str, storage_key: str) -> bytes:
        target = self.existing_target(learner_id, storage_key)
        return target.read_bytes()

    def existing_target(self, learner_id: str, storage_key: str) -> Path:
        target = self.target(learner_id, storage_key)
        if not target.is_file():
            raise WorkspaceResourceNotFound("resource_not_found")
        return target

    def archive(self, learner_id: str, files: list[Any]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for row in files:
                target = self.target(learner_id, row.storage_key)
                if target.is_file():
                    archive.writestr(row.path or row.name, target.read_bytes())
        return buffer.getvalue()

    @staticmethod
    def write_temporary(path: Path, raw: bytes) -> None:
        path.write_bytes(raw)

    @staticmethod
    def read_upload(item: dict[str, Any]) -> bytes:
        temp: Path = item["temp"]
        if temp.is_file():
            return temp.read_bytes()
        return b"".join(
            path.read_bytes()
            for _number, path in sorted(item.get("parts", {}).items())
            if path.is_file()
        )

    @staticmethod
    def cleanup_upload(item: dict[str, Any]) -> None:
        item["temp"].unlink(missing_ok=True)
        for part_path in item.get("parts", {}).values():
            part_path.unlink(missing_ok=True)

    @staticmethod
    def remove(path: Path) -> None:
        path.unlink(missing_ok=True)
