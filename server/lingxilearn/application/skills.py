from __future__ import annotations

import uuid
from typing import Any

from ..domain.skill_catalog import PersonalSkill
from ..state.capabilities import CAPABILITY_INFO
from .ports.skill_catalog import SkillCatalogPort, SystemSkillCatalogPort
from .workspace_errors import WorkspaceDomainError, WorkspaceResourceNotFound


class SkillService:
    def __init__(
        self, repository: SkillCatalogPort, system_catalog: SystemSkillCatalogPort
    ) -> None:
        self._repository = repository
        self._system_catalog = system_catalog

    async def list_all(self, learner_id: str) -> list[dict[str, Any]]:
        system = [
            {
                "id": entry["skill_id"],
                "name": entry["skill_id"],
                "display_name": entry["display_name"] or entry["skill_id"],
                "description": entry["description"],
                "version": entry["version"],
                "license": "MIT",
                "content": entry["content"],
                "source": entry["source"],
                "is_system": True,
                "capabilities": entry["capabilities"],
                "ownership": entry["ownership"],
                "provider": entry["provider"],
                "cost": entry["cost"],
                "enabled": entry["enabled"],
            }
            for entry in await self._system_catalog.list_entries(learner_id)
        ]
        system.extend(_personal_public(row) for row in await self.list_personal(learner_id))
        return system

    async def registry(self, learner_id: str) -> dict[str, Any]:
        entries = await self._system_catalog.list_entries(learner_id)
        by_capability: dict[str, list[str]] = {}
        for entry in entries:
            if entry["enabled"]:
                for tag in entry["capabilities"]:
                    by_capability.setdefault(tag, []).append(entry["skill_id"])
        return {
            "skills": entries,
            "capabilities": [
                {
                    "capability": str(item.capability),
                    "label": item.label,
                    "learner_facing": item.learner_facing,
                    "heavy_artifact": item.heavy_artifact,
                    "irreversible": item.irreversible,
                    "providers": by_capability.get(str(item.capability), []),
                }
                for item in CAPABILITY_INFO.values()
            ],
        }

    async def list_personal(self, learner_id: str) -> list[PersonalSkill]:
        return await self._repository.list_for_learner(learner_id)

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


def _personal_public(row: PersonalSkill) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "display_name": row.name,
        "description": row.description,
        "content": row.content,
        "version": row.version,
        "source": "personal",
        "is_system": False,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
