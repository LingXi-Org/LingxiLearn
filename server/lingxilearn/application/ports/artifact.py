"""Artifact persistence and object-storage boundaries."""

from __future__ import annotations

from typing import Any, Protocol

from ...domain.artifact import Artifact, GeneratedArtifact


class ArtifactRepositoryPort(Protocol):
    async def list(self, workspace_id: str) -> list[Artifact]: ...

    async def get(self, workspace_id: str, artifact_id: str) -> Artifact | None: ...

    async def add(self, artifact: Artifact) -> Artifact: ...

    async def find_generated(
        self, workspace_id: str, task_id: str, kind: str
    ) -> Artifact | None: ...

    async def save_generated(self, artifact: Artifact) -> tuple[Artifact, str | None]: ...

    async def update_metadata(
        self, workspace_id: str, artifact_id: str, *, name: str
    ) -> Artifact | None: ...

    async def replace_content(
        self,
        workspace_id: str,
        artifact_id: str,
        *,
        storage_key: str,
        size: int,
    ) -> Artifact | None: ...

    async def delete(self, workspace_id: str, artifact_id: str) -> Artifact | None: ...


class ArtifactStoragePort(Protocol):
    def write(self, learner_id: str, storage_key: str, content: bytes) -> None: ...

    def read(self, learner_id: str, storage_key: str) -> bytes: ...

    def delete(self, learner_id: str, storage_key: str) -> None: ...


class GeneratedArtifactSourcePort(Protocol):
    def read(self, task_id: str, kind: str) -> GeneratedArtifact | None: ...

    async def recover(self, task_id: str, kind: str) -> dict[str, Any] | None: ...
