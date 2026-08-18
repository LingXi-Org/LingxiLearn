"""Backward-compatible re-export of the runtime loop.

The implementation was split as part of the runtime lifecycle refactor
(issues #35, #59):

* :mod:`lingxilearn.runtime.graph` — ``LoopState``, ``LoopDeps``, graph
  construction, edges, conditional routing, node wiring.
* :mod:`lingxilearn.runtime.nodes` — one module per loop phase.
* :mod:`lingxilearn.runtime.interactions` — the single Interaction-request
  owner (``request_interaction``) and the ``await_user`` node.
* :mod:`lingxilearn.runtime.evaluation` — pure round-exit policy.
* :mod:`lingxilearn.runtime.lifecycle` — the canonical transition contract.

Import from :mod:`lingxilearn.runtime.graph` in new code; this module keeps
the historical ``runtime.loop`` import path working.
"""

from __future__ import annotations

from .graph import (
    GRAPH_NAME,
    GRAPH_VERSION,
    GoalStack,
    LoopDeps,
    LoopState,
    build_loop,
    initial_state,
)

__all__ = [
    "GRAPH_NAME",
    "GRAPH_VERSION",
    "GoalStack",
    "LoopDeps",
    "LoopState",
    "build_loop",
    "initial_state",
]
