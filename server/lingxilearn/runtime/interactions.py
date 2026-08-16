"""Structured HITL interactions (issue #18).

The current ``await_user`` puts raw checkpoint state (messages, plan) into the
interrupt value, which leaks internal plan objects into the learner UI.  This
module defines the typed replacement:

* :class:`InteractionSpec` — structured data an orchestrator may attach to an
  :class:`~lingxilearn.runtime.contracts.OrchestrationPlan`; questions,
  options, purpose and a reason code.  No checkpoint state, ever.
* :func:`opaque_interrupt_payload` — the *only* thing that goes into
  ``interrupt()``: the opaque interaction id.  The full request is durable in
  ``agent_interactions`` before the graph pauses.
* :func:`resume_command` — the continuation command an interaction answer
  produces.  It resumes the original checkpoint within the same turn.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

Purpose = Literal["clarification", "assessment", "confirmation"]
Presentation = Literal["question", "options"]
QuestionType = Literal["single_select", "multi_select"]
InteractionStatus = Literal["pending", "resolved", "dismissed", "cancelled"]


class _WireModel(BaseModel):
    """Wire models speak camelCase JSON and accept both spellings."""

    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
    )


class InteractionOption(_WireModel):
    id: str
    label: str


class InteractionQuestion(_WireModel):
    """One question with explicit, machine-readable answers."""

    id: str
    type: QuestionType = "single_select"
    prompt: str = Field(min_length=1)
    options: list[InteractionOption] = Field(default_factory=list)
    allow_free_text: bool = False

    @model_validator(mode="after")
    def _options_required_for_select(self) -> InteractionQuestion:
        if self.type in {"single_select", "multi_select"} and len(self.options) < 2:
            raise ValueError(f"{self.type} question needs at least two options")
        if self.type == "single_select" and self.allow_free_text is False and not self.options:
            raise ValueError("question without options must allow free text")
        return self


class InteractionSpec(_WireModel):
    """The structured interaction an orchestrator may request.

    ``blocking=True`` pauses the graph at a checkpoint and renders
    ``QuestionDisplay``; the answer resumes the same turn.  ``blocking=False``
    renders ``OptionsDisplay`` as a non-blocking suggestion for the next turn.
    """

    interaction_id: str = ""
    """Assigned by the host when the request is persisted; models leave it empty."""
    purpose: Purpose = "clarification"
    presentation: Presentation = "question"
    blocking: bool = True
    title: str = ""
    prompt: str = ""
    questions: list[InteractionQuestion] = Field(default_factory=list)
    reason_code: str = Field(min_length=1)
    """Stable machine code (e.g. ``goal_ambiguous``) for analytics and tests."""
    dismissible: bool = False

    @model_validator(mode="after")
    def _shape_matches_presentation(self) -> InteractionSpec:
        if self.presentation == "question" and not self.questions:
            if not self.prompt:
                raise ValueError("question interaction needs questions or a prompt")
        if self.presentation == "options" and not self.questions:
            raise ValueError("options interaction needs at least one question with options")
        return self

    def public_request(self) -> dict[str, Any]:
        """The whitelisted payload the frontend may render.

        This is the *only* shape that may reach the browser for an interaction;
        anything else in an interrupt payload is a projection bug.
        """

        return self.model_dump(mode="json", exclude_none=True, by_alias=True)


class InteractionAnswer(_WireModel):
    """One question's answer as submitted through the structured API."""

    question_id: str
    selected_option_ids: list[str] = Field(default_factory=list)
    text: str | None = None

    @model_validator(mode="after")
    def _non_empty(self) -> InteractionAnswer:
        if not self.selected_option_ids and not (self.text or "").strip():
            raise ValueError("answer must select an option or provide text")
        return self


def opaque_interrupt_payload(interaction_id: str) -> dict[str, Any]:
    """The interrupt value: identity only, never checkpoint/graph state."""

    return {"kind": "interaction", "interaction_id": interaction_id}


def is_interaction_interrupt(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("kind") == "interaction"
        and bool(value.get("interaction_id"))
    )


def resume_command(interaction_id: str, answers: list[InteractionAnswer]) -> dict[str, Any]:
    """The continuation payload for ``Command(resume=...)`` after an answer.

    It stays within the current turn: the host resumes the original checkpoint
    rather than initialising a new graph input.
    """

    return {
        "kind": "interaction_answer",
        "interaction_id": interaction_id,
        "answers": [answer.model_dump(mode="json", by_alias=True) for answer in answers],
    }


def parse_answers(raw: Any) -> list[InteractionAnswer]:
    """Validate submitted answers against the strict schema."""

    if not isinstance(raw, list):
        raise ValueError("answers must be a list")
    return [InteractionAnswer.model_validate(item) for item in raw]


__all__ = [
    "InteractionAnswer",
    "InteractionOption",
    "InteractionQuestion",
    "InteractionSpec",
    "InteractionStatus",
    "is_interaction_interrupt",
    "opaque_interrupt_payload",
    "parse_answers",
    "resume_command",
]
