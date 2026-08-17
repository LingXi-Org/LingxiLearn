"""Architecture guards for the runtime module split (issues #32, #33, #35, #59).

These checks exist so the two invariants the runtime split was built on fail
as tests rather than as code review:

* **One Interaction-request owner.**  The pre-execution HITL clarification
  (``nodes/orchestration.py``) and the post-answer follow-up
  (``nodes/evaluation.py``) must both go through
  ``interactions.request_interaction`` — duplicating the persistence/event
  logic inline is the regression PR #73 blocker A guards against.
* **One lifecycle write path.**  Nodes advance the runtime phase only via
  ``LoopDeps.transition_status``; a direct ``set_runtime_status`` call in a
  node reintroduces the DB/checkpoint double write issue #35 removed.
"""

from __future__ import annotations

from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1] / "lingxilearn" / "runtime"


def _modules() -> list[Path]:
    return sorted(path for path in RUNTIME.rglob("*.py") if "__pycache__" not in path.parts)


def test_interaction_requests_have_a_single_owner() -> None:
    """``create_interaction`` persistence may be declared in exactly one place."""

    persisting: list[str] = []
    requesting: list[str] = []
    for path in _modules():
        source = path.read_text(encoding="utf-8")
        if ".create_interaction(" in source:
            persisting.append(str(path.relative_to(RUNTIME)))
        if "def request_interaction(" in source or "def _request_interaction(" in source:
            requesting.append(str(path.relative_to(RUNTIME)))
    assert persisting == ["interactions.py"], (
        "only runtime/interactions.py may persist an Interaction "
        "(the single request owner); found callers in: " + ", ".join(persisting)
    )
    assert requesting == ["interactions.py"], (
        "request_interaction must be defined exactly once, in "
        "runtime/interactions.py; found definitions in: " + ", ".join(requesting)
    )


def test_nodes_request_interactions_through_the_owner() -> None:
    """Node modules call the owner instead of inlining persistence/events."""

    for path in _modules():
        if path.parent.name != "nodes":
            continue
        source = path.read_text(encoding="utf-8")
        assert "interaction.requested" not in source, (
            f"{path.name} emits the interaction.requested event directly; "
            "route it through interactions.request_interaction"
        )
        assert "new_interaction_id" not in source, (
            f"{path.name} mints interaction ids directly; "
            "route requests through interactions.request_interaction"
        )


def test_nodes_transition_status_through_the_single_lifecycle_owner() -> None:
    """No node may write the runtime phase directly (issue #35)."""

    offenders: list[str] = []
    for path in _modules():
        # graph.py hosts the owner itself (LoopDeps.transition_status);
        # lifecycle.py is its documentation-only contract module.
        if path.name in {"graph.py", "lifecycle.py"}:
            continue
        source = path.read_text(encoding="utf-8")
        if "set_runtime_status" in source:
            offenders.append(str(path.relative_to(RUNTIME)))
    assert not offenders, (
        "runtime phase writes must go through LoopDeps.transition_status, not "
        "set_runtime_status; found direct writes in: " + ", ".join(offenders)
    )


def test_graph_module_only_declares_topology_and_wiring() -> None:
    """``graph.py`` stays a thin shape file; node bodies live in ``nodes/``.

    The signal is import-level: wiring needs dispatch (to construct the one
    shared Dispatcher) but never the phase engines.  If ``graph.py`` starts
    importing ``goal_interpreter`` or ``orchestrator``, business code has
    moved back in.
    """

    source = (RUNTIME / "graph.py").read_text(encoding="utf-8")
    assert "goal_interpreter" not in source
    assert "orchestrator.plan" not in source
    assert source.count("async def") == 1, (
        "graph.py should define exactly one async function "
        "(LoopDeps.transition_status); node implementations belong in nodes/"
    )
