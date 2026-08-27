from __future__ import annotations

import re
from inspect import getsource
from pathlib import Path

import lingxilearn.runtime as runtime
from lingxilearn.runtime.execution import ExecutionProjector
from lingxilearn.runtime.timeline import ExecutionTimelineProjector
from lingxilearn.store.models.runtime import AgentExecution

SERVER_ROOT = Path(__file__).parents[1] / "lingxilearn"
EXECUTION_BOUNDARY = tuple(
    SERVER_ROOT / name for name in ("runtime", "application", "api", "contracts")
)
BANNED_EXECUTION_PRIMITIVES = re.compile(r"SimRun|SimTrace|sim-runtime|sim_(?:semantics|trace)")


def test_legacy_execution_projection_modules_are_removed() -> None:
    assert not (SERVER_ROOT / "runtime" / "sim_semantics.py").exists()
    assert not (SERVER_ROOT / "runtime" / "sim_trace.py").exists()


def test_execution_boundary_cannot_reintroduce_legacy_primitives() -> None:
    violations: list[str] = []
    for directory in EXECUTION_BOUNDARY:
        for path in directory.rglob("*.py"):
            if BANNED_EXECUTION_PRIMITIVES.search(path.read_text(encoding="utf-8")):
                violations.append(str(path.relative_to(SERVER_ROOT)))
    assert violations == []


def test_runtime_public_api_is_lingxilearn_owned() -> None:
    exported = set(runtime.__all__)
    assert {"ExecutionSnapshot", "ExecutionSpan", "ExecutionTimeline", "ExecutionError"} <= exported
    assert not any(name.startswith("Sim") or name.startswith("sim_") for name in exported)


def test_execution_projectors_own_native_state_from_event_to_snapshot() -> None:
    execution_source = getsource(ExecutionProjector)
    timeline_source = getsource(ExecutionTimelineProjector)
    for editor_token in (
        "workflow_state",
        '"blocks"',
        '"edges"',
        "subBlocks",
        "position",
        "executionState",
        "stored_execution_snapshot",
    ):
        assert editor_token not in execution_source
    for legacy_span_token in (
        '"type": primitive',
        '"startTime"',
        '"endTime"',
        '"duration"',
        '"blockId"',
        "from_mapping",
    ):
        assert legacy_span_token not in timeline_source

    snapshot = ExecutionProjector("exec-gate", "task-gate", "v1").snapshot()["snapshot"]
    assert snapshot["schemaVersion"] == "lingxilearn.execution.v1"
    assert set(snapshot) >= {"nodes", "dependencies", "variables", "groups", "metadata"}
    assert not ({"blocks", "edges"} & set(snapshot))

    persisted_columns = set(AgentExecution.__table__.columns.keys())
    assert {"execution_snapshot", "timeline_spans"} <= persisted_columns
    assert not {"workflow_state", "trace_spans"} & persisted_columns
