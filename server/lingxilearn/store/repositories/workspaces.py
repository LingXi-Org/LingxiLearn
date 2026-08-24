from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ..models.workspace import Workspace, WorkspacePinnedItem


class WorkspaceRepository:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def get_or_create(self, learner_id: str, workspace_id: str) -> Workspace:
        async with self._db.session() as session:
            row = await session.scalar(select(Workspace).where(Workspace.learner_id == learner_id))
            if row is None:
                row = Workspace(
                    id=workspace_id,
                    learner_id=learner_id,
                    name="灵犀智学",
                    appearance={},
                )
                session.add(row)
                await session.commit()
            return row

    async def update(
        self, workspace_id: str, *, name: str, appearance: dict[str, Any]
    ) -> Workspace | None:
        async with self._db.session() as session:
            row = await session.get(Workspace, workspace_id)
            if row is None:
                return None
            row.name = name
            row.appearance = appearance
            await session.commit()
            return row

    async def list_pins(
        self, learner_id: str, workspace_id: str, resource_type: str | None
    ) -> list[WorkspacePinnedItem]:
        async with self._db.session() as session:
            query = select(WorkspacePinnedItem).where(
                WorkspacePinnedItem.learner_id == learner_id,
                WorkspacePinnedItem.workspace_id == workspace_id,
            )
            if resource_type is not None:
                query = query.where(WorkspacePinnedItem.resource_type == resource_type)
            return list(
                (await session.execute(query.order_by(WorkspacePinnedItem.pinned_at)))
                .scalars()
                .all()
            )

    async def find_pin(
        self, learner_id: str, workspace_id: str, resource_type: str, resource_id: str
    ) -> WorkspacePinnedItem | None:
        async with self._db.session() as session:
            return await session.scalar(
                select(WorkspacePinnedItem).where(
                    WorkspacePinnedItem.learner_id == learner_id,
                    WorkspacePinnedItem.workspace_id == workspace_id,
                    WorkspacePinnedItem.resource_type == resource_type,
                    WorkspacePinnedItem.resource_id == resource_id,
                )
            )

    async def add_pin(self, row: WorkspacePinnedItem) -> WorkspacePinnedItem:
        async with self._db.session() as session:
            session.add(row)
            await session.commit()
            return row

    async def delete_pin(
        self, learner_id: str, workspace_id: str, resource_type: str, resource_id: str
    ) -> None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(WorkspacePinnedItem).where(
                    WorkspacePinnedItem.learner_id == learner_id,
                    WorkspacePinnedItem.workspace_id == workspace_id,
                    WorkspacePinnedItem.resource_type == resource_type,
                    WorkspacePinnedItem.resource_id == resource_id,
                )
            )
            if row is not None:
                await session.delete(row)
                await session.commit()
