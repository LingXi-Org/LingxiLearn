"""Learner-facing runtime state reads and overrides.

Thin but focused owner for the learner dimension of the runtime state store:
the skill catalog, the mastery profile and profile overrides.  Identity and
preference use-cases stay in :class:`~lingxilearn.learner.LearnerService`.
"""

from __future__ import annotations

from typing import Any

from ..store.runtime_state import RuntimeStateRepository


class LearnerStateService:
    def __init__(self, *, runtime_state: RuntimeStateRepository) -> None:
        self._runtime_state = runtime_state

    async def list_skills(self, *, learner_id: str) -> list[dict[str, Any]]:
        return await self._runtime_state.list_skills(learner_id=learner_id)

    async def profile_for(self, learner_id: str) -> list[dict[str, Any]]:
        return await self._runtime_state.profile_for(learner_id)

    async def profile_point(self, learner_id: str, knowledge_point_id: str) -> Any:
        return await self._runtime_state.profile_point(learner_id, knowledge_point_id)

    async def override_profile(
        self,
        *,
        learner_id: str,
        knowledge_point_id: str,
        enabled: bool,
        fields: dict[str, Any] | None = None,
    ) -> Any:
        return await self._runtime_state.override_profile(
            learner_id=learner_id,
            knowledge_point_id=knowledge_point_id,
            enabled=enabled,
            fields=fields,
        )
