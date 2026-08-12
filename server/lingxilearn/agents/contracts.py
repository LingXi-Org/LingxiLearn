"""Stable contracts exchanged by the coordinator and specialized agents."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class IntentContext(BaseModel):
    """The normalized teaching context passed to both specialized agents."""

    model_config = ConfigDict(extra="ignore")

    topic: str = Field(min_length=1, max_length=300)
    learning_objective: str = Field(default="", max_length=500)
    learner_level: str = Field(default="undergraduate", max_length=120)
    course_context: str = Field(default="", max_length=500)
    language: str = Field(default="zh-CN", max_length=32)
    target_duration_sec: int = Field(default=75, ge=20, le=180)


class HookSelection(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    hook_type: str
    opening: str
    story: str
    question: str
    transition: str
    estimated_duration_sec: int = Field(ge=10, le=180)
    why_this_hook_works: str
    visual_cue: str = ""


class HookCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    hook_type: str
    score: float = Field(ge=0, le=100)
    lesson_alignment: float = Field(ge=0, le=100)
    curiosity: float = Field(ge=0, le=100)
    evidence_strength: float = Field(ge=0, le=100)
    rejection_reason: str = ""


class ResearchClaim(BaseModel):
    model_config = ConfigDict(extra="allow")

    claim_id: str
    claim: str
    status: Literal["verified", "qualified", "rejected"]
    confidence: float = Field(ge=0, le=1)
    source_ids: list[str] = Field(default_factory=list)
    qualification: str = ""


class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_id: str
    title: str
    url: str
    tier: Literal["A", "B", "C", "D"]
    publisher: str = ""
    published_at: str = ""
    notes: str = ""


class ResearchLedger(BaseModel):
    model_config = ConfigDict(extra="allow")

    search_angles: list[str] = Field(default_factory=list)
    claims: list[ResearchClaim] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)


class LectureHookResult(BaseModel):
    """Subset-plus-compatible representation of lecture-hook-result.v1."""

    model_config = ConfigDict(extra="allow")

    schema_version: Literal["lecture-hook-result.v1"]
    status: Literal["ok", "insufficient_evidence"]
    topic: str
    selected_hook: HookSelection
    candidates: list[HookCandidate] = Field(min_length=1)
    research: ResearchLedger
    warnings: list[str] = Field(default_factory=list)
    task_id: str = ""


class AgentTaskState(dict):
    """Documentation-only state shape used by the coordinator graph."""


def extract_json(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from a model response with optional prose/fences."""

    if not text:
        return None
    candidates = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates.append(text)
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            return value
    return None


def jsonable(value: Any) -> Any:
    """Convert Pydantic/dataclass-like values to JSON-safe data."""

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value
