"""Artifact domain values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Artifact:
    id: str
    workspace_id: str
    name: str
    mime_type: str
    size: int
    storage_key: str
    path: str
    source: str = "upload"
    task_id: str | None = None
    kind: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    kind: str
    filename: str
    mime_type: str
    content: bytes
