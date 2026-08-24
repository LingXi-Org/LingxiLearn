from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ..models.workspace import PersonalSkill


class SkillRepository:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def add(self, row: PersonalSkill) -> PersonalSkill:
        async with self._db.session() as session:
            session.add(row)
            await session.commit()
            return row

    async def get(self, skill_id: str, learner_id: str) -> PersonalSkill | None:
        async with self._db.session() as session:
            return await session.scalar(
                select(PersonalSkill).where(
                    PersonalSkill.id == skill_id, PersonalSkill.learner_id == learner_id
                )
            )

    async def update(
        self, skill_id: str, learner_id: str, changes: dict[str, str]
    ) -> PersonalSkill | None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(PersonalSkill).where(
                    PersonalSkill.id == skill_id, PersonalSkill.learner_id == learner_id
                )
            )
            if row is None:
                return None
            for field, value in changes.items():
                setattr(row, field, value)
            await session.commit()
            return row

    async def delete(self, skill_id: str, learner_id: str) -> bool:
        async with self._db.session() as session:
            row = await session.scalar(
                select(PersonalSkill).where(
                    PersonalSkill.id == skill_id, PersonalSkill.learner_id == learner_id
                )
            )
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True
