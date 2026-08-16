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

from .sim_trace import replay_trace, total_tokens

PROJECTION_VERSION = "sim-runtime.v1"


class SimRuntimeError(ValueError):
    """Raised when an execution contains a primitive outside the allow-list."""


@dataclass(frozen=True)
class Primitive:
    sim_type: str
    category: str
    idempotent: bool = False
    label: str = ""


@dataclass(frozen=True)
class VisibleExecution:
    """One learner-meaningful capability allowed onto the runtime graph."""

    key: str
    label: str
    sim_type: str = "agent"
    node_kind: str = "agent"


_VISIBLE_EXECUTIONS: tuple[tuple[VisibleExecution, tuple[str, ...]], ...] = (
    (
        VisibleExecution("tutor", "Tutor"),
        (
            "answer_user",
            "dialog.answer",
            "teach.explain",
            "dialog.negotiate",
            "negotiator",
        ),
    ),
    (
        VisibleExecution("learning_companion", "Learning Companion"),
        (
            "learning_companion",
            "dialog.converse",
        ),
    ),
    (
        VisibleExecution("learner_interview", "了解你的基础"),
        (
            "learner_interview",
            "dialog.interview",
        ),
    ),
    (
        VisibleExecution("socratic_prober", "Socratic Probe"),
        (
            "probe_user",
            "dialog.probe",
        ),
    ),
    (
        VisibleExecution("adaptive_tutor", "Adaptive Tutor"),
        (
            "adaptive_pedagogy",
            "teach.strategy",
        ),
    ),
    (
        VisibleExecution("lesson_intro", "Lesson Intro"),
        (
            "lesson_intro",
            "content.lesson_intro",
            "lecture_hook",
        ),
    ),
    (
        VisibleExecution("lecture_deck", "Lecture Deck"),
        (
            "lecture_deck",
            "content.deck",
            "interactive_lecture_deck",
        ),
    ),
    (
        VisibleExecution("visual_explainer", "Visual Explainer"),
        (
            "visual_explainer",
            "content.visual",
            "interactive_visual_explainer",
        ),
    ),
    (
        VisibleExecution("quiz_generator", "Quiz Generator"),
        (
            "quiz_generator",
            "assess.generate",
        ),
    ),
    (
        VisibleExecution("formative_assessor", "Formative Assessor"),
        (
            "formative_assessor",
            "assess.interpret",
        ),
    ),
    (
        VisibleExecution("retrieval_practice", "Retrieval Practice"),
        (
            "retrieval_practice",
            "review_scheduler",
            "review.schedule",
        ),
    ),
    (
        VisibleExecution("curriculum_mapper", "Curriculum Mapper"),
        (
            "curriculum_mapper",
            "curriculum_graph",
            "prerequisite_analyzer",
            "graph.build",
            "graph.prerequisite",
        ),
    ),
    (
        VisibleExecution("learner_reflector", "Learner Reflector"),
        (
            "learner_reflector",
            "learner_state_reflector",
            "model.reflect",
        ),
    ),
    (
        VisibleExecution("investigator", "Investigator"),
        (
            "investigator",
            "pack_investigate",
            "tool.investigate",
            "web_search",
            "web_fetch",
        ),
    ),
    (
        VisibleExecution("learning_reporter", "Learning Reporter"),
        (
            "learning_reporter",
            "pack_report",
            "meta.report",
        ),
    ),
    (
        VisibleExecution("skill_forge", "Skill Forge"),
        (
            "skill_forge",
            "meta.author_skill",
        ),
    ),
    (
        VisibleExecution("knowledge_probe", "Knowledge Probe", "function", "deterministic"),
        (
            "knowledge_probe",
            "pack_probe",
            "knowledge.search",
            "kb.search",
        ),
    ),
    (
        VisibleExecution(
            "deterministic_grader", "Deterministic Grader", "function", "deterministic"
        ),
        (
            "deterministic_grader",
            "assess.grade",
            "quiz_submit",
        ),
    ),
)

VISIBLE_EXECUTION_BY_ALIAS: dict[str, VisibleExecution] = {
    alias.casefold(): execution for execution, aliases in _VISIBLE_EXECUTIONS for alias in aliases
}


def visible_execution(name: str | None) -> VisibleExecution | None:
    """Resolve a capability/provider name, hiding every runtime mechanic by default."""

    return VISIBLE_EXECUTION_BY_ALIAS.get(str(name or "").strip().casefold())


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
    # Runtime loop nodes are executable graph primitives too.  They must be
    # projected with the same closed-world policy as provider/tool nodes;
    # otherwise the first native NODE_STARTED event fails before the UI can
    # receive any trace data.
    "interpret_goal": Primitive("router_v2", "control", True),
    "orchestrate": Primitive("router_v2", "control", True),
    "dispatch": Primitive("router_v2", "control", True),
    "observe": Primitive("router_v2", "control", True),
    "update_state": Primitive("router_v2", "control", True),
    "evaluate_goal": Primitive("router_v2", "control", True),
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
    _planned_blocks: dict[str, str] = field(default_factory=dict, init=False)
    _plan_dependencies: dict[str, list[str]] = field(default_factory=dict, init=False)
    _planned_by_shape: dict[tuple[str, int], list[str]] = field(default_factory=dict, init=False)

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
        self.workflow_state["metadata"]["layoutVersion"] = "semantic-layered.v2"

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
        execution = visible_execution(node)
        if execution is None:
            raise SimRuntimeError(f"runtime mechanic cannot be projected as a block: {node!r}")
        step = int(getattr(event, "step", 0) or 0)
        task_id = getattr(event, "task_id", None)
        key = (node, step, str(task_id or ""))
        existing = self._block_keys.get(key)
        if existing is not None:
            return existing, self.blocks[existing]
        planned = self._promote_planned_block(execution.key, step)
        if planned is not None:
            block_id, block = planned
            self._block_keys[key] = block_id
            return block_id, block
        block_id = self._block_id(node, step, task_id)
        self._block_keys[key] = block_id
        block = {
            "id": block_id,
            "type": execution.sim_type,
            "name": execution.label,
            "position": {"x": (len(self.blocks) % 4) * 300, "y": (len(self.blocks) // 4) * 160},
            "subBlocks": {},
            "outputs": {},
            "enabled": True,
            "data": {
                "primitive": execution.key,
                "provider": node,
                "category": execution.node_kind,
                "nodeKind": execution.node_kind,
                "executionId": self.execution_id,
                "step": step,
                "taskId": task_id,
                "namespace": _json_safe(getattr(event, "namespace", None)),
            },
            "status": "running",
            "executionState": "running",
        }
        self.blocks[block_id] = block
        return block_id, block

    def _ensure_planned_block(self, payload: dict[str, Any]) -> str | None:
        plan_task_id = str(
            payload.get("node_id")
            or payload.get("work_item_id")
            or payload.get("task_id")
            or ""
        )
        logical_task_id = str(payload.get("task_id") or "")
        step = int(payload.get("step") or 0)
        primitive_name = str(payload.get("capability") or payload.get("node") or "coordinator")
        execution = visible_execution(primitive_name)
        self._plan_dependencies[plan_task_id] = [
            str(item) for item in payload.get("depends_on") or []
        ]
        if execution is None:
            self._rebuild_planned_edges()
            return None
        existing = self._planned_blocks.get(plan_task_id)
        if existing is not None:
            return existing
        block_id = f"plan:{step}:{plan_task_id}".replace("/", "_")
        self.blocks[block_id] = {
            "id": block_id,
            "type": execution.sim_type,
            "name": execution.label,
            "position": {"x": 0, "y": 0},
            "subBlocks": {},
            "outputs": {},
            "enabled": bool(payload.get("allowed", True)),
            "data": {
                "primitive": execution.key,
                "capability": primitive_name,
                "category": execution.node_kind,
                "nodeKind": execution.node_kind,
                "executionId": self.execution_id,
                "step": step,
                "planTaskId": plan_task_id,
                "logicalTaskId": logical_task_id or None,
                "knowledgePointId": payload.get("knowledge_point_id"),
                "rationale": payload.get("rationale"),
                "doneWhen": payload.get("done_when"),
            },
            "status": "queued",
            "executionState": "queued",
        }
        self._planned_blocks[plan_task_id] = block_id
        self._planned_by_shape.setdefault((execution.key, step), []).append(block_id)
        self._rebuild_planned_edges()
        return block_id

    def _visible_plan_ancestors(self, task_id: str, visiting: set[str] | None = None) -> set[str]:
        visiting = set(visiting or ())
        if task_id in visiting:
            return set()
        visiting.add(task_id)
        visible = self._planned_blocks.get(task_id)
        if visible:
            return {visible}
        result: set[str] = set()
        for dependency in self._plan_dependencies.get(task_id, []):
            result.update(self._visible_plan_ancestors(dependency, visiting))
        return result

    def _rebuild_planned_edges(self) -> None:
        self.workflow_state["edges"] = [
            edge
            for edge in self.workflow_state["edges"]
            if (edge.get("data") or {}).get("kind") != "dependency"
        ]
        for task_id, target in self._planned_blocks.items():
            for dependency in self._plan_dependencies.get(task_id, []):
                for source in self._visible_plan_ancestors(dependency):
                    self._connect(
                        source,
                        target,
                        kind="dependency",
                        status="queued",
                        label=(
                            "Capability dependency"
                            if dependency in self._planned_blocks
                            else "Lingxi Runtime"
                        ),
                    )

    def _update_planned_execution(self, payload: dict[str, Any], *, status: str) -> str | None:
        task_id = str(
            payload.get("node_id")
            or payload.get("work_item_id")
            or payload.get("task_id")
            or ""
        )
        block_id = self._planned_blocks.get(task_id)
        if block_id is None:
            execution = visible_execution(
                str(
                    payload.get("provider")
                    or payload.get("agent")
                    or payload.get("capability")
                    or ""
                )
            )
            if execution is not None:
                candidates = [
                    item
                    for item in self.blocks.values()
                    if (item.get("data") or {}).get("primitive") == execution.key
                    and item.get("executionState") in {"queued", "pending", "running"}
                ]
                if candidates:
                    # A repeated logical task id can have several queued
                    # revisions.  The newest queued block is the safest
                    # fallback when an external event has no node id.
                    block_id = str(candidates[-1]["id"])
        if block_id is None:
            return None
        block = self.blocks[block_id]
        actual = visible_execution(
            str(payload.get("provider") or payload.get("agent") or payload.get("capability") or "")
        )
        if actual is not None:
            block["name"] = actual.label
            block["type"] = actual.sim_type
            block["data"]["primitive"] = actual.key
            block["data"]["category"] = actual.node_kind
            block["data"]["nodeKind"] = actual.node_kind
        block["status"] = status
        block["executionState"] = status
        block["data"]["provider"] = payload.get("provider") or payload.get("agent")
        for source, target in (
            ("status", "outcomeStatus"),
            ("satisfied", "satisfied"),
            ("detail", "detail"),
            ("skill_id", "skillId"),
        ):
            if source in payload:
                block["data"][target] = _json_safe(payload[source])
        return block_id

    def _promote_planned_block(self, node: str, step: int) -> tuple[str, dict[str, Any]] | None:
        for block_id in self._planned_by_shape.get((node, step), []):
            block = self.blocks[block_id]
            if block.get("status") in {"queued", "pending"}:
                return block_id, block
        return None

    def _connect(
        self,
        source: str,
        target: str,
        *,
        kind: str = "transition",
        status: str | None = None,
        label: str | None = None,
    ) -> None:
        if not source or not target or source == target:
            return
        edge_id = f"{source}->{target}"
        if any(edge["id"] == edge_id for edge in self.workflow_state["edges"]):
            return
        edge_status = status or "not-executed"
        self.workflow_state["edges"].append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "type": "workflow",
                "status": edge_status,
                "label": label or ("Lingxi Runtime" if kind == "transition" else kind),
                "data": {
                    "kind": kind,
                    "status": edge_status,
                    "label": label or ("Lingxi Runtime" if kind == "transition" else kind),
                },
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
        raw_kind = getattr(kind, "name", str(kind)).lower()
        raw_kind = raw_kind.removeprefix("run_")
        runtime_kind = f"run.{raw_kind}"
        legacy_kind = runtime_kind
        payload: dict[str, Any] = {"runtime": metadata, "data": data}

        node_event_kinds = {
            EventKind.NODE_STARTED,
            EventKind.NODE_COMPLETED,
            EventKind.NODE_FAILED,
            EventKind.NODE_RETRYING,
            EventKind.NODE_CACHED,
        }
        span: dict[str, Any] | None = None
        execution = visible_execution(node)
        if kind in node_event_kinds and execution is not None:
            block_id, block = self._ensure_block(event, agent)
            payload["blockId"] = block_id
            if kind is EventKind.NODE_STARTED:
                legacy_kind = "node.started"
                block["status"] = "running"
                block["executionState"] = "running"
                active = self._active_spans.get(block_id)
                if active is None or active.get("status") != "running":
                    attempts = sum(
                        1 for item in self.trace_spans if item.get("blockId") == block_id
                    )
                    span = {
                        "id": metadata["span_id"]
                        or (block_id if attempts == 0 else f"{block_id}:attempt:{attempts + 1}"),
                        "name": node,
                        "type": execution.sim_type,
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
                block["executionState"] = "completed"
                block["outputs"] = (
                    data.get("update") or {} if isinstance(data, dict) else {}
                )
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
                block["executionState"] = "retrying"
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
                block["executionState"] = "failed"
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
                block["executionState"] = "cached"
            if kind is EventKind.NODE_STARTED:
                step = metadata["step"]
                prior = self._last_blocks_by_step.get(step - 1, [])
                for source in prior:
                    self._connect(source, block_id, status="success")
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
        elif kind in node_event_kinds:
            legacy_kind = {
                EventKind.NODE_STARTED: "node.started",
                EventKind.NODE_COMPLETED: "node.completed",
                EventKind.NODE_FAILED: "node.failed",
                EventKind.NODE_RETRYING: "node.retrying",
                EventKind.NODE_CACHED: "node.cached",
            }[kind]
            payload["hiddenBy"] = "lingxi-runtime"
            payload["runtimeMechanic"] = node
        elif kind is EventKind.INTERRUPT_RAISED:
            legacy_kind = "interrupt.raised"
            payload["runtime"]["control"] = "human_in_the_loop"
            self.workflow_state["metadata"]["paused"] = True
        elif runtime_kind == "run.resumed":
            legacy_kind = "run.resumed"
            self.workflow_state["metadata"].update({"paused": False, "status": "running"})
        elif kind is EventKind.RUN_PAUSED:
            legacy_kind = "run.paused"
            self.workflow_state["metadata"].update({"paused": True, "status": "paused"})
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
            update: dict[str, Any] = dict(data) if isinstance(data, dict) else {}
            if isinstance(data, dict):
                candidate_update = data.get("values") or data.get("update") or data
                if isinstance(candidate_update, dict):
                    update = candidate_update
            self.workflow_state["variables"].update(update if isinstance(update, dict) else {})
            legacy_kind = "state.updated"
        elif kind is EventKind.CUSTOM:
            value = data.get("value") if isinstance(data, dict) else None
            if isinstance(value, dict) and value.get("type"):
                legacy_kind = str(value["type"])
                if legacy_kind == "node.appeared":
                    payload_data = {str(k): _json_safe(v) for k, v in value.items()}
                    planned_block_id = self._ensure_planned_block(payload_data)
                    if planned_block_id is not None:
                        payload["blockId"] = planned_block_id
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

    def consume_runtime_event(
        self, kind: str, payload: dict[str, Any], *, agent: str = "orchestrator"
    ) -> dict[str, Any]:
        """Project Lingxi decision-trace events that are not native graph events."""
        safe_payload = _json_safe(payload)
        result: dict[str, Any] = {
            "kind": kind,
            "agent": agent,
            "payload": safe_payload,
            "runtime": {
                "execution_id": self.execution_id,
                "task_id": self.task_id,
                "step": safe_payload.get("step") if isinstance(safe_payload, dict) else None,
            },
        }
        if kind == "node.appeared" and isinstance(safe_payload, dict):
            block_id = self._ensure_planned_block(safe_payload)
            result["payload"] = dict(safe_payload)
            if block_id is not None:
                result["payload"]["blockId"] = block_id
            else:
                result["payload"]["hiddenBy"] = "lingxi-runtime"
        elif kind in {
            "node.started",
            "node.held",
            "node.revising",
            "node.completed",
            "node.failed",
            "node.retrying",
        }:
            status = {
                "node.started": "running",
                "node.held": "running",
                "node.revising": "running",
                "node.completed": "completed",
                "node.failed": "failed",
                "node.retrying": "retrying",
            }[kind]
            block_id = self._update_planned_execution(safe_payload, status=status)
            if block_id is not None:
                result["payload"] = {**safe_payload, "blockId": block_id}
                if kind in {"node.held", "node.revising"}:
                    result["payload"]["held" if kind == "node.held" else "revising"] = True
        return result

    def snapshot(self) -> dict[str, Any]:
        metadata = self.workflow_state.setdefault("metadata", {})
        self.workflow_state["layoutVersion"] = metadata.get("layoutVersion", "semantic-layered.v2")
        self.workflow_state["terminal"] = bool(metadata.get("terminal", False))
        self.workflow_state["status"] = metadata.get("status", "running")
        self.workflow_state["paused"] = bool(metadata.get("paused", False))
        return {
            "workflowState": _json_safe(self.workflow_state),
            "traceSpans": _json_safe(self.trace_spans),
            "projectionVersion": PROJECTION_VERSION,
        }


def _safe_trace_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply the V2 public event envelope before trace replay.

    Reasoning deltas and raw tool call/result payloads are deliberately never
    reconstructed into the learner-facing Sim trace.
    """
    private = {"reasoning.delta", "tool.call.delta", "tool.result", "assistant.delta"}
    blocked = {"arguments", "input", "output", "result", "content", "thinking", "reasoning"}
    safe: list[dict[str, Any]] = []
    for record in records:
        if str(record.get("kind") or "") in private:
            continue
        item = dict(record)
        payload = dict(item.get("payload") or {})
        item["payload"] = {key: value for key, value in payload.items() if key not in blocked}
        safe.append(item)
    return safe


def replay_sim_trace(
    records: Iterable[dict[str, Any]],
    *,
    execution_id: str,
    task_id: str,
    graph_version: str,
    status: str | None = None,
    started_at: Any = None,
    ended_at: Any = None,
) -> list[dict[str, Any]]:
    return replay_trace(
        _safe_trace_records(records),
        execution_id=execution_id,
        task_id=task_id,
        graph_version=graph_version,
        resolve_primitive=PrimitiveCatalog().resolve,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
    )


def sim_trace_total_tokens(trace: list[dict[str, Any]]) -> dict[str, int]:
    return total_tokens(trace)
