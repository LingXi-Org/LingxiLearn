"""Workspace domain values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Workspace:
    id: str
    learner_id: str
    name: str
    appearance: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None
