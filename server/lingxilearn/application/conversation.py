"""Pack-session conversation use-cases.

Owns the session (pack mission) lifecycle: creating a session, driving its
graph to the next pause, answering interrupts, and serving the persisted
session event log for SSE.  A pack session is a long-term goal on the same
runtime stack as an agent task — it is not a second kind of run.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from lingxigraph import Command
from lingxigraph.errors import (
    BudgetExceededError,
    GraphCancelledError,
    GraphRecursionError,
    GraphTimeoutError,
)

from ..config import Settings
from ..learner import LearnerService
from ..packs.models import Pack
from ..runtime.loop import initial_state as initial_loop_state
from ..state.session_state import Goal, GoalKind, RuntimeStatus, new_budget
from ..store.learner import LearnerRepository
from ..store.repositories.sessions import SessionRepository
from ..store.runtime_state import RuntimeStateRepository
from ..stream.projector import EventProjector
from .graph_factory import RuntimeGraphFactory
from .shared import BackgroundTasks, _json_safe

logger = logging.getLogger(__name__)

FLUSH_EVERY = 6
"""Batch size for persisting projections mid-run — small enough to feel live."""


class ConversationService:
    """Session commands, session snapshots and the session event stream."""

    def __init__(
        self,
        *,
        session_repository: SessionRepository,
        runtime_state: RuntimeStateRepository,
        learner_repository: LearnerRepository,
        learner_service: LearnerService,
        packs: dict[str, Pack],
        settings: Settings,
        graph_factory: RuntimeGraphFactory,
        tasks: BackgroundTasks,
    ) -> None:
        self._sessions = session_repository
        self._runtime_state = runtime_state
        self._learner_repo = learner_repository
        self._learners = learner_service
        self._packs = packs
        self._settings = settings
        self._graph_factory = graph_factory
        self._tasks = tasks
        self._waiters: dict[str, asyncio.Event] = defaultdict(asyncio.Event)
        self._run_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    # -- session queries ----------------------------------------------------

    async def get_session_record(self, session_id: str, learner_id: str) -> Any:
        return await self._sessions.get_session_for_learner(session_id, learner_id)

    async def get_report(self, session_id: str, learner_id: str) -> Any:
        return await self._sessions.get_report_for_learner(session_id, learner_id)

    async def list_sessions(self, learner_id: str) -> Any:
        return await self._sessions.list_sessions(learner_id)

    async def events_after(
        self, session_id: str, learner_id: str, after: int
    ) -> list[dict[str, Any]]:
        return await self._sessions.events_after_for_learner(session_id, learner_id, after)

    def waiter(self, session_id: str) -> asyncio.Event:
        return self._waiters[session_id]

    def _notify(self, session_id: str) -> None:
        event = self._waiters[session_id]
        event.set()
        event.clear()

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

    # -- commands -------------------------------------------------------------

    async def create_session(
        self, *, session_id: str, learner_id: str, pack_id: str, mission_id: str
    ) -> dict[str, Any]:
        pack = self._packs.get(pack_id)
        if pack is None:
            raise KeyError(f"unknown pack: {pack_id}")
        if mission_id not in pack.missions:
            raise KeyError(f"unknown mission: {mission_id}")

        await self._learner_repo.ensure_learner(learner_id)
        await self._sessions.create_session(
            id=session_id,
            learner_id=learner_id,
            pack_id=pack.id,
            pack_version=pack.version,
            mission_id=mission_id,
            checkpoint_ns=pack.checkpoint_ns,
            status="running",
        )
        mission = pack.missions[mission_id]
        await self._runtime_state.ensure_session_state(
            learner_id=learner_id,
            task_id=session_id,
            session_id=session_id,
            budget=new_budget(),
        )
        # A pack session is a long-term goal on the same stack, not a second
        # kind of run. Its concepts become the knowledge points the runtime
        # ranks over, so a learner already strong in one of them is not made to
        # sit through it.
        stack = await self._runtime_state.goal_stack(session_id)
        operation = stack.push(
            Goal(
                goal_type="learn",
                topic=mission.title or mission_id,
                kind=GoalKind.LONG_TERM,
                knowledge_points=tuple(mission.concepts),
                expected_outcome=mission.subtitle or "",
                created_by="pack",
                raw_utterance=mission.title or mission_id,
            ),
            reason=f"课程包任务：{pack.id}/{mission_id}",
        )
        await self._runtime_state.apply_stack_operation(session_id, operation)
        self._tasks.spawn(self._drive(session_id, pack, learner_id, None))
        return {"id": session_id, "mission_id": mission_id, "pack_id": pack.id, "status": "running"}

    async def answer(self, session_id: str, payload: Any, learner_id: str | None = None) -> None:
        record = (
            await self._sessions.get_session_for_learner(session_id, learner_id)
            if learner_id is not None
            else await self._sessions.get_session(session_id)
        )
        if record is None:
            raise KeyError(f"unknown session: {session_id}")
        pack = self._packs.get(record.pack_id)
        if pack is None:
            raise KeyError(f"unknown pack: {record.pack_id}")
        await self._sessions.set_status(session_id, "running")
        self._tasks.spawn(self._drive(session_id, pack, record.learner_id, Command(resume=payload)))

    async def snapshot(self, session_id: str, learner_id: str | None = None) -> dict[str, Any]:
        record = (
            await self._sessions.get_session_for_learner(session_id, learner_id)
            if learner_id is not None
            else await self._sessions.get_session(session_id)
        )
        if record is None:
            raise KeyError(f"unknown session: {session_id}")
        pack = self._packs[record.pack_id]
        session_state = await self._runtime_state.get_session_state(session_id) or {}
        stack = await self._runtime_state.goal_stack(session_id)
        current_goal = stack.current()
        decisions = await self._runtime_state.decisions_for_task(session_id)
        profile = await self._runtime_state.profile_for(record.learner_id)
        pending = [
            {"id": item.get("id"), "resumable": True, "value": item}
            for item in ((session_state.get("plan") or {}).get("pending") or [])
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
            "runtime_status": session_state.get("runtime_status", ""),
            "goal": current_goal.to_dict() if current_goal else {},
            "goal_stack": list(session_state.get("goal_stack") or []),
            "plan": dict(session_state.get("plan") or {}),
            "budget": dict(session_state.get("budget") or {}),
            "profile": profile,
            "decisions": decisions,
            "interrupts": pending,
        }

    # -- session run engine ---------------------------------------------------

    async def _drive(self, session_id: str, pack: Pack, learner_id: str, payload: Any) -> None:
        """Run the loop to its next pause, persisting projections as it goes."""

        async with self._run_locks[session_id]:
            buffer: list[dict[str, Any]] = []

            async def flush() -> None:
                if buffer:
                    await self._sessions.append_events(session_id, list(buffer))
                    buffer.clear()
                    self._notify(session_id)

            def emit_runtime_event(kind: str, event_payload: dict[str, Any]) -> None:
                buffer.append(
                    {
                        "kind": kind,
                        "payload": _json_safe(event_payload),
                        "node": str(event_payload.get("capability") or ""),
                    }
                )

            session_state = await self._runtime_state.ensure_session_state(
                learner_id=learner_id, task_id=session_id, session_id=session_id
            )
            graph = self._graph_factory.loop_for(
                learner_id=learner_id,
                task_id=session_id,
                emit=emit_runtime_event,
                pack=pack,
            )
            config = {
                "configurable": {
                    "thread_id": session_id,
                    "checkpoint_ns": pack.checkpoint_ns,
                },
                "recursion_limit": 80,
            }
            projector = EventProjector()
            status, error = "awaiting_learner", ""
            graph_input: Any = (
                payload
                if payload is not None
                else initial_loop_state(
                    learner_id=learner_id,
                    task_id=session_id,
                    utterance="",
                    budget=session_state.get("budget") or new_budget(),
                )
            )

            try:
                async for event in graph.astream(
                    graph_input,
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

            latest = await self._runtime_state.get_session_state(session_id) or {}
            runtime_status = str(latest.get("runtime_status") or RuntimeStatus.PLANNING)
            if status == "awaiting_learner":
                status = await self._finalize(session_id, pack, learner_id, runtime_status)
            elif status in {"failed", "cancelled"}:
                await self._finalize(
                    session_id, pack, learner_id, runtime_status, outcome_override="failed"
                )
            await self._sessions.set_status(session_id, status, error)
            if error:
                await self._sessions.append_events(
                    session_id, [{"kind": "run.failed", "payload": {"message": error}}]
                )
            self._notify(session_id)

    async def _finalize(
        self,
        session_id: str,
        pack: Pack,
        learner_id: str,
        runtime_status: str,
        outcome_override: str | None = None,
    ) -> str:
        """Record the session outcome from the profile the run actually changed."""

        if outcome_override is None and runtime_status not in {
            str(RuntimeStatus.COMPLETED),
            str(RuntimeStatus.FAILED),
        }:
            return "awaiting_learner"

        completed = outcome_override is None and runtime_status == str(RuntimeStatus.COMPLETED)
        rows = await self._runtime_state.profile_for(learner_id)
        mastery = {str(row["knowledge_point_id"]): float(row.get("mastery") or 0.0) for row in rows}
        misconceptions = sorted(
            {
                str(tag)
                for row in rows
                for tag in ((row.get("system") or {}).get("misconceptions") or [])
            }
        )
        evidence = await self._runtime_state.evidence_for_task(session_id)
        decisions = await self._runtime_state.decisions_for_task(session_id)
        report = {
            "session_id": session_id,
            "pack_id": pack.id,
            "decisions": len(decisions),
            "mastery": mastery,
            "misconceptions": misconceptions,
        }

        try:
            context = await self._learners.context_for_learner_id(learner_id)
        except LookupError:
            # Anonymous records created before the identity boundary remain
            # readable only to legacy internal tooling and are never mapped
            # automatically to a new Identity user.
            if completed:
                await self._learner_repo.save_mastery(learner_id, mastery)
                await self._sessions.save_report(
                    session_id=session_id,
                    learner_id=learner_id,
                    mission_id="",
                    report=report,
                )
                return "done"
            return "failed"

        session_record = await self._sessions.get_session(session_id)
        await self._learners.record_session_outcome(
            context,
            session_id=session_id,
            outcome="completed" if completed else "failed",
            evidence=[
                {
                    "id": row.get("evidence_id"),
                    "kind": row.get("kind"),
                    "source": row.get("source"),
                    "summary": row.get("summary"),
                    "locator": row.get("locator") or {},
                    "value": row.get("value"),
                }
                for row in evidence
            ],
            misconceptions=misconceptions,
            mastery=mastery,
            report=report,
            mission_id=str(session_record.mission_id if session_record is not None else ""),
        )
        return "done" if completed else "failed"
