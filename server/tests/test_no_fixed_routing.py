"""Acceptance criterion 3, as a build failure rather than a code review.

The refactor's one hard rule: what runs next is computed from state, never
selected by a branch on what the learner said. These checks walk the package AST
and fail if that shape comes back — under any name.

They are written to catch the *shape*, not the old identifiers, because the way
this regresses is someone adding `if goal_type == "review": run_review_flow()`
in good faith.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "lingxilearn"

LOOP = PACKAGE / "runtime" / "graph.py"
"""The only module allowed to declare graph topology.

Historically this was ``loop.py``; the topology now lives in ``graph.py``
(with node implementations under ``runtime/nodes/``) as part of the runtime
lifecycle refactor (issues #35, #59).  ``loop.py`` is a thin
backward-compatible re-export.
"""

DISPATCH = PACKAGE / "runtime" / "dispatch.py"
"""The only module allowed to turn a capability into a call."""

LOOP_CONTROL_NODES = {
    "interpret_goal",
    "orchestrate",
    "dispatch",
    "observe",
    "update_state",
    "evaluate_goal",
    "await_user",
    "end",
    "__end__",
}

BANNED_IDENTIFIERS = {
    "INTENT_PROMPT",
    "_route_from_state",
    "route_after_investigate",
    "route_after_advance",
    "knowledge_deep_dive",
    "build_agent_graph",
    "build_knowledge_deep_dive_graph",
    "_GRAPH_NODE_TO_AGENT",
    "_AGENT_NODES",
}

ROUTING_FIELDS = {"route", "intent", "workflow", "next_node", "goal_type", "kind"}
"""Reading these is fine. Branching on them to pick what runs is not."""


def _modules() -> list[Path]:
    return sorted(path for path in PACKAGE.rglob("*.py") if "__pycache__" not in path.parts)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_the_deleted_routing_machinery_has_not_come_back() -> None:
    offenders: list[str] = []
    for path in _modules():
        source = path.read_text(encoding="utf-8")
        for name in BANNED_IDENTIFIERS:
            if name in source:
                offenders.append(f"{path.relative_to(PACKAGE)}: {name}")
    assert not offenders, "the intent-routing machinery reappeared: " + "; ".join(offenders)


def test_only_the_loop_declares_graph_topology() -> None:
    """One graph. A second ``StateGraph`` is a second topology by definition."""

    offenders: list[str] = []
    for path in _modules():
        if path == LOOP:
            continue
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "StateGraph":
                    offenders.append(f"{path.relative_to(PACKAGE)}:{node.lineno}")
    assert not offenders, "only runtime/graph.py may build a StateGraph; found one at " + "; ".join(
        offenders
    )


def test_conditional_edges_exist_only_in_the_loop_and_name_no_domain_concept() -> None:
    """The loop's branch may choose a phase. It may not choose a subject."""

    for path in _modules():
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else getattr(node.func, "id", "")
            )
            if name != "add_conditional_edges":
                continue
            assert path == LOOP, (
                f"conditional routing outside runtime/graph.py: "
                f"{path.relative_to(PACKAGE)}:{node.lineno}"
            )
            mapping = next(
                (arg for arg in node.args if isinstance(arg, ast.Dict)),
                None,
            )
            assert mapping is not None, "the loop's routing map must be a literal to audit"
            targets = {
                key.value
                for key in mapping.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            unexpected = targets - LOOP_CONTROL_NODES
            assert not unexpected, (
                "the loop's only branch must route between loop phases, never to a "
                f"domain step; found {sorted(unexpected)}"
            )


def test_no_module_branches_on_a_routing_field_to_pick_what_runs() -> None:
    """``if intent == X: run_workflow_X`` in any spelling.

    The signal is a comparison against a routing-ish field whose body then
    calls something. Reading ``goal_type`` to build a payload is fine; using it
    to decide which function executes is the pattern being removed.
    """

    offenders: list[str] = []
    for path in _modules():
        if path == DISPATCH:
            continue
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.If):
                continue
            if not _compares_routing_field(node.test):
                continue
            if _body_dispatches(node):
                offenders.append(f"{path.relative_to(PACKAGE)}:{node.lineno}")
    assert not offenders, "a branch on an intent-like field decides what runs at " + "; ".join(
        offenders
    )


def _compares_routing_field(test: ast.expr) -> bool:
    for node in ast.walk(test):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        field = (
            left.attr
            if isinstance(left, ast.Attribute)
            else (
                left.slice.value
                if isinstance(left, ast.Subscript)
                and isinstance(left.slice, ast.Constant)
                and isinstance(left.slice.value, str)
                else getattr(left, "id", "")
            )
        )
        if field in ROUTING_FIELDS and any(
            isinstance(comparator, ast.Constant) and isinstance(comparator.value, str)
            for comparator in node.comparators
        ):
            return True
    return False


_RUNNER_METHODS = {"run", "invoke", "ainvoke", "astream", "execute", "dispatch"}
_RUNNER_PREFIXES = ("run_", "build_", "start_", "execute_", "schedule_")


def _body_dispatches(node: ast.If) -> bool:
    """True when the branch body *runs* something rather than shaping a value.

    A bare ``await`` does not count: reading a row is ordinary async work, and
    treating it as dispatch made this guard fire on resource lookups.
    """

    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Attribute) and child.func.attr in _RUNNER_METHODS:
            return True
        if isinstance(child.func, ast.Name) and child.func.id.startswith(_RUNNER_PREFIXES):
            return True
    return False


def test_the_provider_table_is_populated_by_registration_not_by_a_literal() -> None:
    """No module may hard-code a capability-to-implementation map.

    ``base._PROVIDERS`` is a plugin table keyed by provider *name* and filled by
    decorators, which is a different thing: it says how to run something, never
    when.
    """

    from lingxilearn.state.capabilities import Capability

    tags = {str(item) for item in Capability}
    offenders: list[str] = []
    for path in _modules():
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Dict):
                continue
            keys = {
                key.value
                for key in node.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            if not keys & tags:
                continue
            if any(isinstance(value, (ast.Name, ast.Lambda)) for value in node.values):
                offenders.append(f"{path.relative_to(PACKAGE)}:{node.lineno}")
    assert not offenders, (
        "a literal capability→callable table bypasses the registry at " + "; ".join(offenders)
    )


def test_providers_are_resolved_through_the_registry() -> None:
    """Dispatch must look a provider up, not import one directly."""

    source = DISPATCH.read_text(encoding="utf-8")
    assert "resolve(" in source
    assert "skill_registry" in source or "skills" in source
    for module in ("providers.content", "providers.teaching", "providers.assessment"):
        assert module not in source, (
            f"dispatch imports {module} directly, which pins a capability to an implementation"
        )
