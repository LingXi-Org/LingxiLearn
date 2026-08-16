"""Execution-scoped semantic trajectory projection.

The runtime already persists the event stream and the recursive trace spans.
This module deliberately keeps the trajectory as a *projection* of those
records: it does not introduce another event table or another clock.  Every
item is normalised against ``AgentExecution.started_at`` and is assigned to
one of the eight stable audit lanes used by the Logs UI.

The projector accepts both SQLAlchemy rows and plain dictionaries.  Keeping
that boundary small makes it useful from the service and from unit tests,
while the output remains JSON serialisable for the existing Logs endpoints.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

TRAJECTORY_VERSION = "lingxi-trajectory.v1"

TRAJECTORY_LANES: tuple[tuple[str, str], ...] = (
    ("run", "RUN"),
    ("control", "CONTROL ROUND"),
    ("task", "CAPABILITY TASK"),
    ("action", "ACTION"),
    ("runtime", "RUNTIME"),
    ("state", "STATE"),
    ("resource", "RESOURCE"),
    ("output", "OUTPUT"),
)

_LANE_IDS = {lane for lane, _ in TRAJECTORY_LANES}
_ACTION_TYPES = {
    "model",
    "tool",
    "function",
    "file",
    "artifact",
    "schedule",
    "http",
    "code",
    "python",
    "sql",
    "browser",
    "integration",
}
_ACTION_PRIMITIVES = {"model", "tool", "function", "file", "artifact", "schedule"}
_CONTROL_TYPES = {
    "workflow",
    "agent",
    "loop",
    "parallel",
    "iteration",
    "runtime",
    "decision",
    "state",
    "guardrail",
    "delivery",
    "control",
}
_TERMINAL_KINDS = {
    "node.completed",
    "node.failed",
    "node.held",
    "node.cached",
    "task.completed",
    "task.failed",
    "task.cancelled",
}
_ROUND_KINDS = {"round.started", "round.completed"}
_OUTPUT_KINDS = {
    "assistant.delta",
    "agent.output.delta",
    "agent.output",
    "artifact.ready",
    "artifact.recovered",
}
_STATE_KINDS = {"decision.recorded", "profile.updated", "state.updated"}
_RUNTIME_KINDS = {
    "node.appeared",
    "work.claimed",
    "node.started",
    "node.retrying",
    "node.cached",
    "node.completed",
    "node.held",
    "node.failed",
    "checkpoint.saved",
    "interrupt.raised",
    "run.paused",
    "run.resumed",
    "run.failed",
    "run.timed_out",
    "run.budget_exceeded",
    "run.cancelled",
    "run.completed",
    "run.ended",
}


def _value(source: Any, *names: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        for name in names:
            if name in source and source[name] is not None:
                return source[name]
        return default
    for name in names:
        try:
            result = getattr(source, name)
        except AttributeError:
            continue
        if result is not None:
            return result
    return default


def _json(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return _json(value.model_dump(mode="json"))
        except Exception:  # noqa: BLE001 - projection is best effort
            pass
    return str(value)


def _time(value: Any, fallback: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, (int, float)):
        result = datetime.fromtimestamp(value, UTC)
    elif isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            result = datetime.fromisoformat(text)
        except ValueError:
            result = fallback or datetime.now(UTC)
    else:
        result = fallback or datetime.now(UTC)
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _duration(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() * 1000))


def _tokens(value: Any) -> int:
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if not isinstance(value, Mapping):
        return 0
    try:
        total = int(value.get("total") or value.get("total_tokens") or 0)
    except (TypeError, ValueError):
        total = 0
    if total:
        return max(0, total)
    try:
        return max(0, int(value.get("input") or value.get("input_tokens") or 0)) + max(
            0, int(value.get("output") or value.get("output_tokens") or 0)
        )
    except (TypeError, ValueError):
        return 0


def _span_children(span: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    children = span.get("children")
    if isinstance(children, Sequence) and not isinstance(children, (str, bytes)):
        return [item for item in children if isinstance(item, Mapping)]
    calls = span.get("toolCalls")
    if not isinstance(calls, Sequence) or isinstance(calls, (str, bytes)):
        return []
    result: list[Mapping[str, Any]] = []
    for index, call in enumerate(calls):
        if not isinstance(call, Mapping):
            continue
        result.append(
            {
                "id": call.get("id") or f"{span.get('id', 'span')}-tool-{index}",
                "name": call.get("name") or "Tool call",
                "type": "tool",
                "startTime": call.get("startTime"),
                "endTime": call.get("endTime"),
                "durationMs": call.get("duration") or 0,
                "status": "error" if call.get("error") else "success",
                "errorMessage": call.get("error"),
                "input": call.get("arguments"),
                "output": call.get("result"),
            }
        )
    return result


class TrajectoryProjector:
    """Build the versioned eight-lane view for one AgentExecution."""

    def __init__(
        self,
        execution: Any | None = None,
        events: Iterable[Mapping[str, Any]] = (),
        trace_spans: Sequence[Mapping[str, Any]] | None = None,
        *,
        now: datetime | None = None,
    ) -> None:
        self.execution = execution or {}
        self.events = [dict(item) for item in events if isinstance(item, Mapping)]
        self.trace_spans = [dict(item) for item in (trace_spans or ()) if isinstance(item, Mapping)]
        self.now = now.astimezone(UTC) if now else datetime.now(UTC)
        self.execution_id = str(_value(self.execution, "id", "execution_id", "executionId", default=""))
        self.started = _time(
            _value(self.execution, "started_at", "startedAt", default=None), self.now
        )
        ended_value = _value(self.execution, "ended_at", "endedAt", default=None)
        self.ended = _time(ended_value, self.now) if ended_value else self.now
        if self.ended < self.started:
            self.ended = self.started
        self._items: dict[str, list[dict[str, Any]]] = {lane: [] for lane in _LANE_IDS}
        self._relations: list[dict[str, Any]] = []
        self._rounds: dict[str, dict[str, Any]] = {}
        # Legacy plan/decision events are kept separate until projection.  A
        # lifecycle pair is authoritative even when a legacy event for the
        # same step arrived first (or has a different decision id).
        self._legacy_rounds: dict[str, dict[str, Any]] = {}
        self._tasks: dict[str, dict[str, Any]] = {}
        self._events_by_kind: defaultdict[str, list[tuple[datetime, Mapping[str, Any]]]] = defaultdict(list)

    def _event_data(self, event: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any], datetime]:
        kind = str(event.get("kind") or event.get("type") or "runtime.event")
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            payload = {}
        runtime = event.get("runtime")
        if not isinstance(runtime, Mapping):
            runtime = {}
        timestamp = (
            runtime.get("timestamp")
            or payload.get("timestamp")
            or payload.get("createdAt")
            or event.get("ts")
            or event.get("createdAt")
            or event.get("created_at")
        )
        when = _time(timestamp, self.started)
        return kind, dict(payload), dict(runtime), when

    def _item(
        self,
        lane: str,
        *,
        item_id: str,
        kind: str,
        label: str,
        start: datetime,
        end: datetime | None = None,
        status: str | None = None,
        parent_id: str | None = None,
        precision: str = "exact",
        metadata: Mapping[str, Any] | None = None,
        **links: Any,
    ) -> dict[str, Any]:
        if end is None:
            end = start
        if end < start:
            end = start
        item: dict[str, Any] = {
            "id": str(item_id),
            "lane": lane,
            "kind": kind,
            "label": label,
            "startTime": _iso(start),
            "relativeStartMs": max(0, _duration(self.started, start)),
            "durationMs": _duration(start, end),
            "precision": "exact" if precision == "exact" else "inferred",
        }
        if end != start or links.get("includeEnd", False):
            item["endTime"] = _iso(end)
        if status:
            item["status"] = str(status)
        if parent_id:
            item["parentId"] = parent_id
        for key, value in links.items():
            if key == "includeEnd":
                continue
            if value not in (None, "", [], {}):
                item[key] = _json(value)
        if metadata:
            item["metadata"] = _json(dict(metadata))
        self._items[lane].append(item)
        return item

    @staticmethod
    def _payload_node(payload: Mapping[str, Any], runtime: Mapping[str, Any]) -> str:
        return str(
            payload.get("node_id")
            or payload.get("nodeId")
            or payload.get("work_item_id")
            or payload.get("workItemId")
            or runtime.get("node_id")
            or runtime.get("node")
            or payload.get("task_id")
            or payload.get("taskId")
            or ""
        )

    @staticmethod
    def _round_parts(payload: Mapping[str, Any]) -> tuple[Any, str, str]:
        """Return ``(step, decision_id, stable_key)`` for a round payload.

        ``step`` is the lifecycle identity.  Decision ids are assigned by the
        planner and are absent on some ``round.started`` events, so using them
        as the primary key splits one real round into two projected rows.
        """
        raw_step = payload.get("step")
        if raw_step is None:
            raw_step = payload.get("roundStep")
        step: Any = raw_step
        if isinstance(raw_step, str) and raw_step.strip().isdigit():
            step = int(raw_step.strip())
        decision_id = str(payload.get("decision_id") or payload.get("decisionId") or "")
        if step is not None and str(step) != "":
            key = f"step:{step}"
        elif decision_id:
            key = f"decision:{decision_id}"
        else:
            key = "round:unknown"
        return step, decision_id, key

    @staticmethod
    def _round_id(row: Mapping[str, Any]) -> str:
        decision_id = str(row.get("decision_id") or "")
        if decision_id:
            return f"round:{decision_id}"
        step = row.get("step")
        return f"round:step-{step}" if step is not None and str(step) else "round:unknown"

    def _round_item(self, kind: str, payload: Mapping[str, Any], when: datetime) -> None:
        step, decision_id, key = self._round_parts(payload)
        if key not in self._rounds and step is None:
            # Some older completion records omitted ``step`` but followed a
            # single open lifecycle round.  Keep that pair together without
            # making decision ids the identity of normal step-bearing rounds.
            open_rows = [candidate for candidate in self._rounds.values() if not candidate.get("completed")]
            if len(open_rows) == 1:
                key = next(stable for stable, candidate in self._rounds.items() if candidate is open_rows[0])
        row = self._rounds.setdefault(
            key,
            {
                "id": "",
                "start": when,
                "end": when,
                "step": step,
                "decision_id": decision_id,
                "payload": {},
                "precision": "exact",
                "lifecycle": True,
            },
        )
        row["id"] = self._round_id(row)
        if step is not None:
            row["step"] = step
        if decision_id:
            row["decision_id"] = decision_id
            row["id"] = self._round_id(row)
        if kind == "round.started":
            row["start"] = min(row.get("start", when), when)
            row["started"] = True
            row["payload"] = {**row.get("payload", {}), **dict(payload)}
            row["precision"] = "exact"
        else:
            row["end"] = max(row.get("end", when), when)
            row["completed"] = True
            row["payload"] = {**row.get("payload", {}), **dict(payload)}
        if payload.get("turn_id") or payload.get("turnId"):
            row["turn_id"] = payload.get("turn_id") or payload.get("turnId")

    def _legacy_round(self, kind: str, payload: Mapping[str, Any], when: datetime) -> None:
        step, decision_id, key = self._round_parts(payload)
        row = self._legacy_rounds.setdefault(
            key,
            {
                "id": "",
                "start": when,
                "end": when,
                "step": step,
                "decision_id": decision_id,
                "payload": dict(payload),
                "precision": "inferred",
            },
        )
        row["id"] = self._round_id(row)
        if step is not None:
            row["step"] = step
        if decision_id:
            row["decision_id"] = decision_id
            row["id"] = self._round_id(row)
        if kind in {"plan.created", "plan.replanned", "decision.recorded"}:
            row["end"] = when
        if kind in {"plan.created", "plan.replanned"}:
            row["start"] = min(row["start"], when)
        if payload.get("replan_of"):
            self._relations.append(
                {
                    "type": "replan",
                    "from": f"round:{payload['replan_of']}",
                    "to": row["id"],
                }
            )

    def _consume_event(self, event: Mapping[str, Any]) -> None:
        kind, payload, runtime, when = self._event_data(event)
        self._events_by_kind[kind].append((when, payload))
        if kind in _ROUND_KINDS:
            self._round_item(kind, payload, when)
        elif kind in {"decision.recorded", "plan.created", "plan.replanned"}:
            self._legacy_round(kind, payload, when)

        node_id = self._payload_node(payload, runtime)
        if kind == "node.appeared":
            task = self._tasks.setdefault(node_id or f"task:{len(self._tasks) + 1}", {})
            task.update({"appeared": when, "payload": {**task.get("payload", {}), **payload}})
            task["precision"] = (
                "exact"
                if any(kind in self._events_by_kind for kind in _ROUND_KINDS)
                else "inferred"
            )
        elif kind == "work.claimed":
            task = self._tasks.setdefault(node_id or f"task:{len(self._tasks) + 1}", {})
            task.update({"claimed": when, "payload": {**task.get("payload", {}), **payload}})
            task["work_item_id"] = payload.get("work_item_id") or payload.get("workItemId") or node_id
        elif kind == "node.started":
            task = self._tasks.setdefault(node_id or f"task:{len(self._tasks) + 1}", {})
            task.update({"started": when, "payload": {**task.get("payload", {}), **payload}})
        elif kind in _TERMINAL_KINDS:
            task = self._tasks.setdefault(node_id or f"task:{len(self._tasks) + 1}", {})
            task.update({"ended": when, "terminal_kind": kind, "payload": {**task.get("payload", {}), **payload}})

    def _find_parent_round(self, payload: Mapping[str, Any]) -> str | None:
        step, decision_id, key = self._round_parts(payload)
        row = self._rounds.get(key) or self._legacy_rounds.get(key)
        if row is not None:
            return self._round_id(row)
        # A child may carry only a decision id while its round lifecycle was
        # keyed by step.  Resolve that id across the authoritative rows.
        if decision_id:
            for candidate in (*self._rounds.values(), *self._legacy_rounds.values()):
                if str(candidate.get("decision_id") or "") == decision_id:
                    return self._round_id(candidate)
        return None

    def _project_rounds(self) -> None:
        rows = list(self._rounds.values())
        # Legacy rows are a compatibility fallback only.  If a lifecycle row
        # exists for a stable step/decision key, it owns the projected round.
        lifecycle_steps = {str(row.get("step")) for row in self._rounds.values() if row.get("step") is not None}
        lifecycle_decisions = {
            str(row.get("decision_id"))
            for row in self._rounds.values()
            if row.get("decision_id")
        }
        rows.extend(
            row
            for key, row in self._legacy_rounds.items()
            if key not in self._rounds
            and str(row.get("step")) not in lifecycle_steps
            and str(row.get("decision_id") or "") not in lifecycle_decisions
        )
        for row in rows:
            row["id"] = self._round_id(row)
            start = row["start"]
            end = row["end"]
            # Open rounds are bounded by the execution end/now for a useful
            # bar, while exact lifecycle pairs retain exact precision.
            if end <= start and start < self.ended:
                end = self.ended
            item = self._item(
                "control",
                item_id=self._round_id(row),
                kind="round",
                label=f"Control round {row.get('step') or ''}".strip(),
                start=start,
                end=end,
                status=str(
                    (row.get("payload") or {}).get("runtime_status")
                    or (row.get("payload") or {}).get("status")
                    or ("completed" if row.get("completed") else "running")
                ),
                precision=row.get("precision", "inferred"),
                decisionId=row.get("decision_id"),
                roundStep=row.get("step"),
                turnId=row.get("turn_id"),
                metadata=row.get("payload") or {},
            )
            if row.get("payload", {}).get("replan_of"):
                self._relations.append(
                    {"type": "replan", "from": f"round:{row['payload']['replan_of']}", "to": item["id"]}
                )

    def _project_tasks(self) -> None:
        for index, (node_id, row) in enumerate(self._tasks.items(), start=1):
            payload = row.get("payload") or {}
            start = row.get("appeared") or row.get("claimed") or row.get("started") or self.started
            end = row.get("ended") or self.ended
            status = str(payload.get("status") or "")
            if not status:
                status = "failed" if str(row.get("terminal_kind", "")).endswith("failed") else "running"
            item_id = f"task:{node_id or index}"
            parent = self._find_parent_round(payload)
            item = self._item(
                "task",
                item_id=item_id,
                kind="capability.task",
                label=str(payload.get("capability") or payload.get("task_id") or node_id or "Capability task"),
                start=start,
                end=end,
                status=status,
                parent_id=parent,
                precision=row.get("precision", "inferred"),
                decisionId=payload.get("decision_id") or payload.get("decisionId"),
                roundStep=payload.get("step"),
                workItemId=payload.get("work_item_id") or payload.get("workItemId"),
                metadata={
                    "capability": payload.get("capability"),
                    "skill_id": payload.get("skill_id") or payload.get("skillId"),
                    "provider": payload.get("provider"),
                    "depends_on": payload.get("depends_on") or payload.get("dependsOn") or [],
                    "attempt": payload.get("attempt") or payload.get("attempts"),
                    "knowledge_point_id": payload.get("knowledge_point_id") or payload.get("knowledgePointId"),
                },
            )
            row["item_id"] = item["id"]
            deps = payload.get("depends_on") or payload.get("dependsOn") or []
            for dependency in deps:
                self._relations.append({"type": "dependency", "from": f"task:{dependency}", "to": item["id"]})

    def _flatten_spans(self) -> Iterable[tuple[Mapping[str, Any], Mapping[str, Any] | None]]:
        def walk(items: Sequence[Mapping[str, Any]], parent: Mapping[str, Any] | None = None):
            for span in items:
                yield span, parent
                children = _span_children(span)
                if children:
                    yield from walk(children, span)

        yield from walk(self.trace_spans)

    def _span_times(self, span: Mapping[str, Any]) -> tuple[datetime, datetime]:
        start = _time(span.get("startTime") or span.get("startedAt"), self.started)
        end_value = span.get("endTime") or span.get("endedAt")
        if end_value:
            end = _time(end_value, start)
        else:
            try:
                end = start + timedelta(
                    milliseconds=max(0, int(span.get("durationMs") or span.get("duration") or 0))
                )
            except (TypeError, ValueError):
                end = start
        return start, max(start, end)

    def _project_control_spans(self) -> None:
        """Expose native control-plane spans as first-class CONTROL items.

        Native graph nodes such as ``interpret_goal`` use ``type=router_v2``
        and ``category=control``.  They are deliberately not actions, but
        hiding them makes the control lane look empty even though the runtime
        did real work.  Keep each span independent so its timing/status can be
        inspected without pretending it is a capability task.
        """
        control_items = 0
        for span, _parent_span in self._flatten_spans():
            span_type = str(span.get("type") or span.get("category") or "function").lower()
            category = str(span.get("category") or "").lower()
            primitive = str(span.get("primitive") or "").lower()
            if primitive == "lingxigraph.runtime" or primitive == "workflow":
                continue
            if category != "control" and primitive not in {"interpret_goal", "orchestrate", "observe", "dispatch"}:
                continue
            start, end = self._span_times(span)
            item_id = f"control:span:{span.get('id') or control_items + 1}"
            self._item(
                "control",
                item_id=item_id,
                kind=primitive or span_type,
                label=str(span.get("name") or span.get("primitive") or span_type.title()),
                start=start,
                end=end,
                status=str(span.get("status") or "success"),
                precision="exact" if span.get("startTime") else "inferred",
                spanId=span.get("id"),
                roundStep=(span.get("runtime") or {}).get("step") if isinstance(span.get("runtime"), Mapping) else None,
                metadata={
                    "primitive": span.get("primitive"),
                    "category": span.get("category"),
                    "span_type": span.get("type"),
                    "node": span.get("node"),
                    "provider": span.get("provider"),
                },
            )
            control_items += 1

    def _project_actions_and_resources(self) -> None:
        first_output_by_key: dict[str, datetime] = {}
        for kind in ("assistant.delta", "agent.output.delta", "agent.output"):
            for when, payload in self._events_by_kind.get(kind, []):
                key = str(payload.get("stream_id") or payload.get("streamId") or payload.get("model") or "default")
                first_output_by_key.setdefault(key, when)
        action_items = 0
        for span, _parent_span in self._flatten_spans():
            span_type = str(span.get("type") or span.get("category") or "function").lower()
            primitive = str(span.get("primitive") or "").lower()
            if span_type in _CONTROL_TYPES or primitive in {"lingxigraph.runtime", "workflow"}:
                continue
            if span_type not in _ACTION_TYPES and primitive not in _ACTION_PRIMITIVES:
                continue
            start, end = self._span_times(span)
            metadata = {
                "provider": span.get("provider"),
                "model": span.get("model"),
                "tool_call_id": span.get("toolCallId") or span.get("tool_call_id"),
                "tokens": span.get("tokens"),
            }
            runtime = span.get("runtime") if isinstance(span.get("runtime"), Mapping) else {}
            span_metadata = span.get("metadata") if isinstance(span.get("metadata"), Mapping) else {}
            node = self._payload_node({**dict(span_metadata), **dict(span)}, runtime)
            parent = self._tasks.get(node, {}).get("item_id") if node else None
            if parent is None and self._tasks:
                # Older Sim traces did not copy the runtime node id onto every
                # child span.  A time-contained task is a safe best-effort
                # parent for those historical records and is marked inferred
                # by the action below.
                containing = [
                    (task_id, task)
                    for task_id, task in self._tasks.items()
                    if task.get("started")
                    and task["started"] <= start
                    and (task.get("ended") or self.ended) >= end
                ]
                if containing:
                    node, task = min(
                        containing,
                        key=lambda pair: _duration(
                            pair[1].get("started", self.started),
                            pair[1].get("ended") or self.ended,
                        ),
                    )
                    parent = task.get("item_id")
            action_id = f"action:{span.get('id') or action_items + 1}"
            action = self._item(
                "action",
                item_id=action_id,
                kind=span_type,
                label=str(span.get("name") or span.get("primitive") or span_type.title()),
                start=start,
                end=end,
                status=str(span.get("status") or "success"),
                parent_id=parent,
                precision="exact" if span.get("startTime") and node else "inferred",
                spanId=span.get("id"),
                metadata={key: value for key, value in metadata.items() if value not in (None, "")},
            )
            action_items += 1
            if parent:
                self._relations.append({"type": "parent", "from": parent, "to": action["id"]})
            token_count = _tokens(span.get("tokens"))
            if token_count:
                self._item(
                    "resource",
                    item_id=f"resource:tokens:{action_id}",
                    kind="tokens",
                    label=f"{span_type.title()} tokens",
                    start=start,
                    end=end,
                    status=str(span.get("status") or "success"),
                    parent_id=action.get("id"),
                    precision=action.get("precision", "inferred"),
                    spanId=span.get("id"),
                    metadata={"tokens": token_count, "input": span.get("tokens")},
                )
            if span_type == "model":
                key = str(span.get("stream_id") or span.get("streamId") or span.get("model") or "default")
                first = first_output_by_key.get(key)
                if first and start <= first <= end:
                    self._item(
                        "resource",
                        item_id=f"resource:ttft:{action_id}",
                        kind="model.ttft",
                        label="Model TTFT",
                        start=start,
                        end=first,
                        parent_id=action.get("id"),
                        precision=action.get("precision", "inferred"),
                        spanId=span.get("id"),
                        metadata={"model": span.get("model")},
                    )
            if span_type in {"model", "tool"}:
                self._item(
                    "resource",
                    item_id=f"resource:{span_type}:duration:{action_id}",
                    kind=f"{span_type}.duration",
                    label=f"{span_type.title()} duration",
                    start=start,
                    end=end,
                    status=str(span.get("status") or "success"),
                    parent_id=action.get("id"),
                    precision=action.get("precision", "inferred"),
                    spanId=span.get("id"),
                    metadata={
                        "provider": span.get("provider"),
                        "model": span.get("model"),
                        "tool_call_id": span.get("toolCallId") or span.get("tool_call_id"),
                    },
                )

    def _project_runtime_state_output(self) -> None:
        first_output: tuple[datetime, str, Mapping[str, Any]] | None = None
        for kind, records in self._events_by_kind.items():
            if kind in _RUNTIME_KINDS:
                for index, (when, payload) in enumerate(records, start=1):
                    label = kind.replace(".", " ").title()
                    self._item(
                        "runtime",
                        item_id=f"runtime:{kind}:{index}",
                        kind=kind,
                        label=label,
                        start=when,
                        status=str(payload.get("status") or ""),
                        precision="exact",
                        eventSequence=payload.get("sequence"),
                        workItemId=payload.get("work_item_id") or payload.get("workItemId"),
                        spanId=payload.get("span_id") or payload.get("spanId"),
                        metadata=payload,
                    )
            if kind in _STATE_KINDS:
                for index, (when, payload) in enumerate(records, start=1):
                    self._item(
                        "state",
                        item_id=f"state:{kind}:{index}",
                        kind=kind,
                        label=kind.replace(".", " ").title(),
                        start=when,
                        precision="exact",
                        decisionId=payload.get("decision_id") or payload.get("decisionId"),
                        metadata=payload,
                    )
            if kind in _OUTPUT_KINDS:
                grouped: dict[str, list[tuple[datetime, Mapping[str, Any]]]] = defaultdict(list)
                for when, payload in records:
                    key = str(payload.get("stream_id") or payload.get("streamId") or payload.get("model") or payload.get("artifact") or "default")
                    grouped[key].append((when, payload))
                for key, values in grouped.items():
                    start = values[0][0]
                    end = values[-1][0]
                    self._item(
                        "output",
                        item_id=f"output:{kind}:{key}",
                        kind="stream" if kind.endswith("delta") else kind,
                        label="Streaming output" if kind.endswith("delta") else kind.replace(".", " ").title(),
                        start=start,
                        end=end,
                        precision="exact",
                        metadata={"stream_id": key, "events": len(values), **dict(values[-1][1])},
                    )
                    candidate = (start, key, values[0][1])
                    if first_output is None or candidate[0] < first_output[0]:
                        first_output = candidate
        if first_output is not None:
            first_time, stream_key, payload = first_output
            self._item(
                "output",
                item_id=f"output:first:{self.execution_id or 'execution'}",
                kind="first.output",
                label="First backend output",
                start=first_time,
                precision="exact",
                metadata={"stream_id": stream_key, "source": payload.get("source")},
            )

    def _project_task_resources(self) -> None:
        for node_id, row in self._tasks.items():
            appeared = row.get("appeared")
            claimed = row.get("claimed")
            started = row.get("started")
            ended = row.get("ended") or self.ended
            parent = row.get("item_id")
            if appeared and claimed:
                self._item(
                    "resource",
                    item_id=f"resource:queue:{node_id}",
                    kind="queue.wait",
                    label="Queue wait",
                    start=appeared,
                    end=claimed,
                    parent_id=parent,
                    precision="exact",
                    metadata={"work_item_id": row.get("work_item_id") or node_id},
                )
            if claimed and started:
                self._item(
                    "resource",
                    item_id=f"resource:dispatch:{node_id}",
                    kind="dispatch.overhead",
                    label="Dispatch overhead",
                    start=claimed,
                    end=started,
                    parent_id=parent,
                    precision="exact",
                )
            if started:
                self._item(
                    "resource",
                    item_id=f"resource:provider:{node_id}",
                    kind="provider.duration",
                    label="Provider duration",
                    start=started,
                    end=ended,
                    parent_id=parent,
                    precision=row.get("precision", "inferred"),
                    metadata={"provider": (row.get("payload") or {}).get("provider")},
                )
            retries = sum(1 for _, payload in self._events_by_kind.get("node.retrying", []) if self._payload_node(payload, {}) == node_id)
            if retries:
                self._item(
                    "resource",
                    item_id=f"resource:retry:{node_id}",
                    kind="retry.count",
                    label="Retries",
                    start=ended,
                    parent_id=parent,
                    precision="exact",
                    metadata={"count": retries},
                )

    def project(self) -> dict[str, Any]:
        for event in self.events:
            self._consume_event(event)
        self._project_rounds()
        self._project_tasks()
        self._project_control_spans()
        self._project_actions_and_resources()
        self._project_task_resources()
        self._project_runtime_state_output()
        lanes = [
            {"id": lane, "label": label, "items": sorted(self._items[lane], key=lambda item: (item["relativeStartMs"], item["id"]))}
            for lane, label in TRAJECTORY_LANES
        ]
        duration = _duration(self.started, self.ended)
        if not _value(self.execution, "ended_at", "endedAt", default=None):
            duration = _duration(self.started, self.now)
        run = self._item(
            "run",
            item_id=f"run:{self.execution_id or 'execution'}",
            kind="execution",
            label="Agent execution",
            start=self.started,
            end=self.ended,
            status=str(_value(self.execution, "status", default="running")),
            precision="exact" if _value(self.execution, "started_at", "startedAt", default=None) else "inferred",
            metadata={"execution_id": self.execution_id},
        )
        lanes[0]["items"] = [run]
        summary = {
            "rounds": sum(1 for item in self._items["control"] if item.get("kind") == "round"),
            "tasks": len(self._items["task"]),
            "actions": len(self._items["action"]),
            "failures": sum(1 for lane in lanes for item in lane["items"] if str(item.get("status", "")).lower() in {"failed", "error"}),
            "tokens": sum(int((item.get("metadata") or {}).get("tokens") or 0) for item in self._items["resource"]),
            "durationMs": duration,
        }
        return {
            "version": TRAJECTORY_VERSION,
            "executionId": self.execution_id,
            "clock": {
                "startedAt": _iso(self.started),
                "endedAt": _iso(self.ended) if _value(self.execution, "ended_at", "endedAt", default=None) else None,
                "durationMs": duration,
            },
            "lanes": lanes,
            "relations": self._relations,
            "summary": summary,
        }


def build_trajectory_projection(
    execution: Any,
    events: Iterable[Mapping[str, Any]] = (),
    trace_spans: Sequence[Mapping[str, Any]] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Convenience wrapper used by the service and tests."""

    return TrajectoryProjector(execution, events, trace_spans, now=now).project()


project_trajectory = build_trajectory_projection


__all__ = [
    "TRAJECTORY_LANES",
    "TRAJECTORY_VERSION",
    "TrajectoryProjector",
    "build_trajectory_projection",
    "project_trajectory",
]
