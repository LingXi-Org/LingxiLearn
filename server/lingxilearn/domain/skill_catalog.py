"""Skill Catalog domain values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PersonalSkill:
    id: str
    learner_id: str
    name: str
    description: str
    content: str
    version: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
