"""Stable learner-facing service contract.

This module is the boundary between identity and learning data.  Callers pass
the verified Principal, never a subject or internal learner id obtained from a
request body or URL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lingxi_identity import Principal  # type: ignore[import-untyped]

from .config import Settings

if TYPE_CHECKING:
    from .store.learner import LearnerRepository
    from .store.models.learning import LearningPreference


@dataclass(slots=True)
class LearnerContext:
    """Resolved identity plus the current canonical learning snapshot."""

    learner_id: str
    subject: str
    issuer: str
    profile: dict[str, Any]
    mastery: dict[str, float]
    misconceptions: list[dict[str, Any]]
    preferences: dict[str, Any]

    def public_dict(self) -> dict[str, Any]:
        """Return context without exposing internal identity keys."""

        return {
            "profile": self.profile,
            "mastery": self.mastery,
            "misconceptions": self.misconceptions,
            "preferences": self.preferences,
        }


class LearnerService:
    """Application service for the minimum personalized-learning data layer."""

    def __init__(self, repository: LearnerRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    async def get_learner_context(self, principal: Principal) -> LearnerContext:
        issuer = principal.issuer or "lingxi-identity"
        if not principal.subject:
            raise ValueError("principal subject is required")
        learner_id = await self.repository.resolve_identity(issuer, principal.subject)
        return await self.repository.context_for_identity(
            issuer=issuer,
            subject=principal.subject,
            learner_id=learner_id,
        )

    async def context_for_learner_id(self, learner_id: str) -> LearnerContext:
        """Resolve an internal id for trusted server-side terminal persistence."""

        return await self.repository.context_for_learner_id(learner_id)

    async def get_mastery(
        self, context: LearnerContext, concepts: list[str] | None = None
    ) -> dict[str, float]:
        return await self.repository.mastery_for(context.learner_id, concepts=concepts)

    async def update_preference(
        self, context: LearnerContext, patch: dict[str, Any]
    ) -> LearningPreference:
        return await self.repository.update_preference(context.learner_id, patch)
