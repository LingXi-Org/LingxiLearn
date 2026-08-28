"""Persistence boundary for the Skill Catalog."""

from __future__ import annotations

from typing import Any, Protocol

from ...domain.skill_catalog import PersonalSkill


class SkillCatalogPort(Protocol):
    async def list_for_learner(self, learner_id: str) -> list[PersonalSkill]: ...

    async def add(self, skill: PersonalSkill) -> PersonalSkill: ...

    async def get_many(self, learner_id: str, skill_ids: set[str]) -> list[PersonalSkill]: ...

    async def update(
        self, skill_id: str, learner_id: str, changes: dict[str, str]
    ) -> PersonalSkill | None: ...

    async def delete(self, skill_id: str, learner_id: str) -> bool: ...


class SystemSkillCatalogPort(Protocol):
    async def list_entries(self, learner_id: str) -> list[dict[str, Any]]: ...
