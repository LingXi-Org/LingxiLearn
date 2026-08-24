from __future__ import annotations

import secrets
import uuid
from typing import Any

from ..store.models.workspace import Workspace, WorkspacePinnedItem
from ..store.repositories.workspaces import WorkspaceRepository
from .workspace_errors import WorkspaceDomainError, WorkspaceResourceNotFound

PUBLIC_WORKSPACE_ID = "lingxi"
PINNED_RESOURCE_TYPES = {"workflow", "file", "knowledge_base", "table", "folder", "workspace"}


class WorkspaceService:
    def __init__(self, db: Any) -> None:
        self._repository = WorkspaceRepository(db)

    async def resolve(self, learner_id: str, public_id: str = PUBLIC_WORKSPACE_ID) -> Workspace:
        row = await self._repository.get_or_create(learner_id, f"ws_{secrets.token_urlsafe(18)}")
        if public_id not in {PUBLIC_WORKSPACE_ID, row.id}:
            raise WorkspaceResourceNotFound("resource_not_found")
        return row

    async def update(self, learner_id: str, public_id: str, body: dict[str, Any]) -> Workspace:
        row = await self.resolve(learner_id, public_id)
        name = row.name
        appearance = row.appearance or {}
        if "name" in body:
            name = str(body["name"]).strip()[:160] or name
        if "appearance" in body and isinstance(body["appearance"], dict):
            appearance = dict(body["appearance"])
        return await self._repository.update(row.id, name=name, appearance=appearance) or row

    async def list_pins(
        self, learner_id: str, workspace_id: str, resource_type: str | None
    ) -> list[WorkspacePinnedItem]:
        workspace = await self.resolve(learner_id, workspace_id)
        if resource_type is not None and resource_type not in PINNED_RESOURCE_TYPES:
            raise WorkspaceDomainError("invalid_resource_type")
        return await self._repository.list_pins(learner_id, workspace.id, resource_type)

    async def create_pin(self, learner_id: str, body: dict[str, Any]) -> WorkspacePinnedItem:
        workspace = await self.resolve(learner_id, str(body.get("workspaceId") or "lingxi"))
        resource_type = str(body.get("resourceType") or "")
        resource_id = str(body.get("resourceId") or "").strip()
        if resource_type not in PINNED_RESOURCE_TYPES or not resource_id:
            raise WorkspaceDomainError("invalid_pinned_item")
        existing = await self._repository.find_pin(
            learner_id, workspace.id, resource_type, resource_id
        )
        if existing is not None:
            return existing
        return await self._repository.add_pin(
            WorkspacePinnedItem(
                id=f"pin_{uuid.uuid4().hex}",
                learner_id=learner_id,
                workspace_id=workspace.id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        )

    async def delete_pin(self, learner_id: str, resource_type: str, resource_id: str) -> None:
        if resource_type not in PINNED_RESOURCE_TYPES:
            raise WorkspaceDomainError("invalid_resource_type")
        workspace = await self.resolve(learner_id)
        await self._repository.delete_pin(learner_id, workspace.id, resource_type, resource_id)
