"""Canonical runtime lifecycle transition API.

This is the **single owner** of runtime phase transitions for the
constrained autonomous loop.  Every graph node that needs to advance the
runtime phase calls :meth:`LoopDeps.transition_status
<lingxilearn.runtime.graph.LoopDeps.transition_status>` instead of writing
to both the database and the graph checkpoint independently.

The transition validation rules live in
:mod:`lingxilearn.state.session_state` (``_TRANSITIONS``).  They are not
duplicated here or in any graph node.

.. seealso::

   * :func:`lingxilearn.state.session_state.transition` — the pure
     validation function.
   * :class:`lingxilearn.state.session_state.RuntimeStatus` — the closed
     phase enum.
   * :mod:`lingxilearn.runtime.nodes` — the node implementations that call
     ``transition_status``; none of them may call ``set_runtime_status``
     directly.
"""

from __future__ import annotations
