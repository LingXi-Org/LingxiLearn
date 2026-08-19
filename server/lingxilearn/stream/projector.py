"""Turn LingxiGraph runtime events into the UI's event vocabulary.

A pure, synchronous function over a list of events — no FastAPI import, no
database, no I/O — so the whole mapping is unit-testable by feeding it
fabricated :class:`~lingxigraph.Event` values.  The projections are then
persisted and replayed to SSE clients, which is what makes ``Last-Event-ID``
resumption fall out for free.

Notes on the runtime's actual behaviour, verified against LingxiGraph 2.1.0
rather than assumed:

* ``NODE_FAILED`` is declared in the enum but never emitted — a node failure
  surfaces as a raised exception out of ``astream``.  Handling it here would be
  dead code, so we don't.
* ``NODE_COMPLETED`` carries the node's state delta under ``data["update"]``.
* ``NODE_RETRYING`` carries the attempt under ``data["value"]``, not
  ``data["attempt"]``.
* Domain events arrive as ``CUSTOM`` with ``data={"channel", "value"}``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any

from lingxigraph import Event, EventKind

STREAM_CHANNEL = "tutor"

# State keys that are large, redundant on the wire, or already delivered as
# their own domain events. Consumers receive those values from the persisted
# domain-event stream rather than repeated runtime-state snapshots.
_BULKY_STATE_KEYS = frozenset(
    {"evidence", "transcript", "tool_outputs", "report", "current_step", "stage", "move"}
)


class Projection(StrEnum):
    RUN_STARTED = "run.started"
    RUN_ENDED = "run.ended"
    RUN_FAILED = "run.failed"
    RUN_PAUSED = "run.paused"
    NODE_STARTED = "node.started"
    NODE_COMPLETED = "node.completed"
    NODE_RETRYING = "node.retrying"
    INTERRUPT_RAISED = "interrupt.raised"
    ASSISTANT_DELTA = "assistant.delta"


@dataclass(frozen=True, slots=True)
class Emission:
    """One thing the UI should react to."""

    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    node: str | None = None
    run_id: str = ""
    key: str = ""
    """Stable identity for the UI element this belongs to (namespace-aware)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "payload": self.payload,
            "node": self.node,
            "run_id": self.run_id,
            "key": self.key,
        }


def _plain(value: Any) -> Any:
    """Best-effort JSON-safe conversion that never raises on an unknown type."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    for attr in ("to_dict", "model_dump"):
        method = getattr(value, attr, None)
        if callable(method):
            try:
                return _plain(method())
            except Exception:  # noqa: BLE001
                break
    if hasattr(value, "__dict__"):
        return {str(k): _plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return repr(value)


class EventProjector:
    """Stateful only in what it needs to de-duplicate replayed events."""

    def __init__(self) -> None:
        self._seen: set[tuple[str, Any]] = set()

    def project(self, event: Event) -> list[Emission]:
        identity = (event.run_id, event.sequence or event.event_id)
        if identity in self._seen:
            return []
        self._seen.add(identity)

        node_key = self._key(event)
        data = dict(event.data or {})

        if event.kind is EventKind.CUSTOM:
            return self._custom(event, data, node_key)

        if event.kind is EventKind.RUN_STARTED:
            return [self._emit(Projection.RUN_STARTED, event, node_key, {})]

        if event.kind is EventKind.RUN_COMPLETED:
            return [self._emit(Projection.RUN_ENDED, event, node_key, {"status": "completed"})]

        if event.kind is EventKind.RUN_PAUSED:
            return [self._emit(Projection.RUN_PAUSED, event, node_key, {"status": "paused"})]

        if event.kind in _RUN_FAILURES:
            return [
                self._emit(
                    Projection.RUN_FAILED,
                    event,
                    node_key,
                    {"status": _RUN_FAILURES[event.kind], "detail": _plain(data)},
                )
            ]

        if event.kind is EventKind.NODE_STARTED:
            return [self._emit(Projection.NODE_STARTED, event, node_key, {})]

        if event.kind in (EventKind.NODE_COMPLETED, EventKind.NODE_CACHED):
            return [
                self._emit(
                    Projection.NODE_COMPLETED,
                    event,
                    node_key,
                    {
                        "cached": event.kind is EventKind.NODE_CACHED,
                        "state": _summarize_update(data.get("update")),
                    },
                )
            ]

        if event.kind is EventKind.NODE_RETRYING:
            return [
                self._emit(
                    Projection.NODE_RETRYING,
                    event,
                    node_key,
                    {"attempt": _plain(data.get("value"))},
                )
            ]

        if event.kind is EventKind.INTERRUPT_RAISED:
            markers = data.get("interrupts") or ()
            return [
                self._emit(
                    Projection.INTERRUPT_RAISED,
                    event,
                    node_key,
                    {"interrupts": [_plain(m) for m in markers]},
                )
            ]

        if event.kind is EventKind.MESSAGE:
            text = _message_text(data.get("value"))
            if text:
                return [self._emit(Projection.ASSISTANT_DELTA, event, node_key, {"delta": text})]

        return []

    # -- helpers ---------------------------------------------------------

    def _custom(self, event: Event, data: dict[str, Any], key: str) -> list[Emission]:
        if data.get("channel") != STREAM_CHANNEL:
            return []
        value = data.get("value")
        if not isinstance(value, dict) or "type" not in value:
            return []
        payload = {k: _plain(v) for k, v in value.items() if k != "type"}
        return [
            Emission(
                kind=str(value["type"]),
                payload=payload,
                node=event.node,
                run_id=event.run_id,
                key=key,
            )
        ]

    def _emit(self, kind: Projection, event: Event, key: str, payload: dict[str, Any]) -> Emission:
        return Emission(
            kind=kind.value, payload=payload, node=event.node, run_id=event.run_id, key=key
        )

    @staticmethod
    def _key(event: Event) -> str:
        namespace = "/".join(event.namespace or ())
        return f"{event.run_id}:{event.step}:{namespace}:{event.task_id or event.node or ''}"


_RUN_FAILURES = {
    EventKind.RUN_FAILED: "failed",
    EventKind.RUN_CANCELLED: "cancelled",
    EventKind.RUN_TIMED_OUT: "timed_out",
    EventKind.RUN_BUDGET_EXCEEDED: "budget_exceeded",
}


def _summarize_update(update: Any) -> dict[str, Any]:
    """Send the small, useful scalars; leave bulk to the session endpoint."""
    if not isinstance(update, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in update.items():
        if key in _BULKY_STATE_KEYS:
            out[key] = f"<{len(value)} items>" if isinstance(value, (list, dict)) else "<set>"
        else:
            out[key] = _plain(value)
    return out


def _message_text(value: Any) -> str:
    """Pull the text out of an ``(AIMessageChunk, metadata)`` envelope."""
    message = value[0] if isinstance(value, (tuple, list)) and value else value
    content = getattr(message, "content", None)
    return str(content) if content else ""


def project_all(events: list[Event]) -> list[Emission]:
    """Convenience for tests: project a whole list with one projector."""
    projector = EventProjector()
    out: list[Emission] = []
    for event in events:
        out.extend(projector.project(event))
    return out
