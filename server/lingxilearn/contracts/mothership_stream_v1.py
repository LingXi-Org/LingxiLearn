"""Lingxi Mothership Stream V1 — the public event protocol (issue #18).

One versioned envelope carries every learner-facing fact the Mothership UI
needs::

    turn | text | span | tool | interaction | resource | run | error | complete

Design rules, enforced by validation:

* **Strict shapes.**  Every payload model forbids extra fields, so a new
  internal field cannot silently leak to the browser.
* **Identity is explicit.**  ``stream`` names chat/turn/execution; ``scope``
  names the agent/skill a fact belongs to.  The frontend never infers identity
  from event order or names.
* **No secrets, no internals.**  ``PUBLIC_DENYLIST`` is the second line of
  defence after the schema allowlist; ``validate_public_payload`` drops (and
  reports) any denylisted key.

The TypeScript mirror lives at ``web/lib/lingxi/generated/mothership-stream-v1.ts``
and both sides must accept the shared JSON fixtures in
``contracts/fixtures/mothership-stream-v1/``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

PROTOCOL_VERSION: Final[Literal[1]] = 1

EventType = Literal[
    "turn",
    "text",
    "span",
    "tool",
    "interaction",
    "resource",
    "run",
    "error",
    "complete",
]

TextChannel = Literal["assistant", "narration"]
PresentationRole = Literal["primary", "supporting", "background"]
ExecutionKind = Literal["model", "deterministic"]
SpanStatus = Literal[
    "queued", "running", "awaiting_user", "completed", "failed", "cancelled"
]
ToolKind = Literal["skill", "tool"]
ToolStatus = Literal[
    "call",
    "generating",
    "executing",
    "awaiting_approval",
    "success",
    "error",
    "cancelled",
    "skipped",
    "rejected",
]
RunStatus = Literal[
    "started", "checkpoint_pause", "resumed", "completed", "failed", "cancelled"
]
TurnStatus = Literal[
    "started", "awaiting_user", "resumed", "delivered", "failed", "cancelled"
]

# Keys that must never appear in a public payload — the schema allowlist is the
# primary defence; this catches projection bugs (issue #18 §20.1).
PUBLIC_DENYLIST: frozenset[str] = frozenset(
    {
        "reasoning",
        "reasoning_content",
        "thinking",
        "hypotheses",
        "candidates_considered",
        "candidate_id",
        "__runtime_node_id",
        "__work_item_id",
        "__runtime_step",
        "plan",
        "checkpoint",
        "checkpoint_id",
        "api_key",
        "token",
        "password",
        "authorization",
        "html",
        "body",
    }
)

_DENYLIST_PATTERN = re.compile(
    r"(?:^|[_-])(?:api[_-]?key|token|secret|password|authorization)(?:$|[_-])",
    re.IGNORECASE,
)


class V1Model(BaseModel):
    """Base: strict, forward-compatible-but-explicit.

    Fields are snake_case in Python and camelCase on the wire (matching the
    protocol examples); both spellings validate.
    """

    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
    )


class StreamScope(V1Model):
    chat_id: str
    turn_id: str = ""
    execution_id: str = ""
    stream_id: str = ""


class EventScope(V1Model):
    agent_run_id: str = ""
    parent_agent_run_id: str = ""
    skill_run_id: str = ""


class TraceScope(V1Model):
    request_id: str = ""
    run_id: str = ""


class LingxiMothershipEventV1(V1Model):
    """The envelope every public event travels in."""

    v: Literal[1] = PROTOCOL_VERSION
    seq: int = Field(ge=0)
    ts: str
    type: EventType
    stream: StreamScope
    scope: EventScope = Field(default_factory=EventScope)
    trace: TraceScope = Field(default_factory=TraceScope)
    payload: dict[str, Any] = Field(default_factory=dict)


# -- payload shapes ---------------------------------------------------------


class TurnPayload(V1Model):
    turn_id: str
    turn_index: int = Field(default=0, ge=0)
    status: TurnStatus
    user_text: str = ""
    """The learner's input for this turn; present on ``started`` events so a
    refreshed transcript can rebuild the user bubbles without V0 history."""


class TextPayload(V1Model):
    channel: TextChannel
    delta: str = ""
    text: str = ""
    """Full text when this event closes a stream; empty while streaming."""
    stream_id: str = ""
    source: Literal["agent", "system"] = "agent"
    code: str = ""
    """Optional stable narration code, e.g. ``skill.status_line``."""


class SpanStartPayload(V1Model):
    kind: Literal["agent"] = "agent"
    event: Literal["start"] = "start"
    agent_run_id: str
    provider_id: str = ""
    display_name: str = ""
    execution_kind: ExecutionKind = "model"
    capability: str = ""
    presentation_role: PresentationRole = "supporting"
    parent_agent_run_id: str = ""
    skill_ids: list[str] = Field(default_factory=list)


class SpanEndPayload(V1Model):
    kind: Literal["agent"] = "agent"
    event: Literal["end"] = "end"
    agent_run_id: str
    status: SpanStatus = "completed"
    detail: str = ""


class ToolPayload(V1Model):
    tool_call_id: str
    tool_kind: ToolKind = "tool"
    tool_name: str
    display_title: str = ""
    status: ToolStatus = "call"
    safe_params: dict[str, Any] = Field(default_factory=dict)
    safe_result: dict[str, Any] = Field(default_factory=dict)
    started_at: str = ""
    ended_at: str = ""


class InteractionQuestionPayload(V1Model):
    id: str
    type: Literal["single_select", "multi_select"] = "single_select"
    prompt: str
    options: list[dict[str, str]] = Field(default_factory=list)
    allow_free_text: bool = False


class InteractionRequestedPayload(V1Model):
    interaction_id: str
    purpose: Literal["clarification", "assessment", "confirmation"] = "clarification"
    presentation: Literal["question", "options"] = "question"
    blocking: bool = True
    title: str = ""
    prompt: str = ""
    questions: list[InteractionQuestionPayload] = Field(default_factory=list)
    reason_code: str = ""
    dismissible: bool = False


class InteractionResolvedPayload(V1Model):
    interaction_id: str
    answers: list[dict[str, Any]] = Field(default_factory=list)


class ResourceDescriptor(V1Model):
    id: str
    type: Literal["file", "table", "knowledgebase", "task", "skill"] = "file"
    title: str = ""
    path: str = ""
    source_agent_run_id: str = ""
    artifact_kind: str = ""
    mime_type: str = ""


class ResourceUpsertPayload(V1Model):
    resource: ResourceDescriptor
    removed: bool = False


class RunPayload(V1Model):
    status: RunStatus
    execution_id: str = ""
    interaction_id: str = ""
    """Present only on ``checkpoint_pause``; the checkpoint id itself is opaque
    and never published."""
    detail: str = ""


class ErrorPayload(V1Model):
    message: str
    code: str = ""
    fatal: bool = False


class CompletePayload(V1Model):
    status: Literal["delivered", "failed", "cancelled", "awaiting_user"] = "delivered"
    finished_reason: str = ""


# -- validation helpers ------------------------------------------------------


def validate_public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop denylisted keys and reject non-JSON-safe values.

    Unknown Python objects are omitted — never ``repr()``/``str()``-ed into the
    learner UI (issue #18 §20.2).
    """

    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if key in PUBLIC_DENYLIST or _DENYLIST_PATTERN.search(str(key)):
            continue
        if isinstance(value, dict):
            cleaned[str(key)] = validate_public_payload(value)
        elif isinstance(value, (list, tuple)):
            cleaned[str(key)] = [
                validate_public_payload(item)
                if isinstance(item, dict)
                else _public_scalar(item)
                for item in value
            ]
        else:
            cleaned[str(key)] = _public_scalar(value)
    return cleaned


def _public_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # Unknown object types intentionally degrade to an omitted marker rather
    # than a repr; the schema allowlist should have caught them earlier.
    return None


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class LingxiMothershipStreamV1Encoder:
    """Builds validated V1 envelopes.

    The projector owns the sequence numbers; this encoder only guarantees that
    whatever it emits parses against :class:`LingxiMothershipEventV1` and the
    payload schema for its type.
    """

    PAYLOAD_MODELS: dict[str, tuple[type[V1Model], ...]] = {
        "turn": (TurnPayload,),
        "text": (TextPayload,),
        "span": (SpanStartPayload, SpanEndPayload),
        "tool": (ToolPayload,),
        "interaction": (InteractionRequestedPayload, InteractionResolvedPayload),
        "resource": (ResourceUpsertPayload,),
        "run": (RunPayload,),
        "error": (ErrorPayload,),
        "complete": (CompletePayload,),
    }

    def encode(
        self,
        *,
        seq: int,
        event_type: EventType,
        payload: dict[str, Any],
        stream: StreamScope,
        scope: EventScope | None = None,
        trace: TraceScope | None = None,
        ts: str | None = None,
    ) -> LingxiMothershipEventV1:
        cleaned = validate_public_payload(payload)
        event = LingxiMothershipEventV1(
            seq=seq,
            ts=ts or now_iso(),
            type=event_type,
            stream=stream,
            scope=scope or EventScope(),
            trace=trace or TraceScope(),
            payload=cleaned,
        )
        self._validate_payload_shape(event_type, cleaned)
        return event

    @staticmethod
    def _validate_payload_shape(event_type: str, payload: dict[str, Any]) -> None:
        candidates = LingxiMothershipStreamV1Encoder.PAYLOAD_MODELS.get(event_type)
        if candidates is None:
            raise ValueError(f"unknown V1 event type: {event_type}")
        for candidate in candidates:
            try:
                candidate.model_validate(payload)
                return
            except Exception:  # noqa: BLE001 - try the next member of the union
                continue
        raise ValueError(f"payload does not match any V1 {event_type} shape")


__all__ = [
    "CompletePayload",
    "ErrorPayload",
    "EventType",
    "InteractionRequestedPayload",
    "InteractionResolvedPayload",
    "LingxiMothershipEventV1",
    "LingxiMothershipStreamV1Encoder",
    "PROTOCOL_VERSION",
    "PUBLIC_DENYLIST",
    "ResourceDescriptor",
    "ResourceUpsertPayload",
    "RunPayload",
    "SpanEndPayload",
    "SpanStartPayload",
    "StreamScope",
    "TextPayload",
    "ToolPayload",
    "TurnPayload",
    "validate_public_payload",
]
