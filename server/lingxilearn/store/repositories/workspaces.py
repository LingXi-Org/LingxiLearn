"""PostgreSQL adapter for the Workspace port."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ...domain.workspace import Workspace
from ..models.workspace import WorkspaceRow


def _to_domain(row: WorkspaceRow) -> Workspace:
    return Workspace(
        id=row.id,
        learner_id=row.learner_id,
        name=row.name,
        appearance=dict(row.appearance or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class WorkspaceRepository:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def get_or_create(self, learner_id: str, workspace_id: str) -> Workspace:
        async with self._db.session() as session:
            row = await session.scalar(
                select(WorkspaceRow).where(WorkspaceRow.learner_id == learner_id)
            )
            if row is None:
                row = WorkspaceRow(
                    id=workspace_id,
                    learner_id=learner_id,
                    name="灵犀智学",
                    appearance={},
                )
                session.add(row)
                await session.commit()
                await session.refresh(row)
            return _to_domain(row)

    async def update(
        self, workspace_id: str, *, name: str, appearance: dict[str, Any]
    ) -> Workspace | None:
        async with self._db.session() as session:
            row = await session.get(WorkspaceRow, workspace_id)
            if row is None:
                return None
            row.name = name
            row.appearance = appearance
            await session.commit()
            await session.refresh(row)
            return _to_domain(row)
