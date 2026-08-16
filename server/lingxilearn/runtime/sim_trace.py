"""Full-fidelity Sim trace projection for LingxiGraph executions.

The workflow canvas intentionally shows only learner-meaningful semantic nodes.
Logs have a different job: every executable primitive and every control-plane
decision must remain inspectable.  This module builds that second, exhaustive
view without changing what the graph executes or what the learner sees on the
canvas.

The projector accepts both native :class:`lingxigraph.Event` values and the
durable Agent Task event vocabulary.  Consequently the exact same projection
can be produced live and replayed later (including background sidecars).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
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
    sim_type: str
    category: str
    idempotent: bool
    label: str


PrimitiveResolver = Callable[[str], PrimitiveLike]


@dataclass(frozen=True, slots=True)
class _FallbackPrimitive:
    sim_type: str = "function"
    category: str = "runtime"
    idempotent: bool = False
    label: str = ""


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
        if key not in {"workflowState", "traceSpans", "runtime"}
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
class SimTraceProjector:
    """Incrementally build the hierarchical trace consumed by Sim Logs."""

    execution_id: str
    task_id: str
    graph_version: str
    resolve_primitive: PrimitiveResolver
    started_at: Any = None
    trace_spans: list[dict[str, Any]] = field(default_factory=list)
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

    def __post_init__(self) -> None:
        started = _iso(self.started_at)
        self._last_timestamp = started
        self._root = {
            "id": f"{self.execution_id}:workflow",
            "name": "LingxiGraph Runtime",
            "type": "workflow",
            "primitive": "lingxigraph.runtime",
            "category": "runtime",
            "status": "running",
            "duration": 0,
            "durationMs": 0,
            "startTime": started,
            "endTime": started,
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
        self.trace_spans = [self._root]

    # -- primitive/span helpers -----------------------------------------

    def _primitive(
        self,
        name: str,
        *,
        fallback_type: str = "function",
        fallback_category: str = "runtime",
    ) -> PrimitiveLike:
        try:
            return self.resolve_primitive(name)
        except Exception:  # noqa: BLE001 - unknown telemetry must remain visible
            return _FallbackPrimitive(
                sim_type=fallback_type,
                category=fallback_category,
                label=str(name or "Unknown primitive"),
            )

    def _next_id(self, prefix: str) -> str:
        safe = _identifier(prefix)
        self._counts[safe] = self._counts.get(safe, 0) + 1
        return f"{self.execution_id}:{safe}:{self._counts[safe]}"

    def _touch(self, value: Any = None) -> str:
        timestamp = _iso(value)
        self._last_timestamp = timestamp
        self._root["endTime"] = timestamp
        self._root["endedAt"] = timestamp
        return timestamp

    def _new_span(
        self,
        primitive_name: str,
        *,
        parent: dict[str, Any] | None = None,
        timestamp: Any = None,
        span_id: str = "",
        block_id: str = "",
        name: str = "",
        input_data: Any = None,
        fallback_type: str = "function",
        fallback_category: str = "runtime",
        **metadata: Any,
    ) -> dict[str, Any]:
        primitive = self._primitive(
            primitive_name,
            fallback_type=fallback_type,
            fallback_category=fallback_category,
        )
        started = self._touch(timestamp)
        span = {
            "id": span_id or self._next_id(primitive_name),
            "name": name or primitive.label or primitive_name,
            "type": primitive.sim_type,
            "primitive": primitive_name,
            "category": primitive.category,
            "status": "running",
            "duration": 0,
            "durationMs": 0,
            "startTime": started,
            "endTime": started,
            "startedAt": started,
            "endedAt": started,
            "children": [],
            "events": [],
        }
        if block_id:
            span["blockId"] = block_id
        if input_data not in (None, {}, []):
            span["input"] = _json_safe(input_data)
        span.update({key: _json_safe(value) for key, value in metadata.items() if value is not None})
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
        span["endTime"] = ended
        span["endedAt"] = ended
        span["duration"] = _millis(str(span.get("startTime") or ended), ended)
        span["durationMs"] = span["duration"]
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
            span
            for span in self._active_sidecars.values()
            if span.get("status") == "running"
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
        block_id: str = "",
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
            if block_id:
                existing["blockId"] = block_id
            return existing
        primitive_name = str(
            (payload or {}).get("provider")
            or (payload or {}).get("capability")
            or safe_agent
        )
        span = self._new_span(
            primitive_name,
            parent=self._parent(runtime),
            timestamp=timestamp,
            block_id=block_id,
            input_data=_transport_free(payload),
            fallback_type="agent",
            fallback_category="agent",
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
    def _model_key(agent: str, payload: Mapping[str, Any]) -> str:
        node_id = str(payload.get("node_id") or payload.get("work_item_id") or "")
        return f"{agent}:{node_id}" if node_id else agent

    # -- native graph events --------------------------------------------

    def consume_native(
        self,
        event: Any,
        *,
        agent: str = "coordinator",
        block_id: str = "",
    ) -> None:
        kind = getattr(event, "kind", None)
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
                    block_id=block_id,
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
            block_id=block_id,
        )

    def _consume_native_kind(
        self,
        kind: str,
        *,
        node: str,
        data: Mapping[str, Any],
        runtime: Mapping[str, Any],
        timestamp: Any,
        block_id: str = "",
    ) -> None:
        timestamp = self._touch(timestamp)
        if kind == "run.started":
            self._saw_run_lifecycle = True
            self._root.update(
                {
                    "status": "running",
                    "startTime": timestamp,
                    "startedAt": timestamp,
                    "endTime": timestamp,
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
            if kind in _TERMINAL_RUN_EVENTS:
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
                    block_id=block_id,
                    input_data=data,
                    fallback_type="router_v2",
                    fallback_category="control",
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
                    block_id=block_id,
                    fallback_type="router_v2",
                    fallback_category="control",
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
                fallback_type="human_in_the_loop" if kind == "interrupt.raised" else "function",
                fallback_category="interrupt" if kind == "interrupt.raised" else "state",
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
        block_id: str = "",
    ) -> None:
        safe_payload = _transport_free(payload)
        safe_runtime = dict(runtime or {})
        timestamp = self._touch(timestamp)
        kind = str(kind or "runtime.event")
        agent = str(agent or safe_payload.get("provider") or "coordinator")

        if kind == "run.resumed":
            self._saw_run_lifecycle = True
            self._root.update({"status": "running", "paused": False})
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
            primitive = self._primitive(capability, fallback_type="agent", fallback_category="agent")
            span = self._new_span(
                "sidecar",
                timestamp=timestamp,
                name=f"Sidecar · {primitive.label or capability}",
                input_data=safe_payload,
                fallback_type="parallel",
                fallback_category="control",
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
                    fallback_type="parallel",
                    fallback_category="control",
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
                block_id=block_id or str(safe_payload.get("blockId") or ""),
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
                block_id=block_id,
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
            model_key = self._model_key(agent, safe_payload)
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
                fallback_type="model",
                fallback_category="model",
                provider=safe_payload.get("provider"),
                model=safe_payload.get("model"),
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

        model_key = self._model_key(agent, safe_payload)
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
                    fallback_type="model",
                    fallback_category="model",
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
            provider = safe_payload.get("provider") or response.get("provider")
            if provider:
                model_span["provider"] = str(provider)
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
                    model_span["duration"] = max(0, int(float(duration)))
                    model_span["durationMs"] = model_span["duration"]
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
                        fallback_type="tool",
                        fallback_category="tool",
                        toolCallId=call_id,
                    )
                    # Sim's icon resolver expects tool spans to use type=tool,
                    # regardless of the canvas block semantics for that tool.
                    existing["type"] = "tool"
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
                    fallback_type="tool",
                    fallback_category="tool",
                    toolCallId=call_id,
                )
                span["type"] = "tool"
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
                    span["duration"] = max(0, int(float(duration)))
                    span["durationMs"] = span["duration"]
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
                message = safe_payload.get("message")
                if message:
                    output["message"] = str(message)
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
            primitive_name, fallback_type, fallback_category = event_primitives[kind]
            if kind.startswith("schedule.") and safe_payload.get("toolName"):
                primitive_name = str(safe_payload["toolName"])
            instant = self._new_span(
                primitive_name,
                parent=target,
                timestamp=timestamp,
                input_data=safe_payload,
                fallback_type=fallback_type,
                fallback_category=fallback_category,
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
                block_id=str(payload.get("blockId") or ""),
            )
            return
        if kind in {
            "step.started",
            "step.completed",
            "state.updated",
            "checkpoint.saved",
            "interrupt.raised",
            "message.emitted",
        } and "data" in payload:
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
            block_id=str(payload.get("blockId") or ""),
        )

    # -- final projection ------------------------------------------------

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
                self._root["paused"] = True
        if not self._saw_run_lifecycle and self._root.get("status") == "running":
            if not self._active_native and not self._active_tasks and not self._active_sidecars:
                # Preserve the legacy standalone projector contract; durable
                # executions always receive a run.completed envelope and use
                # the normalized ``success`` status above.
                self._root["status"] = "completed"
        terminal = self._root.get("status") in {"success", "error"}
        if terminal and ended_at is not None:
            self._root["endTime"] = end
            self._root["endedAt"] = end
        else:
            self._root["endTime"] = max(str(self._root.get("endTime") or end), end)
            self._root["endedAt"] = self._root["endTime"]

        def update(span: dict[str, Any], root_start: str) -> dict[str, int]:
            if span.get("status") == "running":
                span["endTime"] = end
                span["endedAt"] = end
            span["duration"] = _millis(
                str(span.get("startTime") or end), str(span.get("endTime") or end)
            )
            span["durationMs"] = span["duration"]
            try:
                span["relativeStartMs"] = _millis(root_start, str(span.get("startTime") or end))
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

        root_start = str(self._root.get("startTime") or end)
        update(self._root, root_start)
        return _json_safe(self.trace_spans)


def replay_trace(
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

    projector = SimTraceProjector(
        execution_id=execution_id,
        task_id=task_id,
        graph_version=graph_version,
        resolve_primitive=resolve_primitive,
        started_at=started_at,
    )
    for record in records:
        projector.consume_persisted(record)
    return projector.snapshot(status=status, ended_at=ended_at)


def total_tokens(trace_spans: list[Mapping[str, Any]]) -> int:
    """Return the root token total without double-counting child spans."""

    if not trace_spans:
        return 0
    tokens = trace_spans[0].get("tokens") or {}
    if isinstance(tokens, Mapping):
        try:
            return max(0, int(tokens.get("total") or 0))
        except (TypeError, ValueError):
            return 0
    try:
        return max(0, int(tokens))
    except (TypeError, ValueError):
        return 0


__all__ = ["SimTraceProjector", "replay_trace", "total_tokens"]
