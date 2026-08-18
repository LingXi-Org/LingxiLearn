"""The constrained autonomous loop — graph definition and wiring.

    START → interpret_goal → orchestrate → dispatch → observe
          → update_state → evaluate_goal
    evaluate_goal ──(runtime_status only)──> orchestrate | await_user | END
    await_user → orchestrate

This is the only graph in the system, and it is the whole reason the routing
tables are gone.  Read the edges: not one of them names an agent, a capability,
or a subject.  They encode the *shape of a loop* — plan, act, observe, learn,
decide whether to go again — and the conditional edge branches on
``runtime_status`` alone.

This module only owns the graph's *shape*: ``LoopState``, ``LoopDeps``, edge
declaration, conditional routing, and node wiring.  The node implementations
live in :mod:`lingxilearn.runtime.nodes` (one module per phase, plus the
Interaction answer side in :mod:`lingxilearn.runtime.interactions`); the
round-exit policy is the pure function set in
:mod:`lingxilearn.runtime.evaluation`; phase transitions go through the
single lifecycle write path documented in
:mod:`lingxilearn.runtime.lifecycle`.

What runs inside ``dispatch`` is computed at run time from the learner's
profile via ``candidates`` → ``orchestrator`` → ``skill_registry``.  Adding a
capability, a skill, or a subject changes data; it never changes this file.

.. seealso::

   * :mod:`lingxilearn.runtime.lifecycle` — the canonical runtime phase
     transition API (single owner).
   * :mod:`lingxilearn.runtime.interactions` — the single Interaction-request
     owner (``request_interaction``) and the ``await_user`` node.
   * :mod:`lingxilearn.runtime.evaluation` — pure evaluation policy for
     goal/replan/completion decisions.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Annotated, Any, TypedDict

from lingxigraph import END, START, StateGraph

from ..state.session_state import (
    TERMINAL_STATUSES,
    Goal,
    GoalStack,
    IllegalTransition,
    RuntimeStatus,
    transition,
)
from ..store.runtime_state import RuntimeStateRepository
from .dispatch import DispatchDeps, Dispatcher
from .interactions import build_await_user_node
from .nodes import (
    build_dispatch_node,
    build_evaluate_goal_node,
    build_interpret_goal_node,
    build_observe_node,
    build_orchestrate_node,
    build_update_state_node,
)
from .state_updater import StateUpdater
from .trace import DecisionTracer

GRAPH_NAME = "lingxilearn-runtime-loop"
GRAPH_VERSION = "1.0.0"


def _append(left: list[Any], right: list[Any]) -> list[Any]:
    return [*left, *right]


class LoopState(TypedDict, total=False):
    """The loop's own bookkeeping. Learner state lives in the four tables."""

    learner_id: str
    task_id: str
    utterance: str
    runtime_status: str
    step: int
    goal: dict[str, Any]
    plan: dict[str, Any]
    budget: dict[str, Any]
    outcomes: Annotated[list[dict[str, Any]], _append]
    round_outcomes: list[dict[str, Any]]
    messages: Annotated[list[str], _append]
    last_decision_id: str
    replanning: bool
    user_message: dict[str, Any]
    pending_interaction: dict[str, Any] | None
    """Durable interaction awaiting an answer; drives the typed interrupt."""
    finished_reason: str
    background_pending: bool


class LoopDeps:
    """Everything the loop needs from the service, injected once per run.

    Also serves as the **canonical lifecycle transition owner** (see
    :mod:`lingxilearn.runtime.lifecycle`): graph nodes call
    :meth:`transition_status` to advance the runtime phase, which validates
    the transition, persists it to the database, and returns a graph
    checkpoint patch derived from the committed result.

    Durable work is written through the post-split Store contract —
    ``work_ledger`` and ``runtime_repository`` — never a god repository.
    """

    def __init__(
        self,
        *,
        runtime_state: RuntimeStateRepository,
        work_ledger: Any = None,
        runtime_repository: Any = None,
        learner_id: str,
        task_id: str,
        model: Any = None,
        settings: Any = None,
        artifacts: Any = None,
        registry: Any = None,
        pack: Any = None,
        execution_id: str = "",
        turn_id: str = "",
        emit: Any = None,
        confirmed_actions: frozenset[str] = frozenset(),
        prior_results: Mapping[str, Any] | None = None,
        prior_artifacts: Sequence[str] = (),
        schedule_background: Any = None,
        board_lock: asyncio.Lock | None = None,
    ) -> None:
        self.runtime_state = runtime_state
        self.work_ledger = work_ledger
        self.runtime_repository = runtime_repository
        self.learner_id = learner_id
        self.task_id = task_id
        self.model = model
        self.settings = settings
        self.artifacts = artifacts
        self.registry = registry
        self.pack = pack
        self.execution_id = execution_id
        self.turn_id = turn_id
        self.emit = emit
        self.confirmed_actions = confirmed_actions
        self.prior_results = dict(prior_results or {})
        self.prior_artifacts = tuple(prior_artifacts)
        self.schedule_background = schedule_background
        self.board_lock = board_lock
        self.updater = StateUpdater(runtime_state)
        self.tracer = DecisionTracer(
            runtime_state,
            learner_id=learner_id,
            task_id=task_id,
            execution_id=execution_id,
            emit=emit,
        )
        # Round event tracking for close_round (one entry per graph build).
        self._open_rounds: set[int] = set()
        self._closed_rounds: set[int] = set()

    # -- lifecycle (canonical transition owner) ----------------------------

    async def transition_status(
        self,
        state: LoopState,
        target: RuntimeStatus | str,
        **extra: Any,
    ) -> dict[str, Any]:
        """Validate, persist and return a graph-state patch for a phase change.

        This is the **single write path** for runtime phase transitions.
        It replaces the previous pattern where each node independently
        wrote to both the database (``set_runtime_status``) and the graph
        checkpoint (``return {"runtime_status": ...}``), risking drift
        between the two.

        The transition is validated against ``_TRANSITIONS`` (the single
        source of truth in :mod:`lingxilearn.state.session_state`), then
        persisted to the database.  The returned patch dict is derived from
        the committed result, so the graph checkpoint always reflects what
        the database confirmed.

        The *source* state for validation is read from the database (the
        canonical owner), not from the graph checkpoint ``state``.  This
        is critical when a node calls ``transition_status`` more than once:
        after the first call, the checkpoint state still carries the old
        value while the database has already advanced.

        Any additional keyword arguments are merged into the returned patch
        so callers can include related fields (``finished_reason``,
        ``budget``, etc.) in a single graph update.

        Raises :class:`~lingxilearn.state.session_state.IllegalTransition`
        if the database write fails or the session is missing, ensuring the
        graph never advances to a phase the database has not confirmed.
        """
        target_status = RuntimeStatus(str(target))
        # Use the database as the canonical source for the current phase.
        # This is essential when a node calls transition_status more than
        # once: after the first call, the graph ``state`` still carries the
        # pre-transition value while the DB has already advanced.
        snapshot = await self.runtime_state.get_session_state(self.task_id)
        if snapshot is not None:
            current = RuntimeStatus(str(snapshot.get("runtime_status") or RuntimeStatus.PLANNING))
        else:
            current = RuntimeStatus(str(state.get("runtime_status") or RuntimeStatus.PLANNING))
        canonical = transition(current, target_status)
        snapshot = await self.runtime_state.set_runtime_status(self.task_id, canonical)
        if snapshot is None:
            raise IllegalTransition(
                f"cannot transition to {canonical}: no session state found for task {self.task_id}"
            )
        patch: dict[str, Any] = {"runtime_status": str(canonical)}
        patch.update(extra)
        return patch

    # -- round event helpers -----------------------------------------------

    def open_round(self, step: int) -> None:
        """Mark a decision step as an open round for event tracking."""
        self._open_rounds.add(step)

    def close_round(
        self,
        *,
        step: int,
        decision_id: str = "",
        status: str = "",
        outcomes: Sequence[Mapping[str, Any]] = (),
        **payload: Any,
    ) -> None:
        """Emit one terminal round event, even for non-happy-path exits."""
        if self.emit is None or step not in self._open_rounds or step in self._closed_rounds:
            return
        self._closed_rounds.add(step)
        self.emit(
            "round.completed",
            {
                "step": step,
                "decision_id": decision_id or None,
                "outcomes": [dict(item) for item in outcomes],
                "runtime_status": status or None,
                **payload,
            },
        )


def route(state: LoopState) -> str:
    """The loop's only branch, and it reads one field: the run's own phase.

    No domain concept appears here. What to *do* was decided in
    ``orchestrate``; this decides only whether to go round again, wait, or
    stop.
    """

    status = RuntimeStatus(str(state.get("runtime_status") or RuntimeStatus.PLANNING))
    if status in TERMINAL_STATUSES:
        return "end"
    if status is RuntimeStatus.WAITING_FOR_USER:
        return "await_user"
    return "orchestrate"


def build_loop(deps: LoopDeps, *, checkpointer: Any = None, store: Any = None) -> Any:
    """Compile the runtime loop.

    Every node below is domain-agnostic. ``dispatch`` is the single execution
    node; it resolves capability → skill → provider per task at run time.
    The node bodies live in :mod:`lingxilearn.runtime.nodes` and
    :mod:`lingxilearn.runtime.interactions`; this function only wires them.
    """

    dispatcher = Dispatcher(
        DispatchDeps(
            runtime_state=deps.runtime_state,
            work_ledger=deps.work_ledger,
            runtime_repository=deps.runtime_repository,
            learner_id=deps.learner_id,
            task_id=deps.task_id,
            goal=Goal(goal_type="learn", topic=""),
            skills=[],
            model=deps.model,
            settings=deps.settings,
            artifacts=deps.artifacts,
            registry=deps.registry,
            pack=deps.pack,
            emit=deps.emit,
            execution_id=deps.execution_id,
            turn_id=deps.turn_id,
        )
    )
    dispatcher.seed_results(deps.prior_results)
    dispatcher.seed_artifacts(deps.prior_artifacts)
    # The service supplies one task-scoped lock shared with delivery
    # acknowledgements. Unit callers may omit it and get a local
    # lock, preserving the loop's standalone contract.
    board_lock = deps.board_lock or asyncio.Lock()

    builder = StateGraph(LoopState, name=GRAPH_NAME, version=GRAPH_VERSION)
    builder.add_node("interpret_goal", build_interpret_goal_node(deps))
    builder.add_node("orchestrate", build_orchestrate_node(deps, dispatcher=dispatcher))
    builder.add_node(
        "dispatch", build_dispatch_node(deps, dispatcher=dispatcher, board_lock=board_lock)
    )
    builder.add_node("observe", build_observe_node(deps))
    builder.add_node("update_state", build_update_state_node(deps))
    builder.add_node("evaluate_goal", build_evaluate_goal_node(deps))
    builder.add_node(
        "await_user",
        build_await_user_node(deps, dispatcher=dispatcher, checkpointer=checkpointer),
    )

    builder.add_edge(START, "interpret_goal")
    builder.add_edge("interpret_goal", "orchestrate")
    builder.add_edge("orchestrate", "dispatch")
    builder.add_edge("dispatch", "observe")
    builder.add_edge("observe", "update_state")
    builder.add_edge("update_state", "evaluate_goal")
    builder.add_conditional_edges(
        "evaluate_goal",
        route,
        {"orchestrate": "orchestrate", "await_user": "await_user", "end": END},
    )
    # With a checkpointer, await_user raises an interrupt and the run resumes
    # into the next planning round. Without one there is nothing to resume into,
    # so waiting means ending: the service starts a fresh invocation when the
    # learner replies. Falling through to orchestrate here would spin.
    builder.add_edge("await_user", "orchestrate" if checkpointer is not None else END)

    options: dict[str, Any] = {"checkpointer": checkpointer}
    if store is not None:
        options["store"] = store
    return builder.compile(**options)


def initial_state(
    *, learner_id: str, task_id: str, utterance: str, budget: Mapping[str, Any]
) -> LoopState:
    return LoopState(
        learner_id=learner_id,
        task_id=task_id,
        utterance=utterance,
        runtime_status=str(RuntimeStatus.PLANNING),
        step=0,
        goal={},
        plan={},
        budget=dict(budget),
        outcomes=[],
        round_outcomes=[],
        messages=[],
        last_decision_id="",
        replanning=False,
        user_message={"message": utterance} if utterance.strip() else {},
        pending_interaction=None,
        finished_reason="",
        background_pending=False,
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
