"""Filesystem and registry adapter for shipped skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class SystemSkillCatalog:
    def __init__(self, runtime_state: Any, skills_root: Path) -> None:
        self._runtime_state = runtime_state
        self._skills_root = skills_root

    async def list_entries(self, learner_id: str) -> list[dict[str, Any]]:
        entries = await self._runtime_state.list_skills(learner_id=learner_id)
        result: list[dict[str, Any]] = []
        for entry in entries:
            manifest = self._skills_root / str(entry["skill_id"]) / "SKILL.md"
            result.append(
                {
                    **entry,
                    "content": manifest.read_text(encoding="utf-8") if manifest.is_file() else "",
                }
            )
        return result
