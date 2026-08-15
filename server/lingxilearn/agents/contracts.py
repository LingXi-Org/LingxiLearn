"""Stable contracts exchanged by the coordinator and specialized agents."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator("visual_cue", mode="before")
    @classmethod
    def _none_visual_cue_is_empty(cls, value: Any) -> Any:
        return "" if value is None else value


class HookCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    hook_type: str
    score: float = Field(ge=0, le=100)
    lesson_alignment: float = Field(ge=0, le=100)
    curiosity: float = Field(ge=0, le=100)
    evidence_strength: float = Field(ge=0, le=100)
    rejection_reason: str = ""

    @field_validator("rejection_reason", mode="before")
    @classmethod
    def _none_rejection_reason_is_empty(cls, value: Any) -> Any:
        """Accept model JSON null while keeping the public contract a string."""

        return "" if value is None else value


class ResearchClaim(BaseModel):
    model_config = ConfigDict(extra="allow")

    claim_id: str
    claim: str
    status: Literal["verified", "qualified", "rejected"]
    confidence: float = Field(ge=0, le=1)
    source_ids: list[str] = Field(default_factory=list)
    qualification: str = ""

    @field_validator("qualification", mode="before")
    @classmethod
    def _none_qualification_is_empty(cls, value: Any) -> Any:
        return "" if value is None else value


class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_id: str
    title: str
    url: str
    tier: Literal["A", "B", "C", "D"]
    publisher: str = ""
    published_at: str = ""
    notes: str = ""

    @field_validator("publisher", "published_at", "notes", mode="before")
    @classmethod
    def _none_source_text_is_empty(cls, value: Any) -> Any:
        return "" if value is None else value


class ResearchLedger(BaseModel):
    model_config = ConfigDict(extra="allow")

    search_angles: list[str] = Field(default_factory=list)
    claims: list[ResearchClaim] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)


class LectureHookResult(BaseModel):
    """Subset-plus-compatible representation of lesson-intro-result.v1."""

    model_config = ConfigDict(extra="allow")

    schema_version: Literal["lesson-intro-result.v1"]
    status: Literal["ok", "insufficient_evidence"]
    topic: str
    selected_hook: HookSelection
    candidates: list[HookCandidate] = Field(min_length=1)
    research: ResearchLedger
    warnings: list[str] = Field(default_factory=list)
    task_id: str = ""


class QuizOption(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=500)


class QuizQuestion(BaseModel):
    """Internal quiz contract. ``answer`` and ``explanation`` never cross the API snapshot."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(pattern=r"^q[0-9a-zA-Z_-]+$")
    type: Literal["single_choice", "multi_choice", "short_text"]
    prompt: str = Field(min_length=1, max_length=1200)
    options: list[QuizOption] = Field(default_factory=list, max_length=8)
    points: int = Field(default=1, ge=1, le=100)
    answer: Any
    explanation: str = ""
    keywords: list[str] = Field(default_factory=list, max_length=20)


class QuizGenerationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: Literal["quiz-generation-result.v1"]
    task_id: str
    title: str
    instructions: str
    questions: list[QuizQuestion] = Field(min_length=1, max_length=20)
    total_points: int = Field(ge=1)
    assumptions: list[str] = Field(default_factory=list)


class DeckResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: Literal["interactive-lecture-deck-result.v2.1"]
    task_id: str
    title: str
    status: Literal["ready", "failed"]
    files: dict[str, Any] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    deviations: list[str] = Field(default_factory=list)


def quiz_public(result: dict[str, Any] | QuizGenerationResult) -> dict[str, Any]:
    """Strip all answer keys, explanations and grading hints before rendering."""

    value = result.model_dump(mode="json") if isinstance(result, BaseModel) else dict(result)
    questions = []
    for question in value.get("questions", []):
        questions.append(
            {
                "id": question.get("id"),
                "type": question.get("type"),
                "prompt": question.get("prompt"),
                "options": question.get("options", []),
                "points": question.get("points", 1),
            }
        )
    return {
        "schema_version": "quiz-generation-result.v1",
        "task_id": value.get("task_id", ""),
        "title": value.get("title", "知识点检测"),
        "instructions": value.get("instructions", "每道题只允许提交一次。"),
        "questions": questions,
        "total_points": value.get("total_points", sum(q.get("points", 1) for q in questions)),
    }


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
            # Native Responses summaries can echo the task envelope before
            # the actual contract. Prefer the candidate with contract keys.
            if {"schema_version", "topic", "selected_hook"}.issubset(value):
                return value
            if not any({"schema_version", "topic", "selected_hook"}.issubset(item) for item in candidates if isinstance(item, dict)):
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
