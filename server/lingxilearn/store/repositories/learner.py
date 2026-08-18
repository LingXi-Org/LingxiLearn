"""Learner and identity persistence operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .database import Database
from .models import IdentityUser, Learner, LearnerProfile, Mastery


class LearnerRepository:
    """Repository for learner-related operations."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def ensure_learner(self, learner_id: str, display_name: str = "") -> None:
        """Create learner if not exists."""
        async with self.db.session() as s:
            existing = await s.get(Learner, learner_id)
            if existing is None:
                s.add(Learner(id=learner_id, display_name=display_name or learner_id))
                await s.commit()

    async def get_learner(self, learner_id: str) -> Learner | None:
        """Get learner by ID."""
        async with self.db.session() as s:
            return await s.get(Learner, learner_id)

    async def get_identity_user(
        self, issuer: str, subject: str
    ) -> IdentityUser | None:
        """Get identity user by issuer and subject."""
        async with self.db.session() as s:
            return await s.scalar(
                select(IdentityUser).where(
                    IdentityUser.issuer == issuer,
                    IdentityUser.subject == subject,
                )
            )

    async def map_identity_to_learner(
        self, issuer: str, subject: str, learner_id: str
    ) -> IdentityUser:
        """Map identity to learner, creating mapping if needed."""
        async with self.db.session() as s:
            existing = await s.scalar(
                select(IdentityUser).where(
                    IdentityUser.issuer == issuer,
                    IdentityUser.subject == subject,
                )
            )
            if existing:
                existing.learner_id = learner_id
                existing.last_seen_at = Learner.updated_at  # Will be set by ORM
                await s.commit()
                return existing

            s.add(
                IdentityUser(
                    issuer=issuer,
                    subject=subject,
                    learner_id=learner_id,
                )
            )
            await s.commit()
            await s.refresh(existing)
            return existing

    async def get_learner_profile(self, learner_id: str) -> LearnerProfile | None:
        """Get learner profile."""
        async with self.db.session() as s:
            return await s.get(LearnerProfile, learner_id)

    async def update_learner_profile(
        self, learner_id: str, **fields: Any
    ) -> LearnerProfile:
        """Update learner profile fields."""
        async with self.db.session() as s:
            profile = await s.get(LearnerProfile, learner_id)
            if profile is None:
                profile = LearnerProfile(learner_id=learner_id, **fields)
                s.add(profile)
            else:
                for key, value in fields.items():
                    setattr(profile, key, value)
            await s.commit()
            await s.refresh(profile)
            return profile

    async def mastery_for(self, learner_id: str) -> dict[str, float]:
        """Get mastery scores for learner."""
        async with self.db.session() as s:
            rows = (
                await s.execute(select(Mastery).where(Mastery.learner_id == learner_id))
            ).scalars()
            return {row.concept: row.score for row in rows}

    async def mastery_detail(self, learner_id: str) -> list[dict[str, Any]]:
        """Get detailed mastery information."""
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(Mastery)
                    .where(Mastery.learner_id == learner_id)
                    .order_by(Mastery.concept)
                )
            ).scalars()
            return [
                {
                    "concept": r.concept,
                    "score": round(r.score, 4),
                    "evidence_count": r.evidence_count,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in rows
            ]

    async def save_mastery(self, learner_id: str, scores: dict[str, float]) -> None:
        """Save or update mastery scores."""
        if not scores:
            return
        async with self.db.session() as s:
            existing = {
                row.concept: row
                for row in (
                    await s.execute(select(Mastery).where(Mastery.learner_id == learner_id))
                ).scalars()
            }
            for concept, score in scores.items():
                row = existing.get(concept)
                if row is None:
                    s.add(
                        Mastery(
                            learner_id=learner_id,
                            concept=concept,
                            score=float(score),
                            evidence_count=1,
                        )
                    )
                else:
                    row.score = float(score)
                    row.evidence_count += 1
                    row.updated_at = Mastery.updated_at  # Will be set by ORM
            await s.commit()