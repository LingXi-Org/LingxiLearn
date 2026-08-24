from __future__ import annotations

import uuid
from typing import Any

from ..store.models.workspace import PersonalSkill
from ..store.repositories.skills import SkillRepository
from .workspace_errors import WorkspaceDomainError, WorkspaceResourceNotFound


class SkillService:
    def __init__(self, db: Any) -> None:
        self._repository = SkillRepository(db)

    async def create(self, learner_id: str, body: dict[str, Any]) -> PersonalSkill:
        name = str(body.get("name") or "").strip()
        if not name:
            raise WorkspaceDomainError("name_required")
        return await self._repository.add(
            PersonalSkill(
                id=f"skill_{uuid.uuid4().hex}",
                learner_id=learner_id,
                name=name[:128],
                description=str(body.get("description") or ""),
                content=str(body.get("content") or ""),
                version=str(body.get("version") or "1.0.0"),
            )
        )

    async def update(self, learner_id: str, skill_id: str, body: dict[str, Any]) -> PersonalSkill:
        changes = {
            field: str(body[field])
            for field in ("name", "description", "content", "version")
            if field in body
        }
        row = await self._repository.update(skill_id, learner_id, changes)
        if row is None:
            raise WorkspaceResourceNotFound("resource_not_found")
        return row

    async def delete(self, learner_id: str, skill_id: str) -> None:
        if not await self._repository.delete(skill_id, learner_id):
            raise WorkspaceResourceNotFound("resource_not_found")
