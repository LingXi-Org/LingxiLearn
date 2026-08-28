"""PostgreSQL adapter for Artifact persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ...domain.artifact import Artifact
from ..models.workspace import ArtifactRow


def to_domain(row: ArtifactRow) -> Artifact:
    return Artifact(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        mime_type=row.mime_type,
        size=row.size,
        storage_key=row.storage_key,
        path=row.path,
        source=row.source,
        task_id=row.task_id,
        kind=row.kind,
        metadata=dict(row.metadata_payload or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ArtifactRepository:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def list(self, workspace_id: str) -> list[Artifact]:
        async with self._db.session() as session:
            rows = (
                (
                    await session.execute(
                        select(ArtifactRow)
                        .where(ArtifactRow.workspace_id == workspace_id)
                        .order_by(ArtifactRow.updated_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            return [to_domain(row) for row in rows]

    async def get(self, workspace_id: str, artifact_id: str) -> Artifact | None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(ArtifactRow).where(
                    ArtifactRow.workspace_id == workspace_id,
                    ArtifactRow.id == artifact_id,
                )
            )
            return to_domain(row) if row is not None else None

    async def add(self, artifact: Artifact) -> Artifact:
        row = ArtifactRow(
            id=artifact.id,
            workspace_id=artifact.workspace_id,
            name=artifact.name,
            mime_type=artifact.mime_type,
            size=artifact.size,
            storage_key=artifact.storage_key,
            path=artifact.path,
            source=artifact.source,
            task_id=artifact.task_id,
            kind=artifact.kind,
            metadata_payload=artifact.metadata or {},
        )
        async with self._db.session() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return to_domain(row)

    async def find_generated(self, workspace_id: str, task_id: str, kind: str) -> Artifact | None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(ArtifactRow).where(
                    ArtifactRow.workspace_id == workspace_id,
                    ArtifactRow.task_id == task_id,
                    ArtifactRow.kind == kind,
                    ArtifactRow.source == "agent",
                )
            )
            return to_domain(row) if row is not None else None

    async def save_generated(self, artifact: Artifact) -> tuple[Artifact, str | None]:
        async with self._db.session() as session:
            row = await session.scalar(
                select(ArtifactRow).where(
                    ArtifactRow.workspace_id == artifact.workspace_id,
                    ArtifactRow.task_id == artifact.task_id,
                    ArtifactRow.kind == artifact.kind,
                    ArtifactRow.source == "agent",
                )
            )
            previous_key: str | None = None
            if row is None:
                row = ArtifactRow(
                    id=artifact.id,
                    workspace_id=artifact.workspace_id,
                    name=artifact.name,
                    mime_type=artifact.mime_type,
                    size=artifact.size,
                    storage_key=artifact.storage_key,
                    path=artifact.path,
                    source="agent",
                    task_id=artifact.task_id,
                    kind=artifact.kind,
                    metadata_payload=artifact.metadata or {},
                )
                session.add(row)
            else:
                previous_key = row.storage_key
                row.name = artifact.name
                row.mime_type = artifact.mime_type
                row.size = artifact.size
                row.storage_key = artifact.storage_key
                row.path = artifact.path
                row.metadata_payload = artifact.metadata or {}
            await session.commit()
            await session.refresh(row)
            return to_domain(row), previous_key

    async def update_metadata(
        self, workspace_id: str, artifact_id: str, *, name: str
    ) -> Artifact | None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(ArtifactRow).where(
                    ArtifactRow.workspace_id == workspace_id,
                    ArtifactRow.id == artifact_id,
                )
            )
            if row is None:
                return None
            row.name = name
            await session.commit()
            await session.refresh(row)
            return to_domain(row)

    async def replace_content(
        self,
        workspace_id: str,
        artifact_id: str,
        *,
        storage_key: str,
        size: int,
    ) -> Artifact | None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(ArtifactRow).where(
                    ArtifactRow.workspace_id == workspace_id,
                    ArtifactRow.id == artifact_id,
                )
            )
            if row is None:
                return None
            row.storage_key = storage_key
            row.size = size
            await session.commit()
            await session.refresh(row)
            return to_domain(row)

    async def delete(self, workspace_id: str, artifact_id: str) -> Artifact | None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(ArtifactRow).where(
                    ArtifactRow.workspace_id == workspace_id,
                    ArtifactRow.id == artifact_id,
                )
            )
            if row is None:
                return None
            artifact = to_domain(row)
            await session.delete(row)
            await session.commit()
            return artifact
