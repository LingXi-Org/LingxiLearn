"""Application service: packs, brains, graphs, and run execution.

Two decisions here carry most of the weight.

**Interrupts are durable thread state, never a blocking await.**  When the
graph pauses for the learner we return, persist the status, and let the pending
question be read back from the checkpoint.  An SSE connection dying — which it
will — costs nothing.

**SSE serves from the persisted event log, not from the live stream.**  The run
writes projections with a monotonic per-session sequence; the endpoint replays
from ``Last-Event-ID``.  A reconnect resumes exactly where it left off.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from lingxigraph import Command, GraphCancelledError, PostgresSaver, SqliteSaver
from lingxigraph.errors import BudgetExceededError, GraphRecursionError, GraphTimeoutError

from .brains.base import TutorBrain
from .config import Settings, get_settings
from .kernel.graph import build_graph
from .kernel.state import initial_state
from .packs.loader import discover_packs, validate_pack
from .packs.models import Pack
from .store.db import Database, Repository
from .stream.projector import EventProjector
from .tools import knowledge
from .tools.registry import ToolRegistry, load_builtin_tools

logger = logging.getLogger(__name__)

FLUSH_EVERY = 6
"""Batch size for persisting projections mid-run — small enough to feel live."""


def build_brain(settings: Settings) -> TutorBrain:
    """Pick a brain, falling back to the deterministic one when unconfigured."""
    kind = settings.effective_brain
    if kind == "openai":
        from .brains.openai_compat import OpenAICompatBrain

        return OpenAICompatBrain(settings)
    if kind == "coze":
        from .brains.coze import CozeBrain

        return CozeBrain(settings)
    from .brains.scripted import ScriptedBrain

    return ScriptedBrain()


def build_checkpointer(settings: Settings) -> Any:
    dsn = settings.resolved_checkpoint_url
    if settings.database_url.startswith("postgresql"):
        saver = PostgresSaver(dsn)
        saver.setup()
        return saver
    Path(dsn).parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(dsn)  # constructor runs setup itself


class Service:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.registry: ToolRegistry = load_builtin_tools()
        self.packs: dict[str, Pack] = {}
        self.db = Database(self.settings)
        self.repo = Repository(self.db)
        self.brain: TutorBrain | None = None
        self.checkpointer: Any = None
        self._graphs: dict[str, Any] = {}
        self._graph_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._run_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._waiters: dict[str, asyncio.Event] = defaultdict(asyncio.Event)
        self._tasks: set[asyncio.Task[Any]] = set()

    # -- lifecycle -------------------------------------------------------

    async def startup(self) -> None:
        self.packs = discover_packs(self.settings.packs_dir)
        for pack in self.packs.values():
            result = validate_pack(pack, self.registry)
            if not result.valid:
                for issue in result.issues:
                    logger.warning("pack %s: [%s] %s — %s", pack.id, issue.code, issue.path,
                                   issue.message)
        chunks = knowledge.configure(
            [p.root / "knowledge" for p in self.packs.values() if (p.root / "knowledge").exists()]
        )
        self.brain = build_brain(self.settings)
        self.checkpointer = build_checkpointer(self.settings)
        logger.info(
            "LingxiLearn ready: %d pack(s), %d knowledge chunks, brain=%s",
            len(self.packs),
            chunks,
            self.brain.name,
        )

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self.brain is not None:
            await self.brain.aclose()
        await self.db.dispose()

    # -- graphs ----------------------------------------------------------

    async def graph_for(self, pack_id: str) -> Any:
        cached = self._graphs.get(pack_id)
        if cached is not None:
            return cached
        async with self._graph_locks[pack_id]:
            cached = self._graphs.get(pack_id)  # re-check under the lock
            if cached is not None:
                return cached
            pack = self.packs.get(pack_id)
            if pack is None:
                raise KeyError(f"unknown pack: {pack_id}")
            assert self.brain is not None
            graph = build_graph(
                pack=pack,
                brain=self.brain,
                registry=self.registry,
                checkpointer=self.checkpointer,
            )
            self._graphs[pack_id] = graph
            return graph

    def config_for(self, session_id: str, pack: Pack) -> dict[str, Any]:
        # Namespacing by content version means publishing new lesson content
        # cannot reinterpret a session that is already in flight.
        return {
            "configurable": {
                "thread_id": session_id,
                "checkpoint_ns": pack.checkpoint_ns,
            },
            "recursion_limit": 80,
        }

    # -- sessions --------------------------------------------------------

    async def create_session(
        self, *, session_id: str, learner_id: str, pack_id: str, mission_id: str
    ) -> dict[str, Any]:
        pack = self.packs.get(pack_id)
        if pack is None:
            raise KeyError(f"unknown pack: {pack_id}")
        if mission_id not in pack.missions:
            raise KeyError(f"unknown mission: {mission_id}")

        await self.repo.ensure_learner(learner_id)
        known = await self.repo.mastery_for(learner_id)
        await self.repo.create_session(
            id=session_id,
            learner_id=learner_id,
            pack_id=pack.id,
            pack_version=pack.version,
            mission_id=mission_id,
            checkpoint_ns=pack.checkpoint_ns,
            status="running",
        )
        state = initial_state(
            session_id=session_id,
            learner_id=learner_id,
            pack_id=pack.id,
            pack_version=pack.version,
            mission_id=mission_id,
            mastery=known,
        )
        self._spawn(self._drive(session_id, pack, learner_id, state))
        return {"id": session_id, "mission_id": mission_id, "pack_id": pack.id, "status": "running"}

    async def answer(self, session_id: str, payload: Any) -> None:
        record = await self.repo.get_session(session_id)
        if record is None:
            raise KeyError(f"unknown session: {session_id}")
        pack = self.packs.get(record.pack_id)
        if pack is None:
            raise KeyError(f"unknown pack: {record.pack_id}")
        await self.repo.set_status(session_id, "running")
        self._spawn(
            self._drive(session_id, pack, record.learner_id, Command(resume=payload))
        )

    async def snapshot(self, session_id: str) -> dict[str, Any]:
        record = await self.repo.get_session(session_id)
        if record is None:
            raise KeyError(f"unknown session: {session_id}")
        pack = self.packs[record.pack_id]
        graph = await self.graph_for(record.pack_id)
        state = await graph.aget_state(self.config_for(session_id, pack))
        values = dict(state.values or {})
        pending = [
            {"id": str(m.id), "resumable": bool(m.resumable), "value": m.value}
            for m in (state.interrupts or ())
        ]
        mission = pack.missions.get(record.mission_id)
        return {
            "id": session_id,
            "status": record.status,
            "error": record.error,
            "pack_id": record.pack_id,
            "pack_version": record.pack_version,
            "mission": {
                "id": record.mission_id,
                "title": mission.title if mission else "",
                "subtitle": mission.subtitle if mission else "",
                "why_not_chat": mission.why_not_chat if mission else "",
                "concepts": list(mission.concepts) if mission else [],
            },
            "phase": values.get("phase", ""),
            "stage": values.get("stage", {}),
            "move": values.get("move", {}),
            "plan": values.get("plan", []),
            "step_index": values.get("step_index", 0),
            "current_step": _public_step(values.get("current_step") or {}),
            "hint_level": values.get("hint_level", 0),
            "attempts": values.get("attempts", 0),
            "answer_unlocked": values.get("answer_unlocked", False),
            "mastery": values.get("mastery", {}),
            "mastery_before": values.get("mastery_before", {}),
            "mastery_changes": values.get("mastery_changes", []),
            "misconceptions": values.get("misconceptions", []),
            "evidence": values.get("evidence", []),
            "transcript": values.get("transcript", []),
            "probe_score": values.get("probe_score", 0.0),
            "verify_score": values.get("verify_score", 0.0),
            "step_results": values.get("step_results", []),
            "report": values.get("report", {}),
            "pending": pending[0] if pending else None,
            "brain": self.brain.name if self.brain else "scripted",
        }

    # -- run execution ---------------------------------------------------

    def _spawn(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def waiter(self, session_id: str) -> asyncio.Event:
        return self._waiters[session_id]

    def _notify(self, session_id: str) -> None:
        event = self._waiters[session_id]
        event.set()
        event.clear()

    async def _drive(
        self, session_id: str, pack: Pack, learner_id: str, payload: Any
    ) -> None:
        """Run the graph to its next pause, persisting projections as it goes."""
        async with self._run_locks[session_id]:
            graph = await self.graph_for(pack.id)
            config = self.config_for(session_id, pack)
            projector = EventProjector()
            buffer: list[dict[str, Any]] = []
            status, error = "awaiting_learner", ""

            async def flush() -> None:
                if buffer:
                    await self.repo.append_events(session_id, list(buffer))
                    buffer.clear()
                    self._notify(session_id)

            try:
                async for event in graph.astream(
                    payload,
                    config,
                    stream_mode="events",
                    context={"learner_id": learner_id},
                ):
                    for emission in projector.project(event):
                        buffer.append(emission.to_dict())
                    if len(buffer) >= FLUSH_EVERY:
                        await flush()
            except GraphCancelledError:
                status, error = "cancelled", "运行已被取消。"
            except GraphTimeoutError:
                status, error = "failed", "本次运行超时了，请重试。"
            except BudgetExceededError:
                status, error = "failed", "本次运行超出了资源预算。"
            except GraphRecursionError:
                status, error = "failed", "教学流程出现异常循环，已停止。"
            except Exception as exc:  # noqa: BLE001 - surfaced to the learner
                logger.exception("run failed for session %s", session_id)
                status, error = "failed", f"运行失败：{type(exc).__name__}"
            finally:
                await flush()

            if status == "awaiting_learner":
                status = await self._finalize(session_id, pack, learner_id, config)
            await self.repo.set_status(session_id, status, error)
            if error:
                await self.repo.append_events(
                    session_id, [{"kind": "run.failed", "payload": {"message": error}}]
                )
            self._notify(session_id)

    async def _finalize(
        self, session_id: str, pack: Pack, learner_id: str, config: dict[str, Any]
    ) -> str:
        graph = await self.graph_for(pack.id)
        state = await graph.aget_state(config)
        values = dict(state.values or {})
        if state.interrupts:
            return "awaiting_learner"
        if values.get("phase") == "done":
            await self.repo.save_mastery(learner_id, dict(values.get("mastery") or {}))
            report = dict(values.get("report") or {})
            if report:
                await self.repo.save_report(
                    session_id=session_id,
                    learner_id=learner_id,
                    mission_id=str(values.get("mission_id", "")),
                    report=report,
                )
            return "done"
        return "awaiting_learner"


def _public_step(step: dict[str, Any]) -> dict[str, Any]:
    """Strip the answer key before a step ever crosses the wire."""
    return {
        k: v
        for k, v in step.items()
        if k not in {"grader", "walkthrough", "leak_guard", "hint_ladder"}
    }
