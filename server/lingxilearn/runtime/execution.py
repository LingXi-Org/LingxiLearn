"""LingxiLearn's first-party execution domain.

LingxiGraph remains the executor. This module reduces its event stream into
the learner-meaningful execution snapshot owned by LingxiLearn. It does not
execute graphs and exposes no editor-workflow representation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from lingxigraph import EventKind, RetryPolicy

from .timeline import (
    ExecutionTimeline,
    timeline_total_tokens,
)
from .timeline import (
    replay_timeline as _replay_timeline,
)

EXECUTION_SCHEMA_VERSION = "lingxilearn.execution.v1"


class ExecutionError(ValueError):
    """Structured failure raised by the execution domain."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "execution_error",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


@dataclass(slots=True)
class ExecutionNode:
    """One learner-meaningful node in an execution snapshot."""

    id: str
    label: str
    kind: str
    capability: str
    provider: str | None
    status: str
    step: int
    task_id: str | None = None
    namespace: Any = None
    details: dict[str, Any] = field(default_factory=dict)
    output: Any = None

    def to_dict(self) -> dict[str, Any]:
        value = {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "capability": self.capability,
            "provider": self.provider,
            "status": self.status,
            "step": self.step,
            "taskId": self.task_id,
            "namespace": _json_safe(self.namespace),
            "details": _json_safe(self.details),
        }
        if self.output not in (None, {}, []):
            value["output"] = _json_safe(self.output)
        return value


@dataclass(frozen=True, slots=True)
class ExecutionDependency:
    """A directed relationship between native execution nodes."""

    id: str
    source_node_id: str
    target_node_id: str
    kind: str
    status: str
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceNodeId": self.source_node_id,
            "targetNodeId": self.target_node_id,
            "kind": self.kind,
            "status": self.status,
            "label": self.label,
        }


@dataclass(slots=True)
class ExecutionSnapshot:
    """Native state of one LingxiLearn execution."""

    execution_id: str
    task_id: str
    graph_version: str
    status: str
    paused: bool
    terminal: bool
    nodes: dict[str, ExecutionNode] = field(default_factory=dict)
    dependencies: list[ExecutionDependency] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    groups: dict[str, Any] = field(default_factory=lambda: {"loops": {}, "parallels": {}})
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": EXECUTION_SCHEMA_VERSION,
            "executionId": self.execution_id,
            "taskId": self.task_id,
            "graphVersion": self.graph_version,
            "status": self.status,
            "paused": self.paused,
            "terminal": self.terminal,
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "dependencies": [dependency.to_dict() for dependency in self.dependencies],
            "variables": _json_safe(self.variables),
            "groups": _json_safe(self.groups),
            "metadata": _json_safe(self.metadata),
        }


@dataclass(frozen=True)
class Primitive:
    display_kind: str
    category: str
    idempotent: bool = False
    label: str = ""


@dataclass(frozen=True)
class VisibleExecution:
    """One learner-meaningful capability allowed onto the runtime graph."""

    key: str
    label: str
    display_kind: str = "agent"
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
    """Closed mapping of LingxiLearn primitives to execution capability semantics."""

    def __init__(self, entries: dict[str, Primitive] | None = None) -> None:
        self.entries = dict(entries or PRIMITIVE_CATALOG)

    def resolve(self, name: str) -> Primitive:
        key = str(name or "").strip()
        try:
            return self.entries[key]
        except KeyError as exc:
            raise ExecutionError(f"unregistered LingxiLearn primitive: {key!r}") from exc

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
            raise ExecutionError(f"retry is only allowed for idempotent primitive: {name}")
        return {"maxTries": int(max_tries), "wait": float(wait_seconds), "backoff": "fixed"}

    def lingxi_retry_policy(
        self, name: str, *, max_tries: int = 1, wait_seconds: float = 0.0
    ) -> RetryPolicy | None:
        """Translate an approved execution retry policy to LingxiGraph semantics."""
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


def _elapsed_ms(started_at: str, ended_at: str) -> int:
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return 0
    return max(0, int((end - start).total_seconds() * 1000))


def require_execution_snapshot(
    value: Mapping[str, Any] | None,
    *,
    execution_id: str,
    task_id: str,
    graph_version: str,
    status: str | None = None,
) -> dict[str, Any]:
    """Validate persisted native state and fail closed on every other schema."""

    state = dict(value or {})
    required = {
        "schemaVersion",
        "executionId",
        "taskId",
        "graphVersion",
        "status",
        "paused",
        "terminal",
        "nodes",
        "dependencies",
        "variables",
        "groups",
        "metadata",
    }
    if state.get("schemaVersion") != EXECUTION_SCHEMA_VERSION or not required <= state.keys():
        raise ExecutionError(
            "unsupported execution snapshot schema; expected lingxilearn.execution.v1",
            code="invalid_execution_schema",
        )
    if (
        str(state.get("executionId")) != execution_id
        or str(state.get("taskId")) != task_id
        or str(state.get("graphVersion")) != graph_version
    ):
        raise ExecutionError(
            "persisted execution identity does not match the requested execution",
            code="execution_identity_mismatch",
        )
    if not isinstance(state.get("nodes"), Mapping) or not isinstance(
        state.get("dependencies"), list
    ):
        raise ExecutionError("persisted execution state is malformed", code="invalid_execution_schema")
    if not all(
        isinstance(state.get(key), Mapping) for key in ("variables", "groups", "metadata")
    ) or not isinstance(state.get("paused"), bool) or not isinstance(state.get("terminal"), bool):
        raise ExecutionError("persisted execution state is malformed", code="invalid_execution_schema")
    node_required = {"id", "label", "kind", "capability", "status", "step", "details"}
    for node_id, node in state["nodes"].items():
        if (
            not isinstance(node, Mapping)
            or not node_required <= node.keys()
            or str(node.get("id")) != str(node_id)
        ):
            raise ExecutionError(
                "persisted execution contains a malformed node",
                code="invalid_execution_schema",
            )
    dependency_required = {
        "id",
        "sourceNodeId",
        "targetNodeId",
        "kind",
        "status",
        "label",
    }
    if any(
        not isinstance(dependency, Mapping) or not dependency_required <= dependency.keys()
        for dependency in state["dependencies"]
    ):
        raise ExecutionError(
            "persisted execution contains a malformed dependency",
            code="invalid_execution_schema",
        )
    state["status"] = status or state["status"]
    return _json_safe(state)


@dataclass
class ExecutionProjector:
    """Incrementally project a single StateGraph execution."""

    execution_id: str
    task_id: str
    graph_version: str
    catalog: PrimitiveCatalog = field(default_factory=PrimitiveCatalog)
    state: ExecutionSnapshot = field(init=False)
    timeline_spans: list[dict[str, Any]] = field(default_factory=list)
    _last_nodes_by_step: dict[int, list[str]] = field(default_factory=dict, init=False)
    _active_spans: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)
    _node_counts: dict[str, int] = field(default_factory=dict, init=False)
    _node_keys: dict[tuple[str, int, str], str] = field(default_factory=dict, init=False)
    _planned_nodes: dict[str, str] = field(default_factory=dict, init=False)
    _plan_dependencies: dict[str, list[str]] = field(default_factory=dict, init=False)
    _planned_by_shape: dict[tuple[str, int], list[str]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.state = ExecutionSnapshot(
            execution_id=self.execution_id,
            task_id=self.task_id,
            graph_version=self.graph_version,
            status="running",
            paused=False,
            terminal=False,
            metadata={"executionId": self.execution_id, "taskId": self.task_id},
        )

    @property
    def nodes(self) -> dict[str, ExecutionNode]:
        return self.state.nodes

    def _node_id(self, node: str, step: int, task_id: str | None) -> str:
        count = self._node_counts.get(node, 0) + 1
        self._node_counts[node] = count
        suffix = str(task_id or count).replace("/", "_")
        return f"{node}:{step}:{suffix}"

    def _ensure_node(self, event: Any, agent: str | None = None) -> tuple[str, ExecutionNode]:
        provider = str(getattr(event, "node", "") or agent or "coordinator")
        execution = visible_execution(provider)
        if execution is None:
            raise ExecutionError(f"runtime mechanic cannot be projected as a node: {provider!r}")
        step = int(getattr(event, "step", 0) or 0)
        task_id = getattr(event, "task_id", None)
        key = (provider, step, str(task_id or ""))
        existing = self._node_keys.get(key)
        if existing is not None:
            return existing, self.nodes[existing]
        planned = self._promote_planned_node(execution.key, step)
        if planned is not None:
            node_id, execution_node = planned
            self._node_keys[key] = node_id
            return node_id, execution_node
        node_id = self._node_id(provider, step, task_id)
        self._node_keys[key] = node_id
        execution_node = ExecutionNode(
            id=node_id,
            label=execution.label,
            kind=execution.node_kind,
            capability=execution.key,
            provider=provider,
            status="running",
            step=step,
            task_id=task_id,
            namespace=_json_safe(getattr(event, "namespace", None)),
            details={"executionId": self.execution_id},
        )
        self.nodes[node_id] = execution_node
        return node_id, execution_node

    def _ensure_planned_node(self, payload: dict[str, Any]) -> str | None:
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
        existing = self._planned_nodes.get(plan_task_id)
        if existing is not None:
            return existing
        node_id = f"plan:{step}:{plan_task_id}".replace("/", "_")
        self.nodes[node_id] = ExecutionNode(
            id=node_id,
            label=execution.label,
            kind=execution.node_kind,
            capability=execution.key,
            provider=None,
            status="queued",
            step=step,
            task_id=logical_task_id or None,
            details={
                "declaredCapability": primitive_name,
                "planTaskId": plan_task_id,
                "knowledgePointId": payload.get("knowledge_point_id"),
                "rationale": payload.get("rationale"),
                "doneWhen": payload.get("done_when"),
                "allowed": bool(payload.get("allowed", True)),
            },
        )
        self._planned_nodes[plan_task_id] = node_id
        self._planned_by_shape.setdefault((execution.key, step), []).append(node_id)
        self._rebuild_planned_edges()
        return node_id

    def _visible_plan_ancestors(self, task_id: str, visiting: set[str] | None = None) -> set[str]:
        visiting = set(visiting or ())
        if task_id in visiting:
            return set()
        visiting.add(task_id)
        visible = self._planned_nodes.get(task_id)
        if visible:
            return {visible}
        result: set[str] = set()
        for dependency in self._plan_dependencies.get(task_id, []):
            result.update(self._visible_plan_ancestors(dependency, visiting))
        return result

    def _rebuild_planned_edges(self) -> None:
        self.state.dependencies = [
            dependency for dependency in self.state.dependencies if dependency.kind != "dependency"
        ]
        for task_id, target in self._planned_nodes.items():
            for dependency in self._plan_dependencies.get(task_id, []):
                for source in self._visible_plan_ancestors(dependency):
                    self._connect(
                        source,
                        target,
                        kind="dependency",
                        status="queued",
                        label=(
                            "Capability dependency"
                            if dependency in self._planned_nodes
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
        node_id = self._planned_nodes.get(task_id)
        if node_id is None:
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
                    for item in self.nodes.values()
                    if item.capability == execution.key
                    and item.status in {"queued", "pending", "running"}
                ]
                if candidates:
                    # A repeated logical task id can have several queued
                    # revisions.  The newest queued node is the safest
                    # fallback when an external event has no node id.
                    node_id = candidates[-1].id
        if node_id is None:
            return None
        node = self.nodes[node_id]
        actual = visible_execution(
            str(payload.get("provider") or payload.get("agent") or payload.get("capability") or "")
        )
        if actual is not None:
            node.label = actual.label
            node.capability = actual.key
            node.kind = actual.node_kind
        node.status = status
        node.provider = str(payload.get("provider") or payload.get("agent") or "") or None
        for source, target in (
            ("status", "outcomeStatus"),
            ("satisfied", "satisfied"),
            ("detail", "detail"),
            ("skill_id", "skillId"),
        ):
            if source in payload:
                node.details[target] = _json_safe(payload[source])
        return node_id

    def _promote_planned_node(
        self, capability: str, step: int
    ) -> tuple[str, ExecutionNode] | None:
        for node_id in self._planned_by_shape.get((capability, step), []):
            execution_node = self.nodes[node_id]
            if execution_node.status in {"queued", "pending"}:
                return node_id, execution_node
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
        dependency_id = f"{source}->{target}"
        if any(dependency.id == dependency_id for dependency in self.state.dependencies):
            return
        dependency_status = status or "not-executed"
        self.state.dependencies.append(
            ExecutionDependency(
                id=dependency_id,
                source_node_id=source,
                target_node_id=target,
                kind=kind,
                status=dependency_status,
                label=label or ("Lingxi Runtime" if kind == "transition" else kind),
            )
        )

    def consume(self, event: Any, *, agent: str = "coordinator") -> dict[str, Any]:
        """Consume one native event and return the public envelope."""

        kind = getattr(event, "kind", None)
        provider = str(getattr(event, "node", "") or agent)
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
        event_kind = runtime_kind
        payload: dict[str, Any] = {"runtime": metadata, "data": data}

        node_event_kinds = {
            EventKind.NODE_STARTED,
            EventKind.NODE_COMPLETED,
            EventKind.NODE_FAILED,
            EventKind.NODE_RETRYING,
            EventKind.NODE_CACHED,
        }
        span: dict[str, Any] | None = None
        execution = visible_execution(provider)
        if kind in node_event_kinds and execution is not None:
            node_id, execution_node = self._ensure_node(event, agent)
            payload["nodeId"] = node_id
            if kind is EventKind.NODE_STARTED:
                event_kind = "node.started"
                execution_node.status = "running"
                active = self._active_spans.get(node_id)
                if active is None or active.get("status") != "running":
                    attempts = sum(1 for item in self.timeline_spans if item.get("nodeId") == node_id)
                    started_at = _iso(getattr(event, "timestamp", None))
                    span = {
                        "id": metadata["span_id"]
                        or (node_id if attempts == 0 else f"{node_id}:attempt:{attempts + 1}"),
                        "name": execution.label,
                        "kind": execution.display_kind,
                        "nodeId": node_id,
                        "capability": execution.key,
                        "provider": provider,
                        "status": "running",
                        "attempt": attempts + 1,
                        "startedAt": started_at,
                        "endedAt": started_at,
                        "durationMs": 0,
                        "children": [],
                        "events": [],
                    }
                    self._active_spans[node_id] = span
                    self.timeline_spans.append(span)
            elif kind is EventKind.NODE_COMPLETED:
                event_kind = "node.completed"
                execution_node.status = "completed"
                execution_node.output = data.get("update") or {} if isinstance(data, dict) else {}
                span = self._active_spans.get(node_id)
                if span:
                    ended_at = _iso(getattr(event, "timestamp", None))
                    span.update(
                        {
                            "status": "completed",
                            "endedAt": ended_at,
                            "durationMs": _elapsed_ms(str(span["startedAt"]), ended_at),
                            "output": execution_node.output,
                        }
                    )
            elif kind is EventKind.NODE_RETRYING:
                event_kind = "node.retrying"
                execution_node.status = "retrying"
                span = self._active_spans.get(node_id)
                if span and span.get("status") == "running":
                    ended_at = _iso(getattr(event, "timestamp", None))
                    span.update(
                        {
                            "status": "retrying",
                            "endedAt": ended_at,
                            "durationMs": _elapsed_ms(str(span["startedAt"]), ended_at),
                        }
                    )
            elif kind is EventKind.NODE_FAILED:
                event_kind = "node.failed"
                execution_node.status = "failed"
                span = self._active_spans.get(node_id)
                if span:
                    ended_at = _iso(getattr(event, "timestamp", None))
                    span.update(
                        {
                            "status": "failed",
                            "endedAt": ended_at,
                            "durationMs": _elapsed_ms(str(span["startedAt"]), ended_at),
                            "error": data,
                        }
                    )
            else:
                event_kind = "node.cached"
                execution_node.status = "cached"
            if kind is EventKind.NODE_STARTED:
                step = metadata["step"]
                prior = self._last_nodes_by_step.get(step - 1, [])
                for source in prior:
                    self._connect(source, node_id, status="success")
                self._last_nodes_by_step.setdefault(step, []).append(node_id)
                if len(self._last_nodes_by_step[step]) > 1:
                    parallel_id = f"parallel:{step}"
                    self.state.groups["parallels"].setdefault(
                        parallel_id, {"id": parallel_id, "nodeIds": []}
                    )["nodeIds"].append(node_id)
                if self._node_counts.get(provider, 0) > 1:
                    loop_id = f"loop:{provider}"
                    self.state.groups["loops"].setdefault(
                        loop_id, {"id": loop_id, "provider": provider, "iterations": []}
                    )["iterations"].append(node_id)
        elif kind in node_event_kinds:
            event_kind = {
                EventKind.NODE_STARTED: "node.started",
                EventKind.NODE_COMPLETED: "node.completed",
                EventKind.NODE_FAILED: "node.failed",
                EventKind.NODE_RETRYING: "node.retrying",
                EventKind.NODE_CACHED: "node.cached",
            }[kind]
            payload["hiddenBy"] = "lingxi-runtime"
            payload["runtimeMechanic"] = provider
        elif kind is EventKind.INTERRUPT_RAISED:
            event_kind = "interrupt.raised"
            payload["runtime"]["control"] = "human_in_the_loop"
            self.state.paused = True
        elif runtime_kind == "run.resumed":
            event_kind = "run.resumed"
            self.state.paused = False
            self.state.status = "running"
        elif kind is EventKind.RUN_PAUSED:
            event_kind = "run.paused"
            self.state.paused = True
            self.state.status = "paused"
        elif kind in {
            EventKind.RUN_COMPLETED,
            EventKind.RUN_FAILED,
            EventKind.RUN_CANCELLED,
            EventKind.RUN_TIMED_OUT,
            EventKind.RUN_BUDGET_EXCEEDED,
        }:
            self.state.terminal = True
            self.state.status = runtime_kind.removeprefix("run.")
        elif kind is EventKind.RUN_STARTED:
            event_kind = "run.started"
            self.state.metadata["startedAt"] = _iso(getattr(event, "timestamp", None))
            self.state.status = "running"
        elif kind is EventKind.STATE_UPDATED:
            update: dict[str, Any] = dict(data) if isinstance(data, dict) else {}
            if isinstance(data, dict):
                candidate_update = data.get("values") or data.get("update") or data
                if isinstance(candidate_update, dict):
                    update = candidate_update
            self.state.variables.update(update if isinstance(update, dict) else {})
            event_kind = "state.updated"
        elif kind is EventKind.CUSTOM:
            value = data.get("value") if isinstance(data, dict) else None
            if isinstance(value, dict) and value.get("type"):
                event_kind = str(value["type"])
                if event_kind == "node.appeared":
                    payload_data = {str(k): _json_safe(v) for k, v in value.items()}
                    planned_node_id = self._ensure_planned_node(payload_data)
                    if planned_node_id is not None:
                        payload["nodeId"] = planned_node_id
                payload.update(
                    {k: _json_safe(v) for k, v in value.items() if k not in {"type", "agent"}}
                )

        return {
            "kind": event_kind,
            "agent": agent,
            "payload": payload,
            "runtime": metadata,
            **metadata,
        }

    def consume_runtime_event(
        self, kind: str, payload: dict[str, Any], *, agent: str = "orchestrator"
    ) -> dict[str, Any]:
        """Project Lingxi decision-spans events that are not native graph events."""
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
            node_id = self._ensure_planned_node(safe_payload)
            result["payload"] = dict(safe_payload)
            if node_id is not None:
                result["payload"]["nodeId"] = node_id
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
            node_id = self._update_planned_execution(safe_payload, status=status)
            if node_id is not None:
                result["payload"] = {**safe_payload, "nodeId": node_id}
                if kind in {"node.held", "node.revising"}:
                    result["payload"]["held" if kind == "node.held" else "revising"] = True
        return result

    def snapshot(self) -> dict[str, Any]:
        timeline = ExecutionTimeline.from_native(self.execution_id, self.timeline_spans)
        return {
            "snapshot": self.state.to_dict(),
            "timeline": timeline.to_dict(),
        }


def _safe_timeline_records(records: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Apply the V2 public event envelope before timeline replay.

    Reasoning deltas and raw tool call/result payloads are deliberately never
    reconstructed into the learner-facing execution timeline.
    """
    private = {"reasoning.delta", "tool.call.delta", "tool.result", "assistant.delta"}
    blocked = {"arguments", "input", "output", "result", "content", "thinking", "reasoning"}
    safe: list[Mapping[str, Any]] = []
    for record in records:
        if str(record.get("kind") or "") in private:
            continue
        item = dict(record)
        payload = dict(item.get("payload") or {})
        item["payload"] = {key: value for key, value in payload.items() if key not in blocked}
        safe.append(item)
    return safe


def replay_execution_timeline(
    records: Iterable[Mapping[str, Any]],
    *,
    execution_id: str,
    task_id: str,
    graph_version: str,
    status: str | None = None,
    started_at: Any = None,
    ended_at: Any = None,
) -> list[dict[str, Any]]:
    spans = _replay_timeline(
        _safe_timeline_records(records),
        execution_id=execution_id,
        task_id=task_id,
        graph_version=graph_version,
        resolve_primitive=PrimitiveCatalog().resolve,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
    )
    return spans


def execution_timeline_total_tokens(spans: list[dict[str, Any]]) -> int:
    return timeline_total_tokens(spans)
