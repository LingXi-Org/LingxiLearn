"""Repository for identity mappings and canonical learner data."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..learner import LearnerContext
from .database import Database
from .models.base import utcnow
from .models.identity import IdentityUser, Learner, LearnerProfile
from .models.learning import LearningPreference, Mastery, Misconception
from .models.workspace import WorkspaceRow


def _json_value(value: Any) -> Any:
    """Round-trip values through JSON so PostgreSQL receives JSON-safe payloads."""

    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


class LearnerRepository:
    """Short-transaction data access for identity-owned learning records."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def resolve_identity(self, issuer: str, subject: str) -> str:
        if not issuer or not subject:
            raise ValueError("issuer and subject are required")
        async with self.db.session() as s:
            existing = await s.scalar(
                select(IdentityUser).where(
                    IdentityUser.issuer == issuer,
                    IdentityUser.subject == subject,
                )
            )
            if existing is not None:
                existing.last_seen_at = utcnow()
                if await s.get(LearnerProfile, existing.learner_id) is None:
                    s.add(LearnerProfile(learner_id=existing.learner_id))
                await s.commit()
                return existing.learner_id

            learner_id = f"l-{uuid4().hex[:24]}"
            s.add(Learner(id=learner_id, display_name=subject[:128]))
            # Make the parent row durable in the current transaction before
            # inserting the identity mapping.  The models intentionally do
            # not define an ORM relationship, so relying on unit-of-work
            # dependency sorting is not safe across SQLAlchemy/Postgres
            # combinations.
            await s.flush()
            s.add(
                IdentityUser(
                    issuer=issuer,
                    subject=subject,
                    learner_id=learner_id,
                )
            )
            s.add(LearnerProfile(learner_id=learner_id))
            try:
                await s.commit()
            except IntegrityError:
                # Two first requests for the same subject may race.  The
                # unique identity constraint makes the winning mapping the
                # only authoritative answer.
                await s.rollback()
                winner = await s.scalar(
                    select(IdentityUser).where(
                        IdentityUser.issuer == issuer,
                        IdentityUser.subject == subject,
                    )
                )
                if winner is None:
                    raise
                winner.last_seen_at = utcnow()
                await s.commit()
                return winner.learner_id
            return learner_id

    async def ensure_learner(self, learner_id: str, display_name: str = "") -> None:
        async with self.db.session() as s:
            existing = await s.get(Learner, learner_id)
            if existing is None:
                s.add(Learner(id=learner_id, display_name=display_name or learner_id))
                await s.commit()

    async def ensure_workspace(self, learner_id: str) -> None:
        """Create the learner workspace once, tolerating concurrent first runs."""

        async with self.db.session() as s:
            existing = await s.scalar(
                select(WorkspaceRow).where(WorkspaceRow.learner_id == learner_id)
            )
            if existing is not None:
                return
            s.add(
                WorkspaceRow(
                    id=f"ws_{uuid4().hex}",
                    learner_id=learner_id,
                    name="灵犀智学",
                    appearance={},
                )
            )
            try:
                await s.commit()
            except IntegrityError:
                await s.rollback()
                winner = await s.scalar(
                    select(WorkspaceRow).where(WorkspaceRow.learner_id == learner_id)
                )
                if winner is None:
                    raise

    async def context_for_identity(
        self, *, issuer: str, subject: str, learner_id: str
    ) -> LearnerContext:
        async with self.db.session() as s:
            mapping = await s.scalar(
                select(IdentityUser).where(
                    IdentityUser.issuer == issuer,
                    IdentityUser.subject == subject,
                    IdentityUser.learner_id == learner_id,
                )
            )
            if mapping is None:
                raise LookupError("identity mapping not found")
            return await self._context(s, mapping.learner_id, subject, issuer)

    async def context_for_learner_id(self, learner_id: str) -> LearnerContext:
        async with self.db.session() as s:
            mapping = await s.scalar(
                select(IdentityUser).where(IdentityUser.learner_id == learner_id)
            )
            if mapping is None:
                raise LookupError("identity mapping not found")
            return await self._context(s, learner_id, mapping.subject, mapping.issuer)

    async def _context(
        self, s: AsyncSession, learner_id: str, subject: str, issuer: str
    ) -> LearnerContext:
        learner = await s.get(Learner, learner_id)
        if learner is None:
            raise LookupError("learner not found")
        profile = await s.get(LearnerProfile, learner_id)
        if profile is None:
            profile = LearnerProfile(learner_id=learner_id)
            s.add(profile)
            await s.commit()

        mastery_rows = (
            await s.execute(
                select(Mastery).where(Mastery.learner_id == learner_id).order_by(Mastery.concept)
            )
        ).scalars()
        misconception_rows = (
            await s.execute(
                select(Misconception)
                .where(
                    Misconception.learner_id == learner_id,
                    Misconception.resolved_at.is_(None),
                )
                .order_by(Misconception.last_seen_at.desc())
            )
        ).scalars()
        preferences = await s.get(LearningPreference, learner_id)
        profile_payload = dict(profile.payload or {})
        profile_view = {
            **profile_payload,
            "locale": profile.locale,
            "level": profile.level,
        }
        return LearnerContext(
            learner_id=learner_id,
            subject=subject,
            issuer=issuer,
            profile=profile_view,
            mastery={row.concept: float(row.score) for row in mastery_rows},
            misconceptions=[
                {
                    "tag": row.tag,
                    "occurrence_count": row.occurrence_count,
                    "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
                    "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
                }
                for row in misconception_rows
            ],
            preferences=dict(preferences.payload or {}) if preferences else {},
        )

    async def mastery_for(
        self, learner_id: str, concepts: Iterable[str] | None = None
    ) -> dict[str, float]:
        requested = {str(item) for item in concepts} if concepts is not None else None
        async with self.db.session() as s:
            query = select(Mastery).where(Mastery.learner_id == learner_id)
            if requested is not None:
                query = query.where(Mastery.concept.in_(requested))
            rows = (await s.execute(query.order_by(Mastery.concept))).scalars()
            return {row.concept: float(row.score) for row in rows}

    async def mastery_detail(self, learner_id: str) -> list[dict[str, Any]]:
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
                    row.updated_at = utcnow()
            await s.commit()

    async def update_preference(
        self, learner_id: str, patch: Mapping[str, Any]
    ) -> LearningPreference:
        if not isinstance(patch, Mapping):
            raise ValueError("preference patch must be an object")
        async with self.db.session() as s:
            row = await s.get(LearningPreference, learner_id)
            if row is None:
                row = LearningPreference(learner_id=learner_id, payload={})
                s.add(row)
            merged = {**dict(row.payload or {}), **_json_value(dict(patch))}
            row.payload = merged
            row.updated_at = utcnow()
            await s.commit()
            return row
