"""Workspace use cases."""

from __future__ import annotations

import secrets
from typing import Any

from ..domain.workspace import Workspace
from .ports.workspace import WorkspacePort
from .workspace_errors import WorkspaceResourceNotFound

PUBLIC_WORKSPACE_ID = "lingxi"


class WorkspaceService:
    def __init__(self, repository: WorkspacePort) -> None:
        self._repository = repository

    async def resolve(self, learner_id: str, public_id: str = PUBLIC_WORKSPACE_ID) -> Workspace:
        workspace = await self._repository.get_or_create(
            learner_id, f"ws_{secrets.token_urlsafe(18)}"
        )
        if public_id not in {PUBLIC_WORKSPACE_ID, workspace.id}:
            raise WorkspaceResourceNotFound("resource_not_found")
        return workspace

    async def update(self, learner_id: str, public_id: str, body: dict[str, Any]) -> Workspace:
        workspace = await self.resolve(learner_id, public_id)
        name = workspace.name
        appearance = workspace.appearance
        if "name" in body:
            name = str(body["name"]).strip()[:160] or name
        if "appearance" in body and isinstance(body["appearance"], dict):
            appearance = dict(body["appearance"])
        return (
            await self._repository.update(workspace.id, name=name, appearance=appearance)
            or workspace
        )
