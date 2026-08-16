"""Lingxi Mothership Stream V1 contract tests (issue #18 §23.1).

The shared fixtures in ``contracts/fixtures/mothership-stream-v1/`` are the
Python ↔ TypeScript gate: this module proves the Python projector reproduces
them exactly and that every envelope validates against the versioned schema.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from lingxilearn.contracts.mothership_stream_v1 import (
    PUBLIC_DENYLIST,
    EventScope,
    InteractionRequestedPayload,
    LingxiMothershipEventV1,
    LingxiMothershipStreamV1Encoder,
    ResourceUpsertPayload,
    StreamScope,
    ToolPayload,
    validate_public_payload,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_DIR = REPO_ROOT / "contracts" / "fixtures" / "mothership-stream-v1"
SCENARIOS = sorted(FIXTURE_DIR.glob("*.json"))


def _encoder() -> LingxiMothershipStreamV1Encoder:
    return LingxiMothershipStreamV1Encoder()


def _stream() -> StreamScope:
    return StreamScope(chat_id="t1", turn_id="turn1", execution_id="exec1", stream_id="s1")


# -- envelope strictness ------------------------------------------------------


def test_envelope_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        LingxiMothershipEventV1.model_validate(
            {
                "v": 1,
                "seq": 1,
                "ts": "2026-01-01T00:00:00Z",
                "type": "run",
                "stream": {"chatId": "t1"},
                "payload": {"status": "started"},
                "hypotheses": ["should not be here"],
            }
        )


def test_envelope_rejects_unknown_event_type() -> None:
    with pytest.raises(ValidationError):
        LingxiMothershipEventV1.model_validate(
            {
                "v": 1,
                "seq": 1,
                "ts": "2026-01-01T00:00:00Z",
                "type": "whisper",
                "stream": {"chatId": "t1"},
                "payload": {},
            }
        )


def test_encoder_validates_payload_shape() -> None:
    encoder = _encoder()
    with pytest.raises(ValueError, match="run"):
        encoder.encode(
            seq=1,
            event_type="run",
            payload={"status": "warp_speed"},
            stream=_stream(),
        )


def test_encoder_accepts_camel_case_and_validates_shape() -> None:
    encoder = _encoder()
    event = encoder.encode(
        seq=3,
        event_type="tool",
        payload={
            "toolCallId": "call_1",
            "toolKind": "skill",
            "toolName": "lingxi.skill",
            "displayTitle": "自适应教学",
            "status": "success",
        },
        stream=_stream(),
        scope=EventScope(agent_run_id="ar_1", skill_run_id="sr_1"),
    )
    assert event.payload["toolCallId"] == "call_1"
    ToolPayload.model_validate(event.payload)


def test_encoder_accepts_snake_case_aliases() -> None:
    encoder = _encoder()
    event = encoder.encode(
        seq=4,
        event_type="run",
        payload={"status": "resumed", "execution_id": "exec_9"},
        stream=_stream(),
    )
    assert event.payload["execution_id"] == "exec_9"


# -- privacy rules --------------------------------------------------------------


def test_denylist_keys_are_dropped_from_public_payloads() -> None:
    cleaned = validate_public_payload(
        {
            "status": "completed",
            "reasoning": "chain of thought",
            "hypotheses": ["h1"],
            "candidates_considered": [{"candidate_id": "c1"}],
            "nested": {"plan": {"tasks": []}, "ok": 1},
            "api_key": "sk-secret",
            "X-Auth-Token": "bearer ...",
        }
    )
    assert cleaned["status"] == "completed"
    assert "reasoning" not in cleaned
    assert "hypotheses" not in cleaned
    assert "candidates_considered" not in cleaned
    assert "api_key" not in cleaned
    assert "X-Auth-Token" not in cleaned
    assert "plan" not in cleaned["nested"]
    assert cleaned["nested"]["ok"] == 1


def test_unknown_objects_are_omitted_never_repr() -> None:
    class Secretive:
        def __repr__(self) -> str:  # pragma: no cover - must not be called
            return "SECRET-REPR"

    cleaned = validate_public_payload({"status": "running", "checkpoint": Secretive()})
    assert "SECRET-REPR" not in json.dumps(cleaned)
    assert "checkpoint" not in cleaned


def test_denylist_covers_the_required_keys() -> None:
    for key in ("reasoning", "thinking", "hypotheses", "plan", "checkpoint_id", "api_key"):
        assert key in PUBLIC_DENYLIST


# -- payload shapes --------------------------------------------------------------


def test_interaction_request_payload_is_strict() -> None:
    payload = InteractionRequestedPayload.model_validate(
        {
            "interactionId": "it_1",
            "purpose": "clarification",
            "presentation": "question",
            "blocking": True,
            "prompt": "你想先学哪个方向？",
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
            "reasonCode": "goal_ambiguous",
        }
    )
    assert payload.questions[0].options[1]["label"] == "解题训练"
    with pytest.raises(ValidationError):
        InteractionRequestedPayload.model_validate(
            {"interactionId": "it_2", "hiddenPlan": {"tasks": []}}
        )


def test_resource_payload_is_strict() -> None:
    ResourceUpsertPayload.model_validate(
        {
            "resource": {
                "id": "file_1",
                "type": "file",
                "title": "可视化讲解",
                "artifactKind": "visual",
            },
            "removed": False,
        }
    )
    with pytest.raises(ValidationError):
        ResourceUpsertPayload.model_validate(
            {"resource": {"id": "file_1", "type": "terminal"}}
        )


# -- shared fixtures --------------------------------------------------------------


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_fixture_envelopes_validate_against_the_schema(path: Path) -> None:
    envelopes = json.loads(path.read_text(encoding="utf-8"))
    assert envelopes, f"{path.name} is empty"
    previous_seq = 0
    for envelope in envelopes:
        event = LingxiMothershipEventV1.model_validate(envelope)
        assert event.seq > previous_seq
        previous_seq = event.seq
        dumped = json.dumps(envelope, ensure_ascii=False)
        for banned in ("reasoning", "hypotheses", "SECRET", "password"):
            assert banned not in dumped, f"{path.name} leaks {banned}"


def test_blocking_pause_fixture_leaks_no_checkpoint_state() -> None:
    envelopes = json.loads(
        (FIXTURE_DIR / "blocking-question-pause.json").read_text(encoding="utf-8")
    )
    pause = [e for e in envelopes if e["payload"].get("status") == "checkpoint_pause"]
    assert len(pause) == 1
    dumped = json.dumps(pause[0]["payload"], ensure_ascii=False)
    assert "plan" not in dumped
    assert "内部消息" not in dumped
    assert set(pause[0]["payload"]) <= {"status", "executionId", "interactionId"}


def test_parallel_fixture_has_two_distinct_overlapping_agent_runs() -> None:
    envelopes = json.loads(
        (FIXTURE_DIR / "parallel-siblings.json").read_text(encoding="utf-8")
    )
    starts = [
        e["payload"]["agentRunId"]
        for e in envelopes
        if e["type"] == "span" and e["payload"].get("event") == "start"
    ]
    assert len(starts) == 2
    assert len(set(starts)) == 2
    ends = [
        e["payload"]["agentRunId"]
        for e in envelopes
        if e["type"] == "span" and e["payload"].get("event") == "end"
    ]
    assert sorted(ends) == sorted(starts)


def test_single_primary_agent_fixture_shapes() -> None:
    envelopes = json.loads(
        (FIXTURE_DIR / "single-primary-agent.json").read_text(encoding="utf-8")
    )
    span_starts = [e for e in envelopes if e["type"] == "span" and e["payload"]["event"] == "start"]
    assert len(span_starts) == 1
    assert span_starts[0]["payload"]["presentationRole"] == "primary"
    assert span_starts[0]["scope"]["agentRunId"] == span_starts[0]["payload"]["agentRunId"]

    tools = [e for e in envelopes if e["type"] == "tool"]
    skill_calls = [e for e in tools if e["payload"]["toolKind"] == "skill"]
    assert len(skill_calls) >= 2  # start + success
    web_search = [e for e in tools if e["payload"].get("toolName") == "web_search"]
    assert web_search, "web_search tool events must be projected"
    result = [e for e in web_search if e["payload"]["status"] == "success"][0]
    assert "huge ranked blob" not in json.dumps(result, ensure_ascii=False)
    assert result["payload"]["safeResult"]["ok"] is True

    assistant = [e for e in envelopes if e["type"] == "text" and e["payload"]["channel"] == "assistant"]
    assert assistant and assistant[-1]["payload"]["text"]
    narration = [e for e in envelopes if e["type"] == "text" and e["payload"]["channel"] == "narration"]
    assert narration and narration[0]["scope"]["agentRunId"] == "ar_answer1"
