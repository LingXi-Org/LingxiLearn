from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ...domain.skill_catalog import PersonalSkill
from ..models.workspace import PersonalSkillRow


def _to_domain(row: PersonalSkillRow) -> PersonalSkill:
    return PersonalSkill(
        id=row.id,
        learner_id=row.learner_id,
        name=row.name,
        description=row.description,
        content=row.content,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SkillRepository:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def list_for_learner(self, learner_id: str) -> list[PersonalSkill]:
        async with self._db.session() as session:
            rows = (
                (
                    await session.execute(
                        select(PersonalSkillRow).where(PersonalSkillRow.learner_id == learner_id)
                    )
                )
                .scalars()
                .all()
            )
            return [_to_domain(row) for row in rows]

    async def add(self, skill: PersonalSkill) -> PersonalSkill:
        row = PersonalSkillRow(
            id=skill.id,
            learner_id=skill.learner_id,
            name=skill.name,
            description=skill.description,
            content=skill.content,
            version=skill.version,
        )
        async with self._db.session() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_domain(row)

    async def get_many(self, learner_id: str, skill_ids: set[str]) -> list[PersonalSkill]:
        if not skill_ids:
            return []
        async with self._db.session() as session:
            rows = (
                (
                    await session.execute(
                        select(PersonalSkillRow).where(
                            PersonalSkillRow.learner_id == learner_id,
                            PersonalSkillRow.id.in_(skill_ids),
                        )
                    )
                )
                .scalars()
                .all()
            )
            return [_to_domain(row) for row in rows]

    async def update(
        self, skill_id: str, learner_id: str, changes: dict[str, str]
    ) -> PersonalSkill | None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(PersonalSkillRow).where(
                    PersonalSkillRow.id == skill_id,
                    PersonalSkillRow.learner_id == learner_id,
                )
            )
            if row is None:
                return None
            for field, value in changes.items():
                setattr(row, field, value)
            await session.commit()
            await session.refresh(row)
            return _to_domain(row)

    async def delete(self, skill_id: str, learner_id: str) -> bool:
        async with self._db.session() as session:
            row = await session.scalar(
                select(PersonalSkillRow).where(
                    PersonalSkillRow.id == skill_id,
                    PersonalSkillRow.learner_id == learner_id,
                )
            )
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True
