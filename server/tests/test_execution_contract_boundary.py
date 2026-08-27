from __future__ import annotations

import re
from pathlib import Path

import lingxilearn.runtime as runtime

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
