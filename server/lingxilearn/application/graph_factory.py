"""Compiles the runtime loop graph for conversations and agent tasks.

Pack sessions and free-form agent tasks run the same loop; this factory only
wires the per-run dependencies into ``LoopDeps``.  The composition root assigns
``agent_model`` and ``checkpointer`` at startup, before any run begins.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from ..config import Settings
from ..runtime.loop import LoopDeps, build_loop
from ..store.repositories.runtime import RuntimeRepository
from ..store.repositories.work_ledger import WorkLedgerRepository
from ..store.runtime_state import RuntimeStateRepository


class RuntimeGraphFactory:
    """Build loop graphs; owns no run state of its own."""

    def __init__(
        self,
        *,
        runtime_state: RuntimeStateRepository,
        work_ledger: WorkLedgerRepository,
        runtime_repository: RuntimeRepository,
        settings: Settings,
        artifacts: Any,
        registry: Any,
        board_locks: defaultdict[str, asyncio.Lock],
        graph_store: Any = None,
    ) -> None:
        self._runtime_state = runtime_state
        self._work_ledger = work_ledger
        self._runtime_repository = runtime_repository
        self._settings = settings
        self._artifacts = artifacts
        self._registry = registry
        self._board_locks = board_locks
        self._graph_store = graph_store
        self.agent_model: dict[str, Any] | None = None
        self.checkpointer: Any = None

    def loop_for(
        self,
        *,
        learner_id: str,
        task_id: str,
        execution_id: str = "",
        turn_id: str = "",
        emit: Any = None,
        confirmed_actions: frozenset[str] = frozenset(),
        prior_results: dict[str, Any] | None = None,
        prior_artifacts: tuple[str, ...] = (),
        pack: Any = None,
    ) -> Any:
        """Compile the runtime loop for one learner conversation.

        Pack sessions and free-form agent tasks run the same loop. A pack only
        changes the goal that seeds the stack and the tools available to
        ``pack_investigate``; it does not select a different topology, because
        there is no longer a second topology to select.
        """

        return build_loop(
            LoopDeps(
                runtime_state=self._runtime_state,
                work_ledger=self._work_ledger,
                runtime_repository=self._runtime_repository,
                learner_id=learner_id,
                task_id=task_id,
                model=self.agent_model,
                settings=self._settings,
                artifacts=self._artifacts,
                registry=self._registry,
                pack=pack,
                execution_id=execution_id,
                turn_id=turn_id,
                emit=emit,
                confirmed_actions=confirmed_actions,
                prior_results=prior_results,
                prior_artifacts=prior_artifacts,
                # Provider work is always submitted by the graph to the
                # repository-backed Work Ledger.  There is intentionally no
                # capability-specific background queue here.
                schedule_background=None,
                board_lock=self._board_locks[task_id],
            ),
            checkpointer=self.checkpointer,
            store=self._graph_store,
        )
