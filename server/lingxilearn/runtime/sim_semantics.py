"""The read-only Sim runtime semantic projection.

LingxiGraph remains the executor.  This module deliberately contains no graph
execution code: it turns the *events emitted by an actual graph run* into the
small, stable subset of Sim's ``WorkflowState`` and ``traceSpans`` contracts
used by the chat and Logs surfaces.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from lingxigraph import EventKind, RetryPolicy

PROJECTION_VERSION = "sim-runtime.v1"


class SimRuntimeError(ValueError):
    """Raised when an execution contains a primitive outside the allow-list."""


@dataclass(frozen=True)
class Primitive:
    sim_type: str
    category: str
    idempotent: bool = False


class PrimitiveCatalog:
    """Closed mapping of LingxiLearn primitives to Sim block semantics."""

    def __init__(self, entries: dict[str, Primitive] | None = None) -> None:
        self.entries = dict(entries or PRIMITIVE_CATALOG)

    def resolve(self, name: str) -> Primitive:
        key = str(name or "").strip()
        try:
            return self.entries[key]
        except KeyError as exc:
            raise SimRuntimeError(f"unregistered LingxiLearn primitive: {key!r}") from exc

    def validate(self, names: Iterable[str]) -> None:
        for name in names:
            self.resolve(name)

    def retry_policy(
        self, name: str, *, max_tries: int = 1, wait_seconds: float = 0.0
    ) -> dict[str, Any] | None:
        primitive = self.resolve(name)
        if max_tries <= 1:
            return None
        if not primitive.idempotent:
            raise SimRuntimeError(f"retry is only allowed for idempotent primitive: {name}")
        return {"maxTries": int(max_tries), "wait": float(wait_seconds), "backoff": "fixed"}

    def lingxi_retry_policy(
        self, name: str, *, max_tries: int = 1, wait_seconds: float = 0.0
    ) -> RetryPolicy | None:
        """Translate an approved Sim retry block to LingxiGraph semantics."""
        config = self.retry_policy(name, max_tries=max_tries, wait_seconds=wait_seconds)
        if config is None:
            return None
        return RetryPolicy(
            max_attempts=int(config["maxTries"]),
            initial_interval=float(config["wait"]),
            backoff_factor=1.0,
            max_interval=float(config["wait"]),
            jitter=False,
        )


# Every node and tool currently shipped by LingxiLearn is registered here.  A
# missing entry is an intentional startup/run failure rather than a generic
# visual node that could conceal a new executable primitive.
PRIMITIVE_CATALOG: dict[str, Primitive] = {
    "recognize_intent": Primitive("router_v2", "condition", True),
    "intent": Primitive("router_v2", "condition", True),
    "lecture_hook": Primitive("agent", "agent"),
    "interactive_lecture_deck": Primitive("agent", "agent"),
    "quiz_generator": Primitive("agent", "agent"),
    "await_user": Primitive("human_in_the_loop", "interrupt"),
    "answer_user": Primitive("agent", "agent"),
    "adaptive_pedagogy": Primitive("agent", "agent"),
    "interactive_visual_explainer": Primitive("agent", "agent"),
    "quiz_submit": Primitive("agent", "agent"),
    "handoff": Primitive("agent", "agent"),
    "curriculum_graph_builder": Primitive("agent", "agent"),
    "learner_state_reflector": Primitive("agent", "agent"),
    "knowledge.search": Primitive("knowledge", "knowledge", True),
    "kb.search": Primitive("knowledge", "knowledge", True),
    "web_search": Primitive("search", "search", True),
    "web_fetch": Primitive("search", "search", True),
    "stage_artifact_file": Primitive("file", "artifact"),
    "stage_artifact_chunk": Primitive("file", "artifact"),
    "stage_artifact_files": Primitive("file", "artifact"),
    "read_staged_artifact": Primitive("file", "artifact", True),
    "list_staged_artifacts": Primitive("file", "artifact", True),
    "read_skill": Primitive("agent", "skill", True),
    "read_skill_resource": Primitive("agent", "skill", True),
    "net.ipv4.lpm": Primitive("function", "tool", True),
    "net.ipv4.subnet": Primitive("function", "tool", True),
    "schedule.propose": Primitive("schedule", "schedule"),
    "schedule.revoke": Primitive("schedule", "schedule"),
    "parallel": Primitive("parallel", "control"),
    "loop": Primitive("loop", "control"),
    "router_v2": Primitive("router_v2", "condition"),
    "coordinator": Primitive("router_v2", "condition", True),
    "__start__": Primitive("router_v2", "condition", True),
    "__end__": Primitive("router_v2", "condition", True),
}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="json"))
    return str(value)


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC).isoformat()
    if isinstance(value, str) and value:
        return value
    return datetime.now(UTC).isoformat()


@dataclass
class SimRunProjector:
    """Incrementally project a single StateGraph execution."""

    execution_id: str
    task_id: str
    graph_version: str
    catalog: PrimitiveCatalog = field(default_factory=PrimitiveCatalog)
    workflow_state: dict[str, Any] = field(default_factory=dict)
    trace_spans: list[dict[str, Any]] = field(default_factory=list)
    _last_blocks_by_step: dict[int, list[str]] = field(default_factory=dict, init=False)
    _active_spans: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)
    _node_counts: dict[str, int] = field(default_factory=dict, init=False)
    _block_keys: dict[tuple[str, int, str], str] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.workflow_state = {
            "id": self.execution_id,
            "version": PROJECTION_VERSION,
            "graphVersion": self.graph_version,
            "blocks": {},
            "edges": [],
            "loops": {},
            "parallels": {},
            "variables": {},
            "metadata": {"executionId": self.execution_id, "taskId": self.task_id},
        }

    @property
    def blocks(self) -> dict[str, Any]:
        return self.workflow_state["blocks"]

    def _block_id(self, node: str, step: int, task_id: str | None) -> str:
        count = self._node_counts.get(node, 0) + 1
        self._node_counts[node] = count
        suffix = str(task_id or count).replace("/", "_")
        return f"{node}:{step}:{suffix}"

    def _ensure_block(self, event: Any, agent: str | None = None) -> tuple[str, dict[str, Any]]:
        node = str(getattr(event, "node", "") or agent or "coordinator")
        self.catalog.resolve(node)
        step = int(getattr(event, "step", 0) or 0)
        task_id = getattr(event, "task_id", None)
        key = (node, step, str(task_id or ""))
        existing = self._block_keys.get(key)
        if existing is not None:
            return existing, self.blocks[existing]
        block_id = self._block_id(node, step, task_id)
        self._block_keys[key] = block_id
        primitive = self.catalog.resolve(node)
        block = {
            "id": block_id,
            "type": primitive.sim_type,
            "name": node,
            "position": {"x": (len(self.blocks) % 4) * 300, "y": (len(self.blocks) // 4) * 160},
            "subBlocks": {},
            "outputs": {},
            "enabled": True,
            "data": {
                "primitive": node,
                "category": primitive.category,
                "executionId": self.execution_id,
                "step": step,
                "taskId": task_id,
                "namespace": _json_safe(getattr(event, "namespace", None)),
            },
            "status": "running",
        }
        self.blocks[block_id] = block
        return block_id, block

    def _connect(self, source: str, target: str, *, kind: str = "transition") -> None:
        if not source or not target or source == target:
            return
        edge_id = f"{source}->{target}"
        if any(edge["id"] == edge_id for edge in self.workflow_state["edges"]):
            return
        self.workflow_state["edges"].append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "type": "workflow",
                "data": {"kind": kind},
            }
        )

    def consume(self, event: Any, *, agent: str = "coordinator") -> dict[str, Any]:
        """Consume one native event and return the legacy-compatible envelope."""

        kind = getattr(event, "kind", None)
        node = str(getattr(event, "node", "") or agent)
        metadata = {
            "execution_id": self.execution_id,
            "run_id": getattr(event, "run_id", None),
            "step": int(getattr(event, "step", 0) or 0),
            "node": getattr(event, "node", None),
            "task_id": getattr(event, "task_id", None) or self.task_id,
            "namespace": _json_safe(getattr(event, "namespace", None)),
            "checkpoint_id": getattr(event, "checkpoint_id", None),
            "span_id": getattr(event, "span_id", None),
        }
        data = _json_safe(getattr(event, "data", None) or {})
        runtime_kind = f"run.{getattr(kind, 'name', str(kind)).lower()}"
        legacy_kind = runtime_kind
        payload: dict[str, Any] = {"runtime": metadata, "data": data}

        if kind in {
            EventKind.NODE_STARTED,
            EventKind.NODE_COMPLETED,
            EventKind.NODE_FAILED,
            EventKind.NODE_RETRYING,
            EventKind.NODE_CACHED,
        }:
            block_id, block = self._ensure_block(event, agent)
            payload["blockId"] = block_id
            if kind is EventKind.NODE_STARTED:
                legacy_kind = "node.started"
                block["status"] = "running"
                active = self._active_spans.get(block_id)
                if active is None or active.get("status") != "running":
                    attempts = sum(
                        1 for item in self.trace_spans if item.get("blockId") == block_id
                    )
                    span = {
                        "id": metadata["span_id"]
                        or (block_id if attempts == 0 else f"{block_id}:attempt:{attempts + 1}"),
                        "name": node,
                        "type": self.catalog.resolve(node).sim_type,
                        "blockId": block_id,
                        "node": node,
                        "status": "running",
                        "attempt": attempts + 1,
                        "startedAt": _iso(getattr(event, "timestamp", None)),
                        "startTime": _iso(getattr(event, "timestamp", None)),
                        "events": [],
                    }
                    self._active_spans[block_id] = span
                    self.trace_spans.append(span)
            elif kind is EventKind.NODE_COMPLETED:
                legacy_kind = "node.completed"
                block["status"] = "completed"
                block["outputs"] = data.get("update") if isinstance(data, dict) else {}
                span = self._active_spans.get(block_id)
                if span:
                    span.update(
                        {
                            "status": "completed",
                            "endedAt": _iso(getattr(event, "timestamp", None)),
                            "endTime": _iso(getattr(event, "timestamp", None)),
                            "output": block["outputs"],
                        }
                    )
            elif kind is EventKind.NODE_RETRYING:
                legacy_kind = "node.retrying"
                block["status"] = "retrying"
                span = self._active_spans.get(block_id)
                if span and span.get("status") == "running":
                    span.update(
                        {
                            "status": "retrying",
                            "endedAt": _iso(getattr(event, "timestamp", None)),
                            "endTime": _iso(getattr(event, "timestamp", None)),
                        }
                    )
            elif kind is EventKind.NODE_FAILED:
                legacy_kind = "node.failed"
                block["status"] = "failed"
                span = self._active_spans.get(block_id)
                if span:
                    span.update(
                        {
                            "status": "failed",
                            "endedAt": _iso(getattr(event, "timestamp", None)),
                            "endTime": _iso(getattr(event, "timestamp", None)),
                            "error": data,
                        }
                    )
            else:
                legacy_kind = "node.cached"
                block["status"] = "cached"
            if kind is EventKind.NODE_STARTED:
                step = metadata["step"]
                prior = self._last_blocks_by_step.get(step - 1, [])
                for source in prior:
                    self._connect(source, block_id)
                self._last_blocks_by_step.setdefault(step, []).append(block_id)
                if len(self._last_blocks_by_step[step]) > 1:
                    parallel_id = f"parallel:{step}"
                    self.workflow_state["parallels"].setdefault(
                        parallel_id, {"id": parallel_id, "blockIds": []}
                    )["blockIds"].append(block_id)
                if self._node_counts.get(node, 0) > 1:
                    loop_id = f"loop:{node}"
                    self.workflow_state["loops"].setdefault(
                        loop_id, {"id": loop_id, "node": node, "iterations": []}
                    )["iterations"].append(block_id)
        elif kind is EventKind.INTERRUPT_RAISED:
            legacy_kind = "interrupt.raised"
            payload["runtime"]["control"] = "human_in_the_loop"
            self.workflow_state["metadata"]["paused"] = True
        elif kind is EventKind.RUN_PAUSED:
            legacy_kind = "run.paused"
            self.workflow_state["metadata"]["paused"] = True
        elif kind in {
            EventKind.RUN_COMPLETED,
            EventKind.RUN_FAILED,
            EventKind.RUN_CANCELLED,
            EventKind.RUN_TIMED_OUT,
            EventKind.RUN_BUDGET_EXCEEDED,
        }:
            self.workflow_state["metadata"].update(
                {"terminal": True, "status": runtime_kind.removeprefix("run.")}
            )
        elif kind is EventKind.RUN_STARTED:
            legacy_kind = "run.started"
            self.workflow_state["metadata"].update(
                {"startedAt": _iso(getattr(event, "timestamp", None)), "status": "running"}
            )
        elif kind is EventKind.STATE_UPDATED:
            update = data
            if isinstance(data, dict):
                update = data.get("values") or data.get("update") or data
            self.workflow_state["variables"].update(update if isinstance(update, dict) else {})
            legacy_kind = "state.updated"
        elif kind is EventKind.CUSTOM:
            value = data.get("value") if isinstance(data, dict) else None
            if isinstance(value, dict) and value.get("type"):
                legacy_kind = str(value["type"])
                payload.update(
                    {k: _json_safe(v) for k, v in value.items() if k not in {"type", "agent"}}
                )

        return {
            "kind": legacy_kind,
            "agent": agent,
            "payload": payload,
            "runtime": metadata,
            **metadata,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "workflowState": _json_safe(self.workflow_state),
            "traceSpans": _json_safe(self.trace_spans),
            "projectionVersion": PROJECTION_VERSION,
        }
