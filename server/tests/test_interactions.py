"""Typed HITL interaction contract tests (issue #18 §5.6/§10)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lingxilearn.runtime.interactions import (
    InteractionAnswer,
    InteractionQuestion,
    InteractionSpec,
    is_interaction_interrupt,
    opaque_interrupt_payload,
    parse_answers,
    resume_command,
)


def _spec(**overrides: object) -> InteractionSpec:
    base: dict = {
        "purpose": "clarification",
        "presentation": "question",
        "blocking": True,
        "prompt": "你想先学哪个方向？",
        "reason_code": "goal_ambiguous",
        "questions": [
            {
                "id": "q1",
                "type": "single_select",
                "prompt": "学习目标偏向？",
                "options": [
                    {"id": "o1", "label": "概念理解"},
                    {"id": "o2", "label": "解题训练"},
                ],
                "allow_free_text": True,
            }
        ],
    }
    base.update(overrides)
    return InteractionSpec.model_validate(base)


def test_spec_requires_reason_code() -> None:
    with pytest.raises(ValidationError):
        InteractionSpec.model_validate({"prompt": "没有 reason code", "presentation": "question"})


def test_select_question_needs_two_options() -> None:
    with pytest.raises(ValidationError):
        InteractionQuestion.model_validate(
            {
                "id": "q1",
                "type": "single_select",
                "prompt": "只有一项",
                "options": [{"id": "o1", "label": "唯一选项"}],
            }
        )


def test_options_presentation_requires_questions_with_options() -> None:
    with pytest.raises(ValidationError):
        InteractionSpec.model_validate(
            {"presentation": "options", "reason_code": "next_step_suggestion"}
        )


def test_public_request_is_whitelisted_shape() -> None:
    spec = _spec()
    request = spec.public_request()
    assert request["questions"][0]["options"][0]["id"] == "o1"
    assert request["reasonCode"] == "goal_ambiguous"
    # No checkpoint/graph fields can appear: the model forbids extras.
    with pytest.raises(ValidationError):
        InteractionSpec.model_validate({**_spec().model_dump(), "plan": {"tasks": []}})


def test_opaque_interrupt_payload_carries_identity_only() -> None:
    payload = opaque_interrupt_payload("it_1")
    assert payload == {"kind": "interaction", "interaction_id": "it_1"}
    assert is_interaction_interrupt(payload)
    assert not is_interaction_interrupt({"kind": "user_message", "messages": [], "plan": {}})
    assert not is_interaction_interrupt("raw string")


def test_resume_command_round_trips_structured_answers() -> None:
    answers = parse_answers([{"questionId": "q1", "selectedOptionIds": ["o2"], "text": None}])
    assert answers == [InteractionAnswer(question_id="q1", selected_option_ids=["o2"])]
    command = resume_command("it_1", answers)
    assert command["kind"] == "interaction_answer"
    assert command["interaction_id"] == "it_1"
    assert command["answers"][0]["selectedOptionIds"] == ["o2"]


def test_parse_answers_rejects_empty_and_malformed() -> None:
    with pytest.raises(ValidationError):
        parse_answers([{"questionId": "q1"}])  # neither options nor text
    with pytest.raises(ValueError):
        parse_answers({"questionId": "q1"})  # type: ignore[arg-type]
    free_text = parse_answers([{"questionId": "q2", "text": "我想先学叠加态"}])
    assert free_text[0].text == "我想先学叠加态"
