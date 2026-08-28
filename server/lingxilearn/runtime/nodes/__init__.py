"""Node implementations for the constrained autonomous loop.

Each module here owns exactly one phase of the loop; the graph topology
itself (edges, conditional routing, wiring) lives in
:mod:`lingxilearn.runtime.graph` and may not be declared anywhere else.

Nodes advance the runtime phase exclusively through
:meth:`lingxilearn.runtime.graph.LoopDeps.transition_status` — the single
lifecycle write path owned by the graph runtime —
and request HITL interactions exclusively through
:func:`lingxilearn.runtime.interactions.request_interaction`.
"""

from .evaluation import build_evaluate_goal_node
from .execution import build_dispatch_node
from .goal import build_interpret_goal_node
from .observation import build_observe_node, build_update_state_node
from .orchestration import build_orchestrate_node

__all__ = [
    "build_dispatch_node",
    "build_evaluate_goal_node",
    "build_interpret_goal_node",
    "build_observe_node",
    "build_orchestrate_node",
    "build_update_state_node",
]
