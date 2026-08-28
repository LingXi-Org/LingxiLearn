"""Workspace Artifact use cases."""

from __future__ import annotations

import mimetypes
import uuid

from ..domain.artifact import Artifact
from .ports.artifact import ArtifactRepositoryPort, ArtifactStoragePort
from .workspace_errors import (
    WorkspaceDomainError,
    WorkspacePayloadTooLarge,
    WorkspaceResourceNotFound,
)


def _artifact_name(value: str) -> str:
    name = value.strip().replace("\x00", "")
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise WorkspaceDomainError("invalid_artifact_name")
    return name[:255]


def _artifact_mime(name: str, supplied: str | None) -> str:
    mime = (supplied or mimetypes.guess_type(name)[0] or "application/octet-stream").strip()
    if not mime or len(mime) > 160 or any(ord(char) < 32 for char in mime):
        raise WorkspaceDomainError("invalid_mime_type")
    return mime


class WorkspaceArtifactService:
    def __init__(
        self,
        repository: ArtifactRepositoryPort,
        storage: ArtifactStoragePort,
        *,
        max_bytes: int,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._max_bytes = max_bytes

    async def list(self, workspace_id: str) -> list[Artifact]:
        return await self._repository.list(workspace_id)

    async def require(self, workspace_id: str, artifact_id: str) -> Artifact:
        artifact = await self._repository.get(workspace_id, artifact_id)
        if artifact is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return artifact

    async def create(
        self,
        *,
        workspace_id: str,
        learner_id: str,
        name: str,
        mime_type: str | None,
        content: bytes,
    ) -> Artifact:
        if len(content) > self._max_bytes:
            raise WorkspacePayloadTooLarge("artifact_too_large")
        artifact_id = f"artifact_{uuid.uuid4().hex}"
        safe_name = _artifact_name(name)
        storage_key = f"{learner_id}/{uuid.uuid4().hex}"
        artifact = Artifact(
            id=artifact_id,
            workspace_id=workspace_id,
            name=safe_name,
            mime_type=_artifact_mime(safe_name, mime_type),
            size=len(content),
            storage_key=storage_key,
            path=f"uploads/{artifact_id}/{safe_name}",
        )
        self._storage.write(learner_id, storage_key, content)
        try:
            return await self._repository.add(artifact)
        except Exception:
            self._storage.delete(learner_id, storage_key)
            raise

    async def rename(self, workspace_id: str, artifact_id: str, name: str) -> Artifact:
        artifact = await self._repository.update_metadata(
            workspace_id, artifact_id, name=_artifact_name(name)
        )
        if artifact is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return artifact

    async def read(
        self, workspace_id: str, artifact_id: str, learner_id: str
    ) -> tuple[Artifact, bytes]:
        artifact = await self.require(workspace_id, artifact_id)
        return artifact, self._storage.read(learner_id, artifact.storage_key)

    async def replace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        learner_id: str,
        content: bytes,
    ) -> Artifact:
        if len(content) > self._max_bytes:
            raise WorkspacePayloadTooLarge("artifact_too_large")
        current = await self.require(workspace_id, artifact_id)
        storage_key = f"{learner_id}/{uuid.uuid4().hex}"
        self._storage.write(learner_id, storage_key, content)
        try:
            artifact = await self._repository.replace_content(
                workspace_id,
                artifact_id,
                storage_key=storage_key,
                size=len(content),
            )
            if artifact is None:
                raise WorkspaceResourceNotFound("resource_not_found")
        except Exception:
            self._storage.delete(learner_id, storage_key)
            raise
        self._storage.delete(learner_id, current.storage_key)
        return artifact

    async def delete(self, workspace_id: str, artifact_id: str, learner_id: str) -> None:
        artifact = await self._repository.delete(workspace_id, artifact_id)
        if artifact is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        self._storage.delete(learner_id, artifact.storage_key)
