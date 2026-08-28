"""Workspace persistence boundary."""

from __future__ import annotations

from typing import Any, Protocol

from ...domain.workspace import Workspace


class WorkspacePort(Protocol):
    async def get_or_create(self, learner_id: str, workspace_id: str) -> Workspace: ...

    async def update(
        self, workspace_id: str, *, name: str, appearance: dict[str, Any]
    ) -> Workspace | None: ...
