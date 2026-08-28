"""LingxiLearn's full-fidelity execution timeline.

The workflow canvas intentionally shows only learner-meaningful semantic nodes.
Logs have a different job: every executable primitive and every control-plane
decision must remain inspectable.  This module builds that second, exhaustive
view without changing what the graph executes or what the learner sees.

The projector accepts both native :class:`lingxigraph.Event` values and the
durable Agent Task event vocabulary.  Consequently the exact same projection
can be produced live and replayed later (including background sidecars).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from lingxigraph import EventKind

MAX_EVENTS_PER_SPAN = 200
_RUN_FAILURES = {
    "run.failed",
    "run.cancelled",
    "run.timed_out",
    "run.budget_exceeded",
    "task.failed",
    "task.cancelled",
}
_TERMINAL_RUN_EVENTS = _RUN_FAILURES | {"run.completed", "run.ended"}
_NODE_EVENTS = {
    "node.started",
    "node.completed",
    "node.failed",
    "node.retrying",
    "node.cached",
}


class PrimitiveLike(Protocol):
    @property
    def display_kind(self) -> str: ...

    @property
    def category(self) -> str: ...

    @property
    def idempotent(self) -> bool: ...

    @property
    def label(self) -> str: ...


PrimitiveResolver = Callable[[str], PrimitiveLike]


@dataclass(frozen=True, slots=True)
class _DefaultPrimitive:
    display_kind: str = "function"
    category: str = "runtime"
    idempotent: bool = False
    label: str = ""


@dataclass(frozen=True, slots=True)
class ExecutionSpan:
    """One hierarchical interval in a LingxiLearn execution timeline."""

    id: str
    name: str
    kind: str
    status: str
    started_at: str
    ended_at: str
    duration_ms: int
    children: tuple[ExecutionSpan, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_native(cls, value: Mapping[str, Any]) -> ExecutionSpan:
        """Build a span from the one accepted native timeline schema."""

        required = {"id", "name", "kind", "status", "startedAt", "endedAt", "durationMs"}
        missing = required.difference(value)
        if missing:
            raise ValueError(f"invalid native execution span; missing {sorted(missing)}")
        known = {
            "id",
            "name",
            "kind",
            "status",
            "startedAt",
            "endedAt",
            "durationMs",
            "children",
        }
        return cls(
            id=str(value.get("id") or ""),
            name=str(value.get("name") or "Execution"),
            kind=str(value["kind"]),
            status=str(value.get("status") or "running"),
            started_at=str(value["startedAt"]),
            ended_at=str(value["endedAt"]),
            duration_ms=max(0, int(value["durationMs"])),
            children=tuple(
                cls.from_native(item)
                for item in value.get("children") or ()
                if isinstance(item, Mapping)
            ),
            attributes={key: _json_safe(item) for key, item in value.items() if key not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "startedAt": self.started_at,
            "endedAt": self.ended_at,
            "durationMs": self.duration_ms,
            "children": [child.to_dict() for child in self.children],
            **_json_safe(self.attributes),
        }


@dataclass(frozen=True, slots=True)
class ExecutionTimeline:
    """Ordered, hierarchical history of one execution."""

    execution_id: str
    spans: tuple[ExecutionSpan, ...]

    @classmethod
    def from_native(
        cls,
        execution_id: str,
        spans: Sequence[Mapping[str, Any]],
    ) -> ExecutionTimeline:
        return cls(
            execution_id=execution_id,
            spans=tuple(ExecutionSpan.from_native(span) for span in spans),
        )

    def to_dict(self) -> dict[str, Any]:
        root = self.spans[0].attributes if self.spans else {}
        return {
            "schemaVersion": "lingxilearn.timeline.v1",
            "executionId": self.execution_id,
            "spans": [span.to_dict() for span in self.spans],
            "totalTokens": timeline_total_tokens([span.to_dict() for span in self.spans]),
            "waitingForUserMs": max(0, int(root.get("waitingForUserMs") or 0)),
        }


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            return _json_safe(value.model_dump(mode="json"))
        except Exception:  # noqa: BLE001 - trace serialization is best effort
            pass
    return str(value)


def _iso(value: Any = None) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC).isoformat()
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat()
    return datetime.now(UTC).isoformat()


def _millis(start: str, end: str) -> int:
    try:
        start_value = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_value = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return 0
    return max(0, int((end_value - start_value).total_seconds() * 1000))


def _identifier(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "").strip())
    return text.strip("-") or "unknown"


def _transport_free(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Remove repeated transport snapshots before placing data in a span."""

    return {
        str(key): _json_safe(value)
        for key, value in dict(payload or {}).items()
        if key not in {"executionSnapshot", "timeline", "runtime"}
    }


def _usage_tokens(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    usage = dict(value)

    def integer(*names: str) -> int:
        for name in names:
            candidate = usage.get(name)
            if candidate is None:
                continue
            try:
                return max(0, int(candidate))
            except (TypeError, ValueError):
                continue
        return 0

    tokens = {
        "input": integer("input", "input_tokens", "prompt_tokens"),
        "output": integer("output", "output_tokens", "completion_tokens"),
        "total": integer("total", "total_tokens"),
        "cacheRead": integer("cache_read", "cache_read_tokens", "cached_tokens"),
        "cacheWrite": integer("cache_write", "cache_write_tokens"),
        "reasoning": integer("reasoning", "reasoning_tokens"),
    }
    if not tokens["total"]:
        tokens["total"] = tokens["input"] + tokens["output"]
    return {key: count for key, count in tokens.items() if count}


def _tool_arguments(value: Any) -> Any:
    if not isinstance(value, str):
        return _json_safe(value)
    stripped = value.strip()
    if not stripped:
        return {}
    try:
        return _json_safe(json.loads(stripped))
    except (TypeError, ValueError):
        return stripped


@dataclass
class ExecutionTimelineProjector:
    """Incrementally build the hierarchical timeline consumed by Logs."""

    execution_id: str
    task_id: str
    graph_version: str
    resolve_primitive: PrimitiveResolver
    started_at: Any = None
    spans: list[dict[str, Any]] = field(default_factory=list)
    _root: dict[str, Any] = field(default_factory=dict, init=False)
    _active_native: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)
    _active_native_order: list[str] = field(default_factory=list, init=False)
    _active_tasks: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)
    _active_agents: dict[str, list[dict[str, Any]]] = field(default_factory=dict, init=False)
    _active_models: dict[str, list[dict[str, Any]]] = field(default_factory=dict, init=False)
    _active_tools: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)
    _active_sidecars: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)
    _counts: dict[str, int] = field(default_factory=dict, init=False)
    _last_timestamp: str = field(default="", init=False)
    _saw_run_lifecycle: bool = field(default=False, init=False)
    _paused_since: str = field(default="", init=False)
    """Set while the run is paused (``run.paused`` seen, no ``run.resumed`` yet).

    Human wait time accrues from here, not from active-execution spans, so a
    learner sitting on WAITING_FOR_USER for hours never shows up as hours of
    Agent/Skill execution (issue #32 §3).
    """
    _waiting_for_user_ms: int = field(default=0, init=False)
    """Accumulated waiting time from *completed* pause intervals only."""
    _pause_intervals: list[tuple[str, str]] = field(default_factory=list, init=False)
    """Completed ``(pause_ts, resume_ts)`` wall-clock windows.

    Any span whose own ``[startedAt, endedAt]`` overlaps one of these windows
    must have that overlap excluded from its ``durationMs`` — not just the
    root's — otherwise a native span (e.g. ``await_user``) that is still open
    when ``run.paused`` fires and only closes after ``run.resumed`` would show
    the full paused wall-clock gap as active duration.
    """

    def __post_init__(self) -> None:
        started = _iso(self.started_at)
        self._last_timestamp = started
        self._root = {
            "id": f"{self.execution_id}:execution",
            "name": "LingxiGraph Runtime",
            "kind": "execution",
            "primitive": "lingxigraph.runtime",
            "category": "runtime",
            "status": "running",
            "durationMs": 0,
            "startedAt": started,
            "endedAt": started,
            "input": {
                "taskId": self.task_id,
                "executionId": self.execution_id,
                "graphVersion": self.graph_version,
            },
            "children": [],
            "events": [],
        }
        self.spans = [self._root]

    # -- primitive/span helpers -----------------------------------------

    def _primitive(
        self,
        name: str,
        *,
        default_type: str = "function",
        default_category: str = "runtime",
    ) -> PrimitiveLike:
        try:
            return self.resolve_primitive(name)
        except Exception:  # noqa: BLE001 - unknown telemetry must remain visible
            return _DefaultPrimitive(
                display_kind=default_type,
                category=default_category,
                label=str(name or "Unknown primitive"),
            )

    def _next_id(self, prefix: str) -> str:
        safe = _identifier(prefix)
        self._counts[safe] = self._counts.get(safe, 0) + 1
        return f"{self.execution_id}:{safe}:{self._counts[safe]}"

    def _touch(self, value: Any = None) -> str:
        timestamp = _iso(value)
        self._last_timestamp = timestamp
        self._root["endedAt"] = timestamp
        return timestamp

    def _new_span(
        self,
        primitive_name: str,
        *,
        parent: dict[str, Any] | None = None,
        timestamp: Any = None,
        span_id: str = "",
        node_id: str = "",
        name: str = "",
        input_data: Any = None,
        default_type: str = "function",
        default_category: str = "runtime",
        **metadata: Any,
    ) -> dict[str, Any]:
        primitive = self._primitive(
            primitive_name,
            default_type=default_type,
            default_category=default_category,
        )
        started = self._touch(timestamp)
        span = {
            "id": span_id or self._next_id(primitive_name),
            "name": name or primitive.label or primitive_name,
            "kind": primitive.display_kind,
            "primitive": primitive_name,
            "category": primitive.category,
            "status": "running",
            "durationMs": 0,
            "startedAt": started,
            "endedAt": started,
            "children": [],
            "events": [],
        }
        if node_id:
            span["nodeId"] = node_id
        if input_data not in (None, {}, []):
            span["input"] = _json_safe(input_data)
        span.update(
            {key: _json_safe(value) for key, value in metadata.items() if value is not None}
        )
        (parent or self._root).setdefault("children", []).append(span)
        return span

    def _finish(
        self,
        span: dict[str, Any] | None,
        *,
        timestamp: Any = None,
        status: str = "success",
        output: Any = None,
        error_type: str = "",
        error_message: str = "",
        error_handled: bool | None = None,
    ) -> None:
        if span is None:
            return
        ended = self._touch(timestamp)
        span["status"] = status
        span["endedAt"] = ended
        span["durationMs"] = _millis(str(span.get("startedAt") or ended), ended)
        if output not in (None, {}, []):
            span["output"] = _json_safe(output)
        if error_type:
            span["errorType"] = error_type
        if error_message:
            span["errorMessage"] = error_message
            span.setdefault("output", {"error": error_message})
        if error_handled is not None:
            span["errorHandled"] = error_handled
        for child in span.get("children") or []:
            if child.get("status") == "running":
                self._finish(
                    child,
                    timestamp=ended,
                    status="error" if status == "error" else "success",
                    error_handled=status == "error",
                )

    def _event(
        self,
        span: dict[str, Any] | None,
        kind: str,
        *,
        agent: str,
        timestamp: Any,
        payload: Mapping[str, Any] | None,
        runtime: Mapping[str, Any] | None,
    ) -> None:
        # Streaming deltas and usage are represented by aggregate span fields.
        if kind.endswith(".delta") or kind == "model.usage":
            return
        target = span or self._root
        events = target.setdefault("events", [])
        if len(events) >= MAX_EVENTS_PER_SPAN:
            target["eventsTruncated"] = int(target.get("eventsTruncated") or 0) + 1
            return
        events.append(
            {
                "kind": kind,
                "agent": agent,
                "timestamp": _iso(timestamp),
                "payload": _transport_free(payload),
                "runtime": _json_safe(dict(runtime or {})),
            }
        )

    def _native_key(self, node: str, runtime: Mapping[str, Any]) -> str:
        span_id = str(runtime.get("span_id") or "")
        if span_id:
            return span_id
        return ":".join(
            (
                node,
                str(runtime.get("step") or 0),
                str(runtime.get("task_id") or ""),
                "/".join(str(item) for item in runtime.get("namespace") or ()),
            )
        )

    def _current_native(self, runtime: Mapping[str, Any] | None = None) -> dict[str, Any]:
        runtime = dict(runtime or {})
        node = str(runtime.get("node") or "")
        if node:
            for key in reversed(self._active_native_order):
                candidate = self._active_native.get(key)
                if candidate and candidate.get("primitive") == node:
                    return candidate
        for key in reversed(self._active_native_order):
            candidate = self._active_native.get(key)
            if candidate and candidate.get("status") == "running":
                return candidate
        return self._root

    def _current_sidecar(self, runtime: Mapping[str, Any] | None) -> dict[str, Any] | None:
        runtime = dict(runtime or {})
        sidecar_id = str(runtime.get("sidecar_id") or "")
        if sidecar_id and sidecar_id in self._active_sidecars:
            return self._active_sidecars[sidecar_id]
        active = [
            span for span in self._active_sidecars.values() if span.get("status") == "running"
        ]
        return active[-1] if len(active) == 1 else None

    def _parent(self, runtime: Mapping[str, Any] | None) -> dict[str, Any]:
        return self._current_sidecar(runtime) or self._current_native(runtime)

    def _find_agent(self, agent: str) -> dict[str, Any] | None:
        candidates = self._active_agents.get(agent, [])
        return next(
            (span for span in reversed(candidates) if span.get("status") == "running"),
            None,
        )

    def _ensure_agent(
        self,
        agent: str,
        *,
        payload: Mapping[str, Any] | None,
        runtime: Mapping[str, Any] | None,
        timestamp: Any,
        node_id: str = "",
    ) -> dict[str, Any]:
        safe_agent = str(agent or "coordinator")
        logical_task_key = str((payload or {}).get("task_id") or "")
        task_key = str(
            (payload or {}).get("node_id")
            or (payload or {}).get("work_item_id")
            or logical_task_key
            or ""
        )
        if task_key:
            existing = self._active_tasks.get(task_key)
            if existing is not None and existing.get("status") == "running":
                self._active_agents.setdefault(safe_agent, []).append(existing)
                return existing
        existing = self._find_agent(safe_agent)
        if existing is not None:
            if node_id:
                existing["nodeId"] = node_id
            return existing
        primitive_name = str(
            (payload or {}).get("provider") or (payload or {}).get("capability") or safe_agent
        )
        span = self._new_span(
            primitive_name,
            parent=self._parent(runtime),
            timestamp=timestamp,
            node_id=node_id,
            input_data=_transport_free(payload),
            default_type="agent",
            default_category="agent",
            agent=safe_agent,
            capability=(payload or {}).get("capability"),
            skillId=(payload or {}).get("skill_id"),
            taskId=task_key or None,
            logicalTaskId=logical_task_key or None,
            nodeId=task_key or None,
            runtime=_json_safe(dict(runtime or {})),
        )
        self._active_agents.setdefault(safe_agent, []).append(span)
        if task_key:
            self._active_tasks[task_key] = span
        return span

    def _finish_agent(
        self,
        agent: str,
        *,
        payload: Mapping[str, Any] | None,
        timestamp: Any,
        failed: bool = False,
    ) -> dict[str, Any] | None:
        task_key = str(
            (payload or {}).get("node_id")
            or (payload or {}).get("work_item_id")
            or (payload or {}).get("task_id")
            or ""
        )
        span = self._active_tasks.get(task_key) if task_key else None
        span = span or self._find_agent(agent)
        if span is None:
            span = self._ensure_agent(
                agent,
                payload=payload,
                runtime={},
                timestamp=timestamp,
            )
        status_value = str((payload or {}).get("status") or "")
        is_error = failed or status_value in {
            "failed",
            "blocked",
            "cancelled",
            "timed_out",
            "budget_exceeded",
        }
        detail = str(
            (payload or {}).get("detail")
            or (payload or {}).get("message")
            or (payload or {}).get("error")
            or ""
        )
        self._finish(
            span,
            timestamp=timestamp,
            status="error" if is_error else "success",
            output=_transport_free(payload),
            error_type=str((payload or {}).get("error_type") or ""),
            error_message=detail if is_error else "",
        )
        if task_key:
            self._active_tasks.pop(task_key, None)
        return span

    @staticmethod
    def _model_key(
        agent: str,
        payload: Mapping[str, Any],
        runtime: Mapping[str, Any] | None = None,
    ) -> str:
        """Keep concurrent same-model calls in separate active buckets."""

        runtime = runtime or {}
        node_id = str(
            payload.get("node_id")
            or payload.get("nodeId")
            or runtime.get("node_id")
            or runtime.get("nodeId")
            or runtime.get("node")
            or ""
        )
        work_item = str(
            payload.get("work_item_id")
            or payload.get("workItemId")
            or runtime.get("work_item_id")
            or runtime.get("workItemId")
            or payload.get("task_id")
            or payload.get("taskId")
            or runtime.get("task_id")
            or runtime.get("taskId")
            or ""
        )
        if node_id or work_item:
            return f"{agent}:node:{node_id}:work:{work_item}"
        # A graph runtime span can surround an entire dispatch fan-out, so it
        # is not a work identity when the event already carries node/work
        # metadata. Use it only as the last stable identity.
        span_id = str(
            payload.get("span_id")
            or payload.get("spanId")
            or runtime.get("span_id")
            or runtime.get("spanId")
            or ""
        )
        if span_id:
            return f"{agent}:span:{span_id}"
        return agent

    # -- native graph events --------------------------------------------

    def consume_native(
        self,
        event: Any,
        *,
        agent: str = "coordinator",
        node_id: str = "",
    ) -> None:
        kind = getattr(event, "kind", None)
        if not isinstance(kind, EventKind):
            return
        runtime = {
            "execution_id": self.execution_id,
            "run_id": getattr(event, "run_id", None),
            "step": int(getattr(event, "step", 0) or 0),
            "node": getattr(event, "node", None),
            "task_id": getattr(event, "task_id", None) or self.task_id,
            "namespace": _json_safe(getattr(event, "namespace", None)),
            "checkpoint_id": getattr(event, "checkpoint_id", None),
            "span_id": getattr(event, "span_id", None),
        }
        timestamp = getattr(event, "timestamp", None)
        data = _json_safe(getattr(event, "data", None) or {})

        if kind is EventKind.CUSTOM:
            value = data.get("value") if isinstance(data, dict) else None
            if isinstance(value, dict) and value.get("type"):
                custom_agent = str(value.get("agent") or agent)
                self.consume_event(
                    str(value["type"]),
                    {str(key): item for key, item in value.items() if key not in {"type", "agent"}},
                    agent=custom_agent,
                    runtime=runtime,
                    timestamp=timestamp,
                    node_id=node_id,
                )
            return

        native_kind = {
            EventKind.RUN_STARTED: "run.started",
            EventKind.RUN_PAUSED: "run.paused",
            EventKind.RUN_COMPLETED: "run.completed",
            EventKind.RUN_FAILED: "run.failed",
            EventKind.RUN_CANCELLED: "run.cancelled",
            EventKind.RUN_TIMED_OUT: "run.timed_out",
            EventKind.RUN_BUDGET_EXCEEDED: "run.budget_exceeded",
            EventKind.NODE_STARTED: "node.started",
            EventKind.NODE_COMPLETED: "node.completed",
            EventKind.NODE_FAILED: "node.failed",
            EventKind.NODE_RETRYING: "node.retrying",
            EventKind.NODE_CACHED: "node.cached",
            EventKind.STEP_STARTED: "step.started",
            EventKind.STEP_COMPLETED: "step.completed",
            EventKind.STATE_UPDATED: "state.updated",
            EventKind.CHECKPOINT_SAVED: "checkpoint.saved",
            EventKind.INTERRUPT_RAISED: "interrupt.raised",
            EventKind.MESSAGE: "message.emitted",
        }.get(kind)
        if not native_kind:
            return
        self._consume_native_kind(
            native_kind,
            node=str(runtime.get("node") or agent),
            data=data if isinstance(data, dict) else {"value": data},
            runtime=runtime,
            timestamp=timestamp,
            node_id=node_id,
        )

    def _consume_native_kind(
        self,
        kind: str,
        *,
        node: str,
        data: Mapping[str, Any],
        runtime: Mapping[str, Any],
        timestamp: Any,
        node_id: str = "",
    ) -> None:
        span: dict[str, Any] | None
        timestamp = self._touch(timestamp)
        if kind == "run.started":
            self._saw_run_lifecycle = True
            self._root.update(
                {
                    "status": "running",
                    "startedAt": timestamp,
                    "endedAt": timestamp,
                }
            )
            self._event(
                self._root,
                kind,
                agent="coordinator",
                timestamp=timestamp,
                payload=data,
                runtime=runtime,
            )
            return
        if kind in _TERMINAL_RUN_EVENTS or kind == "run.paused":
            failed = kind in _RUN_FAILURES
            status = "error" if failed else ("running" if kind == "run.paused" else "success")
            self._root["status"] = status
            self._root["paused"] = kind == "run.paused"
            if kind == "run.paused" and not self._paused_since:
                self._paused_since = timestamp
            if kind in _TERMINAL_RUN_EVENTS:
                if self._paused_since:
                    self._waiting_for_user_ms += _millis(self._paused_since, timestamp)
                    self._pause_intervals.append((self._paused_since, timestamp))
                    self._paused_since = ""
                for span in list(self._active_native.values()):
                    if span.get("status") == "running":
                        self._finish(
                            span,
                            timestamp=timestamp,
                            status="error" if failed else "success",
                            error_handled=False if failed else None,
                        )
            self._event(
                self._root,
                kind,
                agent="coordinator",
                timestamp=timestamp,
                payload=data,
                runtime=runtime,
            )
            return
        if kind in _NODE_EVENTS:
            key = self._native_key(node, runtime)
            span = self._active_native.get(key)
            if kind == "node.started":
                if span is not None and span.get("status") == "running":
                    self._event(
                        span,
                        kind,
                        agent=node,
                        timestamp=timestamp,
                        payload=data,
                        runtime=runtime,
                    )
                    return
                attempt = 1 + sum(
                    1
                    for item in self._root.get("children") or []
                    if item.get("primitive") == node
                    and (item.get("runtime") or {}).get("step") == runtime.get("step")
                )
                span = self._new_span(
                    node,
                    timestamp=timestamp,
                    span_id=str(runtime.get("span_id") or ""),
                    node_id=node_id,
                    input_data=data,
                    default_type="router_v2",
                    default_category="control",
                    node=node,
                    attempt=attempt,
                    runtime=_json_safe(runtime),
                )
                self._active_native[key] = span
                self._active_native_order.append(key)
            elif span is None:
                span = self._new_span(
                    node,
                    timestamp=timestamp,
                    node_id=node_id,
                    default_type="router_v2",
                    default_category="control",
                    node=node,
                    runtime=_json_safe(runtime),
                )
                self._active_native[key] = span
                self._active_native_order.append(key)
            if kind == "node.completed":
                output = data.get("update") or data
                self._finish(span, timestamp=timestamp, status="success", output=output)
                self._active_native.pop(key, None)
            elif kind == "node.cached":
                span["cached"] = True
                self._finish(span, timestamp=timestamp, status="success", output=data)
                self._active_native.pop(key, None)
            elif kind == "node.retrying":
                span["tries"] = max(int(span.get("tries") or 1), int(span.get("attempt") or 1))
                self._finish(
                    span,
                    timestamp=timestamp,
                    status="error",
                    output=data,
                    error_message="Primitive scheduled for retry",
                    error_handled=True,
                )
                self._active_native.pop(key, None)
            elif kind == "node.failed":
                message = str(data.get("message") or data.get("error") or "Node failed")
                self._finish(
                    span,
                    timestamp=timestamp,
                    status="error",
                    output=data,
                    error_type=str(data.get("error_type") or ""),
                    error_message=message,
                )
                self._active_native.pop(key, None)
            self._event(
                span,
                kind,
                agent=node,
                timestamp=timestamp,
                payload=data,
                runtime=runtime,
            )
            return

        # Step/checkpoint/state/interrupt events are observable annotations on
        # the currently executing primitive. Interrupts also get their own
        # instantaneous control span so they are searchable in the trace tree.
        parent = self._current_native(runtime)
        if kind in {"interrupt.raised", "checkpoint.saved"}:
            primitive_name = "await_user" if kind == "interrupt.raised" else "checkpoint"
            instant = self._new_span(
                primitive_name,
                parent=parent,
                timestamp=timestamp,
                input_data=data,
                default_type="human_in_the_loop" if kind == "interrupt.raised" else "function",
                default_category="interrupt" if kind == "interrupt.raised" else "state",
            )
            self._finish(instant, timestamp=timestamp, status="success", output=data)
            parent = instant
        self._event(
            parent,
            kind,
            agent=node,
            timestamp=timestamp,
            payload=data,
            runtime=runtime,
        )

    # -- durable/domain events ------------------------------------------

    def consume_event(
        self,
        kind: str,
        payload: Mapping[str, Any] | None,
        *,
        agent: str = "coordinator",
        runtime: Mapping[str, Any] | None = None,
        timestamp: Any = None,
        node_id: str = "",
    ) -> None:
        span: dict[str, Any] | None
        safe_payload = _transport_free(payload)
        safe_runtime = dict(runtime or {})
        timestamp = self._touch(timestamp)
        kind = str(kind or "runtime.event")
        agent = str(agent or safe_payload.get("provider") or "coordinator")

        if kind == "run.resumed":
            self._saw_run_lifecycle = True
            self._root.update({"status": "running", "paused": False})
            if self._paused_since:
                self._waiting_for_user_ms += _millis(self._paused_since, timestamp)
                self._pause_intervals.append((self._paused_since, timestamp))
                self._paused_since = ""
            self._event(
                self._root,
                kind,
                agent=agent,
                timestamp=timestamp,
                payload=safe_payload,
                runtime=safe_runtime,
            )
            return

        if kind.startswith("run.") or kind.startswith("task."):
            normalized = "run.started" if kind == "task.started" else kind
            normalized = "run.completed" if kind in {"run.ended", "task.completed"} else normalized
            normalized = "run.failed" if kind == "task.failed" else normalized
            normalized = "run.cancelled" if kind == "task.cancelled" else normalized
            self._consume_native_kind(
                normalized,
                node="coordinator",
                data=safe_payload,
                runtime=safe_runtime,
                timestamp=timestamp,
            )
            return

        if kind == "sidecar.started":
            sidecar_id = str(safe_payload.get("sidecar_id") or self._next_id("sidecar"))
            capability = str(safe_payload.get("capability") or agent)
            primitive = self._primitive(capability, default_type="agent", default_category="agent")
            span = self._new_span(
                "sidecar",
                timestamp=timestamp,
                name=f"Sidecar · {primitive.label or capability}",
                input_data=safe_payload,
                default_type="parallel",
                default_category="control",
                sidecarId=sidecar_id,
                capability=capability,
            )
            self._active_sidecars[sidecar_id] = span
            self._event(
                span,
                kind,
                agent=agent,
                timestamp=timestamp,
                payload=safe_payload,
                runtime=safe_runtime,
            )
            return
        if kind in {"sidecar.completed", "sidecar.failed"}:
            sidecar_id = str(safe_payload.get("sidecar_id") or "")
            span = self._active_sidecars.get(sidecar_id)
            if span is None:
                span = self._new_span(
                    "sidecar",
                    timestamp=timestamp,
                    input_data=safe_payload,
                    default_type="parallel",
                    default_category="control",
                    sidecarId=sidecar_id or None,
                )
            failed = kind == "sidecar.failed"
            message = str(safe_payload.get("error") or "")
            self._finish(
                span,
                timestamp=timestamp,
                status="error" if failed else "success",
                output=safe_payload,
                error_message=message if failed else "",
            )
            self._event(
                span,
                kind,
                agent=agent,
                timestamp=timestamp,
                payload=safe_payload,
                runtime=safe_runtime,
            )
            self._active_sidecars.pop(sidecar_id, None)
            return

        if kind in {"node.started", "node.revising"}:
            provider = str(safe_payload.get("provider") or agent or safe_payload.get("capability"))
            span = self._ensure_agent(
                provider,
                payload=safe_payload,
                runtime=safe_runtime,
                timestamp=timestamp,
                node_id=node_id or str(safe_payload.get("nodeId") or ""),
            )
            if kind == "node.revising":
                span["revising"] = True
            self._event(
                span,
                kind,
                agent=provider,
                timestamp=timestamp,
                payload=safe_payload,
                runtime=safe_runtime,
            )
            return
        if kind in {"node.completed", "node.held", "node.failed", "node.retrying"}:
            provider = str(safe_payload.get("provider") or agent or safe_payload.get("capability"))
            failed = kind in {"node.failed", "node.retrying"}
            span = self._finish_agent(
                provider,
                payload=safe_payload,
                timestamp=timestamp,
                failed=failed,
            )
            if span is not None:
                if kind == "node.held":
                    span["held"] = True
                if kind == "node.retrying":
                    span["errorHandled"] = True
                    span["tries"] = int(span.get("tries") or 1)
                self._event(
                    span,
                    kind,
                    agent=provider,
                    timestamp=timestamp,
                    payload=safe_payload,
                    runtime=safe_runtime,
                )
            return

        if kind == "agent.started":
            span = self._ensure_agent(
                agent,
                payload=safe_payload,
                runtime=safe_runtime,
                timestamp=timestamp,
                node_id=node_id,
            )
            self._event(
                span,
                kind,
                agent=agent,
                timestamp=timestamp,
                payload=safe_payload,
                runtime=safe_runtime,
            )
            return
        if kind in {"agent.completed", "agent.failed"}:
            span = self._finish_agent(
                agent,
                payload=safe_payload,
                timestamp=timestamp,
                failed=kind == "agent.failed",
            )
            self._event(
                span,
                kind,
                agent=agent,
                timestamp=timestamp,
                payload=safe_payload,
                runtime=safe_runtime,
            )
            return

        if kind == "model.started":
            model_key = self._model_key(agent, safe_payload, safe_runtime)
            parent = self._ensure_agent(
                agent,
                payload=safe_payload,
                runtime=safe_runtime,
                timestamp=timestamp,
            )
            span = self._new_span(
                "model",
                parent=parent,
                timestamp=timestamp,
                name=str(safe_payload.get("model") or "Model invocation"),
                default_type="model",
                default_category="model",
                provider=safe_payload.get("provider"),
                model=safe_payload.get("model"),
                agent=agent,
                node=(safe_payload.get("node") or safe_runtime.get("node")),
                workItemId=(
                    safe_payload.get("work_item_id")
                    or safe_payload.get("workItemId")
                    or safe_runtime.get("work_item_id")
                    or safe_runtime.get("workItemId")
                ),
                runtime=_json_safe(safe_runtime),
            )
            self._active_models.setdefault(model_key, []).append(span)
            self._event(
                span,
                kind,
                agent=agent,
                timestamp=timestamp,
                payload=safe_payload,
                runtime=safe_runtime,
            )
            return

        model_key = self._model_key(agent, safe_payload, safe_runtime)
        model_span = next(
            (
                span
                for span in reversed(self._active_models.get(model_key, []))
                if span.get("status") == "running"
            ),
            None,
        )
        if kind == "reasoning.delta":
            if model_span is not None:
                model_span["thinking"] = str(model_span.get("thinking") or "") + str(
                    safe_payload.get("delta") or ""
                )
            return
        if kind in {"assistant.delta", "agent.output.delta"}:
            if model_span is not None:
                output = dict(model_span.get("output") or {})
                output["content"] = str(output.get("content") or "") + str(
                    safe_payload.get("delta") or ""
                )
                model_span["output"] = output
            return
        if kind == "model.usage":
            if model_span is not None:
                tokens = _usage_tokens(safe_payload.get("usage") or safe_payload)
                if tokens:
                    model_span["tokens"] = tokens
            return
        if kind in {"model.completed", "model.failed"}:
            if model_span is None:
                parent = self._ensure_agent(
                    agent,
                    payload=safe_payload,
                    runtime=safe_runtime,
                    timestamp=timestamp,
                )
                model_span = self._new_span(
                    "model",
                    parent=parent,
                    timestamp=timestamp,
                    default_type="model",
                    default_category="model",
                )
            response = dict(safe_payload.get("response_metadata") or {})
            additional = dict(safe_payload.get("additional_kwargs") or {})
            model_span["model"] = str(
                safe_payload.get("model")
                or response.get("model_name")
                or response.get("model")
                or model_span.get("model")
                or ""
            )
            provider_value = safe_payload.get("provider") or response.get("provider")
            if provider_value:
                model_span["provider"] = str(provider_value)
            finish_reason = response.get("finish_reason") or response.get("stop_reason")
            if finish_reason:
                model_span["finishReason"] = str(finish_reason)
            reasoning = additional.get("reasoning_content") or additional.get("reasoning")
            if reasoning and not model_span.get("thinking"):
                model_span["thinking"] = str(reasoning)
            failed = kind == "model.failed"
            message = str(safe_payload.get("error") or safe_payload.get("message") or "")
            self._finish(
                model_span,
                timestamp=timestamp,
                status="error" if failed else "success",
                output=model_span.get("output") or response,
                error_type=str(safe_payload.get("error_type") or ""),
                error_message=message if failed else "",
            )
            duration = safe_payload.get("duration_ms")
            if duration is not None:
                try:
                    model_span["durationMs"] = max(0, int(float(duration)))
                except (TypeError, ValueError):
                    pass
            self._event(
                model_span,
                kind,
                agent=agent,
                timestamp=timestamp,
                payload=safe_payload,
                runtime=safe_runtime,
            )
            return

        if kind == "tool.call.delta":
            calls = safe_payload.get("calls") or safe_payload.get("chunks") or []
            if isinstance(calls, Mapping):
                calls = [calls]
            for index, raw_call in enumerate(calls if isinstance(calls, list) else []):
                if not isinstance(raw_call, Mapping):
                    continue
                call = dict(raw_call)
                call_id = str(call.get("id") or f"{agent}:{call.get('index', index)}")
                existing = self._active_tools.get(call_id)
                name = str(call.get("name") or (existing or {}).get("primitive") or "tool")
                if existing is None:
                    parent = self._ensure_agent(
                        agent,
                        payload=safe_payload,
                        runtime=safe_runtime,
                        timestamp=timestamp,
                    )
                    existing = self._new_span(
                        name,
                        parent=parent,
                        timestamp=timestamp,
                        name=name,
                        default_type="tool",
                        default_category="tool",
                        toolCallId=call_id,
                    )
                    existing["kind"] = "tool"
                    self._active_tools[call_id] = existing
                raw_args = call.get("args", call.get("arguments", ""))
                if isinstance(raw_args, str):
                    existing["rawArguments"] = str(existing.get("rawArguments") or "") + raw_args
                    existing["input"] = _tool_arguments(existing["rawArguments"])
                elif raw_args is not None:
                    existing["input"] = _json_safe(raw_args)
                if model_span is not None:
                    requested = model_span.setdefault("modelToolCalls", [])
                    prior = next((item for item in requested if item.get("id") == call_id), None)
                    if prior is None:
                        requested.append(
                            {
                                "id": call_id,
                                "name": name,
                                "arguments": existing.get("input") or {},
                            }
                        )
                    else:
                        prior["name"] = name
                        prior["arguments"] = existing.get("input") or {}
            return

        if kind == "tool.result":
            call_id = str(
                safe_payload.get("tool_call_id")
                or safe_payload.get("id")
                or f"{agent}:{safe_payload.get('name') or 'tool'}"
            )
            span = self._active_tools.get(call_id)
            name = str(safe_payload.get("name") or (span or {}).get("primitive") or "tool")
            if span is None:
                parent = self._ensure_agent(
                    agent,
                    payload=safe_payload,
                    runtime=safe_runtime,
                    timestamp=timestamp,
                )
                duration_value = safe_payload.get("duration_ms")
                try:
                    duration_ms = max(0, int(float(duration_value or 0)))
                except (TypeError, ValueError):
                    duration_ms = 0
                started = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) - timedelta(
                    milliseconds=duration_ms
                )
                span = self._new_span(
                    name,
                    parent=parent,
                    timestamp=started,
                    name=name,
                    default_type="tool",
                    default_category="tool",
                    toolCallId=call_id,
                )
                span["kind"] = "tool"
            arguments = safe_payload.get("arguments")
            if arguments is not None:
                span["input"] = _json_safe(arguments)
            content = safe_payload.get("content", safe_payload.get("result"))
            output = {"content": _json_safe(content)}
            for key in ("additional_kwargs", "response_metadata"):
                if safe_payload.get(key):
                    output[key] = _json_safe(safe_payload[key])
            status_value = str(safe_payload.get("status") or "").lower()
            error = str(safe_payload.get("error") or "")
            failed = bool(error) or status_value in {"error", "failed", "cancelled"}
            self._finish(
                span,
                timestamp=timestamp,
                status="error" if failed else "success",
                output=output,
                error_type=str(safe_payload.get("error_type") or ""),
                error_message=error or (str(content) if failed else ""),
            )
            duration = safe_payload.get("duration_ms")
            if duration is not None:
                try:
                    span["durationMs"] = max(0, int(float(duration)))
                except (TypeError, ValueError):
                    pass
            self._event(
                span,
                kind,
                agent=agent,
                timestamp=timestamp,
                payload=safe_payload,
                runtime=safe_runtime,
            )
            self._active_tools.pop(call_id, None)
            return

        if kind == "agent.output":
            span = self._find_agent(agent) or self._parent(safe_runtime)
            if span is not None:
                output = dict(span.get("output") or {})
                message_value = safe_payload.get("message")
                if message_value:
                    output["message"] = str(message_value)
                span["output"] = output or safe_payload
            self._event(
                span,
                kind,
                agent=agent,
                timestamp=timestamp,
                payload=safe_payload,
                runtime=safe_runtime,
            )
            return

        # Decision, state, artifact, delivery, schedule and guardrail events
        # are instantaneous runtime primitives. They remain visible in the
        # trace and their full payload is also retained as an annotation.
        event_primitives = {
            "decision.recorded": ("Decision Trace", "function", "decision"),
            "plan.created": ("Decision Trace", "function", "decision"),
            "plan.replanned": ("Decision Trace", "function", "decision"),
            "guardrail.triggered": ("Guardrails", "function", "guardrail"),
            "profile.updated": ("ProfileWriter", "function", "state"),
            "artifact.ready": ("Artifact Validator", "file", "artifact"),
            "artifact.recovered": ("Artifact Validator", "file", "artifact"),
            "delivery.queued": ("Delivery Queue", "function", "delivery"),
            "delivery.unlocked": ("Delivery Queue", "function", "delivery"),
            "schedule.proposed": ("schedule.propose", "schedule", "schedule"),
            "schedule.permission": ("schedule.propose", "schedule", "schedule"),
        }
        target = self._parent(safe_runtime)
        if kind in event_primitives:
            primitive_name, default_type, default_category = event_primitives[kind]
            if kind.startswith("schedule.") and safe_payload.get("toolName"):
                primitive_name = str(safe_payload["toolName"])
            instant = self._new_span(
                primitive_name,
                parent=target,
                timestamp=timestamp,
                input_data=safe_payload,
                default_type=default_type,
                default_category=default_category,
            )
            failed = kind == "guardrail.triggered" and bool(safe_payload.get("fatal"))
            self._finish(
                instant,
                timestamp=timestamp,
                status="error" if failed else "success",
                output=safe_payload,
                error_handled=True if failed else None,
            )
            target = instant
        self._event(
            target,
            kind,
            agent=agent,
            timestamp=timestamp,
            payload=safe_payload,
            runtime=safe_runtime,
        )

    def consume_persisted(self, record: Mapping[str, Any]) -> None:
        """Replay one row from ``agent_task_events`` into the trace."""

        kind = str(record.get("kind") or "")
        payload = dict(record.get("payload") or {})
        runtime = dict(record.get("runtime") or payload.get("runtime") or {})
        timestamp = runtime.get("timestamp") or record.get("ts") or record.get("created_at")
        agent = str(record.get("agent") or "coordinator")

        # Native graph projections retain their original event data envelope.
        # Domain events use a direct payload, even when emitted from inside a
        # native node and therefore carrying that node in runtime metadata.
        if kind in _NODE_EVENTS and "data" in payload:
            self._consume_native_kind(
                kind,
                node=str(runtime.get("node") or agent),
                data=dict(payload.get("data") or {}),
                runtime=runtime,
                timestamp=timestamp,
                node_id=str(payload.get("nodeId") or ""),
            )
            return
        if (
            kind
            in {
                "step.started",
                "step.completed",
                "state.updated",
                "checkpoint.saved",
                "interrupt.raised",
                "message.emitted",
            }
            and "data" in payload
        ):
            self._consume_native_kind(
                kind,
                node=str(runtime.get("node") or agent),
                data=dict(payload.get("data") or {}),
                runtime=runtime,
                timestamp=timestamp,
            )
            return
        self.consume_event(
            kind,
            payload,
            agent=agent,
            runtime=runtime,
            timestamp=timestamp,
            node_id=str(payload.get("nodeId") or ""),
        )

    # -- final projection ------------------------------------------------

    def _paused_overlap_ms(self, start: str, end: str) -> int:
        """Wall-clock time within ``[start, end]`` that fell inside a pause.

        Covers every completed ``run.paused``/``run.resumed`` window plus, if
        the run is *currently* paused, the still-open window up to ``end`` —
        so a span whose ``node.completed`` lands after resume still excludes
        the pause it straddled.
        """

        intervals = list(self._pause_intervals)
        if self._paused_since:
            intervals.append((self._paused_since, end))
        total = 0
        for pause_start, pause_end in intervals:
            overlap_start = max(start, pause_start)
            overlap_end = min(end, pause_end)
            if overlap_start < overlap_end:
                total += _millis(overlap_start, overlap_end)
        return total

    def snapshot(
        self,
        *,
        status: str | None = None,
        ended_at: Any = None,
    ) -> list[dict[str, Any]]:
        end = _iso(ended_at) if ended_at is not None else _iso()
        if status:
            normalized = str(status)
            if normalized in {"failed", "timed_out", "budget_exceeded", "cancelled"}:
                self._root["status"] = "error"
            elif normalized in {"completed", "handed_off", "succeeded"}:
                self._root["status"] = "success"
            elif normalized in {"awaiting_user", "paused"}:
                self._root["status"] = "running"
                if not self._root.get("paused"):
                    # Entering pause via a status-only call (e.g. a replay with
                    # no explicit run.paused event): freeze from the last known
                    # activity instead of from "now", or the freeze point
                    # itself would already include this call's own delay.
                    self._paused_since = self._paused_since or str(self._root.get("endedAt") or end)
                self._root["paused"] = True
        if not self._saw_run_lifecycle and self._root.get("status") == "running":
            if not self._active_native and not self._active_tasks and not self._active_sidecars:
                # A standalone projection without a run lifecycle is complete
                # once it has no active native work.
                self._root["status"] = "completed"

        terminal = self._root.get("status") in {"success", "error"}
        # While paused, repeated snapshot() calls (e.g. live polling) must not
        # keep inflating active execution time with the human's wait — freeze
        # running spans at the pause point and count the elapsed wait
        # separately instead of folding it into their duration.
        paused = bool(self._root.get("paused")) and not terminal
        freeze_at = self._paused_since or end
        waiting_ms = self._waiting_for_user_ms
        if paused and self._paused_since:
            waiting_ms += _millis(self._paused_since, end)

        if terminal and ended_at is not None:
            self._root["endedAt"] = end
        else:
            self._root["endedAt"] = max(str(self._root.get("endedAt") or end), end)

        def update(span: dict[str, Any], root_start: str) -> dict[str, int]:
            if span.get("status") == "running" and span is not self._root:
                clamp = freeze_at if paused else end
                span["endedAt"] = clamp
            span_start = str(span.get("startedAt") or end)
            span_end = str(span.get("endedAt") or end)
            overlap = self._paused_overlap_ms(span_start, span_end) if span is not self._root else 0
            span["durationMs"] = max(0, _millis(span_start, span_end) - overlap)
            try:
                span["relativeStartMs"] = _millis(root_start, str(span.get("startedAt") or end))
            except Exception:  # pragma: no cover - _millis already guards malformed values
                span["relativeStartMs"] = 0
            totals = {} if span is self._root else _usage_tokens(span.get("tokens") or {})
            for child in span.get("children") or []:
                child_totals = update(child, root_start)
                for key, value in child_totals.items():
                    totals[key] = totals.get(key, 0) + value
            if span is self._root and totals:
                span["tokens"] = totals
            return totals

        root_start = str(self._root.get("startedAt") or end)
        update(self._root, root_start)

        # wallDurationMs is real wall-clock elapsed time (grows through a
        # pause); activeDurationMs excludes accumulated/ongoing waiting-for-
        # user time; durationMs is active execution time.
        wall_ms = _millis(root_start, str(self._root.get("endedAt") or end))
        active_ms = max(0, wall_ms - waiting_ms)
        self._root["wallDurationMs"] = wall_ms
        self._root["waitingForUserMs"] = waiting_ms
        self._root["activeDurationMs"] = active_ms
        self._root["durationMs"] = active_ms
        return _json_safe(self.spans)


def replay_timeline(
    records: list[Mapping[str, Any]],
    *,
    execution_id: str,
    task_id: str,
    graph_version: str,
    resolve_primitive: PrimitiveResolver,
    started_at: Any = None,
    ended_at: Any = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Rebuild a trace from the durable Agent Task event log."""

    projector = ExecutionTimelineProjector(
        execution_id=execution_id,
        task_id=task_id,
        graph_version=graph_version,
        resolve_primitive=resolve_primitive,
        started_at=started_at,
    )
    for record in records:
        projector.consume_persisted(record)
    return projector.snapshot(status=status, ended_at=ended_at)


def timeline_total_tokens(spans: Sequence[Mapping[str, Any]]) -> int:
    """Return the root token total without double-counting child spans."""

    if not spans:
        return 0
    tokens = spans[0].get("tokens") or {}
    if isinstance(tokens, Mapping):
        try:
            return max(0, int(tokens.get("total") or 0))
        except (TypeError, ValueError):
            return 0
    try:
        return max(0, int(tokens))
    except (TypeError, ValueError):
        return 0


__all__ = [
    "ExecutionSpan",
    "ExecutionTimeline",
    "ExecutionTimelineProjector",
    "replay_timeline",
    "timeline_total_tokens",
]
