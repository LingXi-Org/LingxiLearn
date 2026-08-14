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
import base64
import inspect
import json
import logging
import mimetypes
import secrets
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lingxigraph import Command, EventKind, GraphCancelledError, PostgresSaver, SqliteSaver
from lingxigraph.errors import (
    BudgetExceededError,
    GraphRecursionError,
    GraphTimeoutError,
)
from sqlalchemy import select

from .agents.artifact_store import ArtifactError, ArtifactStore
from .agents.contracts import quiz_public
from .agents.model_runtime import EVENT_CHANNEL, model_roles
from .agents.providers import load_all as load_providers
from .agents.providers import missing_providers
from .brains.base import TutorBrain
from .config import REPO_ROOT, Settings, get_settings
from .learner import LearnerService
from .packs.loader import discover_packs, validate_pack
from .packs.models import Pack
from .runtime.contracts import Cost, DoneCondition, PlannedTask
from .runtime.dispatch import DispatchDeps, Dispatcher
from .runtime.guardrails import Budget
from .runtime.loop import GRAPH_NAME as LOOP_GRAPH_NAME
from .runtime.loop import GRAPH_VERSION as LOOP_GRAPH_VERSION
from .runtime.loop import LoopDeps, build_loop
from .runtime.loop import initial_state as initial_loop_state
from .runtime.schedules import next_schedule_time, validate_schedule
from .runtime.sim_semantics import PrimitiveCatalog, SimRunProjector
from .state.capabilities import UnknownCapability
from .state.capabilities import info as capability_details
from .state.session_state import Goal, GoalKind, RuntimeStatus, new_budget
from .state.skill_catalog import discover as discover_skill_manifests
from .store.db import Database, Repository
from .store.learner import LearnerRepository
from .store.models import (
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeGraph,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    Workspace,
    WorkspaceFile,
)
from .store.runtime_state import RuntimeStateRepository
from .stream.projector import EventProjector
from .tools import knowledge
from .tools.registry import ToolRegistry, load_builtin_tools

logger = logging.getLogger(__name__)

FLUSH_EVERY = 6
AGENT_FLUSH_EVERY = 4
"""Batch size for persisting projections mid-run — small enough to feel live."""

_AGENT_FORCE_FLUSH = frozenset(
    {
        "agent.started",
        "agent.completed",
        "agent.failed",
        "model.started",
        "model.completed",
        "tool.call.delta",
        "tool.result",
        "artifact.ready",
    }
)

_LOOP_NODES = frozenset(
    {"interpret_goal", "orchestrate", "dispatch", "observe", "update_state",
     "evaluate_goal", "await_user"}
)
"""The runtime loop's own nodes. Which *agent* ran is not derived from these.

Providers announce themselves on the event channel, so attribution follows the
run rather than a table of agent names that would have to be edited every time a
capability is added.
"""


def _normalize_attachment_refs(
    value: list[dict[str, Any]] | None, learner_id: str
) -> list[dict[str, Any]]:
    """Keep only the metadata needed to let agents retrieve uploaded files."""

    refs: list[dict[str, Any]] = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        filename = str(item.get("filename") or "").strip()
        if not key or not filename or not key.startswith(f"{learner_id}/"):
            continue
        try:
            size = max(0, int(item.get("size") or 0))
        except (TypeError, ValueError):
            size = 0
        refs.append(
            {
                "key": key[:512],
                "path": f"/api/attachments/{key[:512]}",
                "filename": filename[:255],
                "media_type": str(item.get("media_type") or "application/octet-stream")[:128],
                "size": size,
            }
        )
    return refs[:10]


def _prompt_with_attachments(prompt: str, attachments: list[dict[str, Any]]) -> str:
    if not attachments:
        return prompt
    lines = ["\n\n[已上传附件]"]
    lines.extend(
        f"- {item['filename']} ({item['media_type']}, {item['path'] or item['key']})"
        for item in attachments
    )
    return prompt + "\n".join(lines)


def _trace_agent(metadata: Any, default_agent: str = "coordinator") -> str:
    """Attribute a streamed message to whichever agent is currently running.

    LingxiGraph namespaces child-agent events under the agent's own name, so the
    namespace is the attribution; there is no list of known agents to check
    against.
    """

    if not isinstance(metadata, dict):
        return default_agent
    namespace = metadata.get("namespace") or ()
    if isinstance(namespace, (list, tuple)):
        for value in reversed(namespace):
            name = str(value)
            if name and name not in _LOOP_NODES:
                return name
    for key in ("agent", "name"):
        value = metadata.get(key)
        if value and str(value) not in _LOOP_NODES:
            return str(value)
    return default_agent


def _message_trace_events(value: Any, default_agent: str) -> list[dict[str, Any]]:
    """Convert one native LingxiGraph message envelope into Agent Task events."""
    if not isinstance(value, (tuple, list)) or not value:
        return []
    message = value[0]
    metadata = value[1] if len(value) > 1 else {}
    agent = _trace_agent(metadata, default_agent)
    events: list[dict[str, Any]] = []
    message_type = str(getattr(message, "type", "") or "")
    content = getattr(message, "content", "")
    if message_type == "tool":
        events.append(
            {
                "kind": "tool.result",
                "agent": agent,
                "payload": {
                    "tool_call_id": getattr(message, "tool_call_id", None),
                    "name": getattr(message, "name", None),
                    "content": str(content or ""),
                    "status": getattr(message, "status", None),
                    "additional_kwargs": _json_safe(
                        getattr(message, "additional_kwargs", {}) or {}
                    ),
                    "response_metadata": _json_safe(
                        getattr(message, "response_metadata", {}) or {}
                    ),
                },
            }
        )
        return events
    additional = getattr(message, "additional_kwargs", {}) or {}
    reasoning = ""
    if isinstance(additional, dict):
        for key in ("reasoning_content", "reasoning", "thinking"):
            candidate = additional.get(key)
            if candidate:
                reasoning = str(candidate)
                break
    if reasoning and not additional.get("_reasoning_replay"):
        events.append(
            {
                "kind": "reasoning.delta",
                "agent": agent,
                "payload": {
                    "delta": reasoning,
                    "debug": _json_safe(additional),
                    "response_metadata": _json_safe(
                        getattr(message, "response_metadata", {}) or {}
                    ),
                },
            }
        )
    if content:
        events.append(
            {"kind": "assistant.delta", "agent": agent, "payload": {"delta": str(content)}}
        )
    tool_chunks = getattr(message, "tool_call_chunks", ()) or ()
    if tool_chunks:
        events.append(
            {
                "kind": "tool.call.delta",
                "agent": agent,
                "payload": {
                    "chunks": [
                        {
                            "name": getattr(chunk, "name", None),
                            "args": getattr(chunk, "args", ""),
                            "id": getattr(chunk, "id", None),
                            "index": getattr(chunk, "index", 0),
                        }
                        for chunk in tool_chunks
                    ],
                    "debug": _json_safe(additional),
                    "response_metadata": _json_safe(
                        getattr(message, "response_metadata", {}) or {}
                    ),
                },
            }
        )
    usage = getattr(message, "usage", {}) or {}
    if usage:
        events.append({"kind": "model.usage", "agent": agent, "payload": {"usage": dict(usage)}})
    for event in events:
        event["runtime"] = {
            "run_id": _json_safe(metadata.get("run_id")) if isinstance(metadata, dict) else None,
            "step": _json_safe(metadata.get("step")) if isinstance(metadata, dict) else None,
            "node": _json_safe(metadata.get("node")) if isinstance(metadata, dict) else None,
            "task_id": _json_safe(metadata.get("task_id")) if isinstance(metadata, dict) else None,
            "namespace": _json_safe(metadata.get("namespace"))
            if isinstance(metadata, dict)
            else None,
            "checkpoint_id": _json_safe(metadata.get("checkpoint_id"))
            if isinstance(metadata, dict)
            else None,
            "span_id": _json_safe(metadata.get("span_id")) if isinstance(metadata, dict) else None,
        }
        logger.debug(
            "agent trace task=%s agent=%s kind=%s payload=%s",
            metadata.get("task_id", ""),
            agent,
            event["kind"],
            event["payload"],
        )
    return events


def _safe_agent_error(exc: BaseException, settings: Settings) -> str:
    """Expose actionable workflow errors without leaking credentials."""

    detail = str(exc).strip() or type(exc).__name__
    secret = settings.agent_api_key.get_secret_value()
    if secret:
        detail = detail.replace(secret, "[redacted]")
    return detail[-4000:]


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
    def __init__(self, settings: Settings | None = None, graph_store: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self.registry: ToolRegistry = load_builtin_tools()
        self.packs: dict[str, Pack] = {}
        self.db = Database(self.settings)
        self.repo = Repository(self.db)
        self.learner_repository = LearnerRepository(self.db)
        self.runtime_state = RuntimeStateRepository(self.db)
        self.learner_service = LearnerService(self.learner_repository, self.settings)
        self.learners = self.learner_service
        self.brain: TutorBrain | None = None
        self.agent_model: dict[str, Any] | None = None
        self.agent_artifacts = ArtifactStore(self.settings)
        self.checkpointer: Any = None
        # Optional LingxiGraph runtime Store/Memory seam.  Canonical learner
        # data remains in LearnerRepository regardless of whether a host wires
        # this runtime capability in.
        self.graph_store = graph_store
        self._graphs: dict[str, Any] = {}
        self._graph_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._run_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._waiters: dict[str, asyncio.Event] = defaultdict(asyncio.Event)
        self._agent_waiters: dict[str, asyncio.Event] = defaultdict(asyncio.Event)
        self._tasks: set[asyncio.Task[Any]] = set()
        self._workspace_projection_lock = asyncio.Lock()
        self._agent_slots = asyncio.Semaphore(max(1, self.settings.agent_concurrency))
        self._sidecar_slots = asyncio.Semaphore(max(1, self.settings.agent_sidecar_concurrency))

    # -- lifecycle -------------------------------------------------------

    async def startup(self) -> None:
        self.packs = discover_packs(self.settings.packs_dir)
        for pack in self.packs.values():
            result = validate_pack(pack, self.registry)
            if not result.valid:
                for issue in result.issues:
                    logger.warning(
                        "pack %s: [%s] %s — %s", pack.id, issue.code, issue.path, issue.message
                    )
        # Keep the primitive projection closed: adding a callable LingxiLearn
        # tool without a Sim mapping is a startup error, never a generic node.
        PrimitiveCatalog().validate(self.registry.names())
        # Seed the capability registry from the SKILL.md manifests on disk, so
        # the orchestrator plans against declared capabilities rather than a
        # hard-coded agent list.
        manifests = discover_skill_manifests(REPO_ROOT / "skills")
        await self.runtime_state.sync_skill_manifests(manifests)
        load_providers()
        gaps = missing_providers([manifest.to_row() for manifest in manifests])
        if gaps:
            # A capability the orchestrator can plan for but nobody can run is a
            # dead end at run time; surface it at startup instead.
            logger.warning("skills naming an unimplemented provider: %s", ", ".join(gaps))
        chunks = knowledge.configure(
            [p.root / "knowledge" for p in self.packs.values() if (p.root / "knowledge").exists()]
        )
        self.brain = build_brain(self.settings)
        if self.settings.agents_configured:
            from .brains.traced_openai_compat import TracedOpenAICompatChatModel

            model_options = {
                "base_url": self.settings.agent_base_url,
                "api_key": self.settings.agent_api_key.get_secret_value(),
                "timeout": self.settings.agent_timeout,
                # Keep one shared low-latency default so every current and
                # future specialist avoids expensive hidden reasoning.
                "default_options": {
                    # Keep Agent tool loops responsive.  The UI still renders
                    # provider reasoning when a provider sends it, but normal
                    # orchestration requests do not spend tokens on CoT.
                    "thinking": {"type": "disabled"},
                    "reasoning_effort": "low",
                },
                "cache_first": {
                    "enabled": self.settings.agent_cache_enabled,
                    "verify_mode": self.settings.agent_cache_verify_mode,
                },
            }
            # Each specialist has a different immutable system prompt and tool
            # catalog. Keeping one model instance per role makes the cache
            # prefix stable across tasks and avoids cross-agent drift errors.
            # Derive the roles from what actually asks for a model. The
            # previous hand-written list drifted the moment a provider was
            # added, leaving eleven roles resolving to None in production while
            # every test passed a fake model directly.
            self.agent_model = {
                role: TracedOpenAICompatChatModel(self.settings.agent_model, **model_options)
                # One instance per role: each has a different immutable system
                # prompt and tool catalog, and sharing one would break the
                # provider's prompt-cache prefix.
                for role in model_roles()
            }
        self.checkpointer = build_checkpointer(self.settings)
        # Sidecars are durable. A process restart must never strand a running
        # proposal; queue it again and let the normal worker claim it.
        for sidecar in await self.repo.queued_agent_sidecars():
            if sidecar["status"] == "running":
                await self.repo.finish_agent_sidecar(sidecar["id"], status="queued")
            self._spawn(self._run_capability_sidecar(sidecar["id"]))
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
        for model in (self.agent_model or {}).values():
            closer = getattr(model, "aclose", None)
            if callable(closer):
                await closer()
        if self.checkpointer is not None:
            closer = getattr(self.checkpointer, "close", None)
            if callable(closer):
                result = closer()
                if inspect.isawaitable(result):
                    await result
        await self.db.dispose()

    # -- graphs ----------------------------------------------------------

    def loop_for(
        self,
        *,
        learner_id: str,
        task_id: str,
        execution_id: str = "",
        emit: Any = None,
        confirmed_actions: frozenset[str] = frozenset(),
        prior_results: dict[str, Any] | None = None,
        prior_artifacts: tuple[str, ...] = (),
        pack: Pack | None = None,
    ) -> Any:
        """Compile the runtime loop for one learner conversation.

        Pack sessions and free-form agent tasks run the same loop. A pack only
        changes the goal that seeds the stack and the tools available to
        ``pack_investigate``; it does not select a different topology, because
        there is no longer a second topology to select.
        """

        return build_loop(
            LoopDeps(
                runtime_state=self.runtime_state,
                learner_id=learner_id,
                task_id=task_id,
                model=self.agent_model,
                settings=self.settings,
                artifacts=self.agent_artifacts,
                registry=self.registry,
                pack=pack,
                execution_id=execution_id,
                emit=emit,
                confirmed_actions=confirmed_actions,
                prior_results=prior_results,
                prior_artifacts=prior_artifacts,
            ),
            checkpointer=self.checkpointer,
            store=self.graph_store,
        )

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
        await self.repo.create_session(
            id=session_id,
            learner_id=learner_id,
            pack_id=pack.id,
            pack_version=pack.version,
            mission_id=mission_id,
            checkpoint_ns=pack.checkpoint_ns,
            status="running",
        )
        mission = pack.missions[mission_id]
        await self.runtime_state.ensure_session_state(
            learner_id=learner_id,
            task_id=session_id,
            session_id=session_id,
            budget=new_budget(),
        )
        # A pack session is a long-term goal on the same stack, not a second
        # kind of run. Its concepts become the knowledge points the runtime
        # ranks over, so a learner already strong in one of them is not made to
        # sit through it.
        stack = await self.runtime_state.goal_stack(session_id)
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
        await self.runtime_state.apply_stack_operation(session_id, operation)
        self._spawn(self._drive(session_id, pack, learner_id, None))
        return {"id": session_id, "mission_id": mission_id, "pack_id": pack.id, "status": "running"}

    # -- Agent Tasks ------------------------------------------------------

    async def create_agent_task(
        self,
        *,
        task_id: str,
        learner_id: str,
        prompt: str,
        attachments: list[dict[str, Any]] | None = None,
        resources: list[dict[str, Any]] | None = None,
        schedule_id: str | None = None,
        scheduled_for: datetime | None = None,
        graph_version: str = f"{LOOP_GRAPH_NAME}@{LOOP_GRAPH_VERSION}",
    ) -> dict[str, Any]:
        normalized = " ".join(prompt.strip().split())
        if not normalized:
            raise ValueError("prompt must not be empty")
        if len(normalized) > 4000:
            raise ValueError("prompt is too long")
        attachment_refs = _normalize_attachment_refs(attachments, learner_id)
        await self.repo.ensure_learner(learner_id)
        await self.repo.create_agent_task(
            id=task_id,
            learner_id=learner_id,
            prompt=normalized,
            graph_version=graph_version,
            status="queued",
            resources=resources or [],
            intent={},
            lecture_result={},
            deck_result={},
            quiz_result={},
            adaptive_result={},
            handoff_result={},
            user_messages=[],
            visual_result={},
        )
        await self.repo.append_agent_events(
            task_id,
            [{"kind": "task.started", "agent": "coordinator", "payload": {"status": "queued"}}],
        )
        if self.agent_model is None:
            message = "DS_API_KEY is not configured"
            await self.repo.set_agent_task_status(task_id, "failed", message)
            await self.repo.append_agent_events(
                task_id,
                [{"kind": "task.failed", "agent": "coordinator", "payload": {"message": message}}],
            )
            return {"id": task_id, "status": "failed", "error": message}
        self._spawn(
            self._drive_agent_task(
                task_id,
                learner_id,
                _prompt_with_attachments(normalized, attachment_refs),
                schedule_id=schedule_id,
                scheduled_for=scheduled_for,
            )
        )
        return {"id": task_id, "status": "queued"}

    async def propose_schedule(
        self,
        *,
        learner_id: str,
        prompt: str,
        cron: str,
        timezone: str = "UTC",
        resources: list[dict[str, Any]] | None = None,
        source_task_id: str | None = None,
        graph_version: str = f"{LOOP_GRAPH_NAME}@{LOOP_GRAPH_VERSION}",
    ) -> dict[str, Any]:
        """Create a pending Agent proposal; only the native Sim card can approve it."""

        expression, zone = validate_schedule(cron, timezone)
        now = datetime.now(UTC)
        proposal_id = f"schedule-proposal-{uuid.uuid4().hex}"
        row = await self.repo.create_schedule_proposal(
            id=f"schedule-{uuid.uuid4().hex}",
            proposal_id=proposal_id,
            learner_id=learner_id,
            source_task_id=source_task_id,
            prompt=" ".join(prompt.split()),
            cron=expression,
            timezone=zone,
            inputs_snapshot={"prompt": prompt, "createdAt": now.isoformat()},
            resources_snapshot=list(resources or []),
            graph_version=graph_version,
            status="proposed",
            next_run_at=next_schedule_time(expression, zone, now),
        )
        if source_task_id:
            await self.repo.append_agent_events(
                source_task_id,
                [
                    {
                        "kind": "schedule.proposed",
                        "agent": "coordinator",
                        "payload": {
                            "proposalId": proposal_id,
                            "toolCallId": proposal_id,
                            "toolName": "schedule.propose",
                            "cron": expression,
                            "timezone": zone,
                            "permissionDecision": "pending",
                        },
                    }
                ],
            )
            self._notify_agent(source_task_id)
        return {
            "proposalId": row.proposal_id,
            "scheduleId": row.id,
            "status": row.status,
            "cron": row.cron,
            "timezone": row.timezone,
            "nextRunAt": row.next_run_at.isoformat() if row.next_run_at else None,
        }

    async def propose_schedule_revocation(
        self, *, learner_id: str, schedule_id: str
    ) -> dict[str, Any]:
        schedule = await self.repo.get_schedule(schedule_id=schedule_id, learner_id=learner_id)
        if schedule is None:
            raise KeyError(schedule_id)
        proposal_id = f"schedule-revoke-proposal-{uuid.uuid4().hex}"
        row = await self.repo.create_schedule_proposal(
            id=f"schedule-{uuid.uuid4().hex}",
            proposal_id=proposal_id,
            learner_id=learner_id,
            source_task_id=schedule.source_task_id,
            prompt=f"撤销计划：{schedule.prompt}",
            cron=schedule.cron,
            timezone=schedule.timezone,
            inputs_snapshot={"revokesScheduleId": schedule.id},
            resources_snapshot=schedule.resources_snapshot or [],
            graph_version=schedule.graph_version,
            status="proposed",
            next_run_at=schedule.next_run_at,
            revision=int(schedule.revision or 1) + 1,
        )
        if schedule.source_task_id:
            await self.repo.append_agent_events(
                schedule.source_task_id,
                [
                    {
                        "kind": "schedule.proposed",
                        "agent": "coordinator",
                        "payload": {
                            "proposalId": proposal_id,
                            "toolCallId": proposal_id,
                            "toolName": "schedule.revoke",
                            "revokesScheduleId": schedule.id,
                            "permissionDecision": "pending",
                        },
                    }
                ],
            )
            self._notify_agent(schedule.source_task_id)
        return {
            "proposalId": row.proposal_id,
            "scheduleId": row.id,
            "revokesScheduleId": schedule.id,
            "status": row.status,
        }

    async def agent_task_snapshot(
        self, task_id: str, learner_id: str | None = None
    ) -> dict[str, Any]:
        record = (
            await self.repo.get_agent_task_for_learner(task_id, learner_id)
            if learner_id is not None
            else await self.repo.get_agent_task(task_id)
        )
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        executions = await self.repo.list_agent_executions(record.id, record.learner_id)
        session_state = await self.runtime_state.get_session_state(record.id) or {}
        stack = await self.runtime_state.goal_stack(record.id)
        current_goal = stack.current()
        decisions = await self.runtime_state.decisions_for_task(record.id)
        sidecars = await self.repo.list_agent_sidecars(record.id, record.learner_id)
        return {
            "id": record.id,
            "status": record.status,
            "prompt": record.prompt,
            "title": record.title or "",
            "is_pinned": bool(record.is_pinned),
            "is_unread": bool(record.is_unread),
            "deleted_at": record.deleted_at.isoformat() if record.deleted_at else None,
            "resources": record.resources or [],
            "graph_version": record.graph_version,
            "current_execution_id": record.current_execution_id,
            "latest_execution_id": record.latest_execution_id,
            "executions": [
                {
                    "id": item.id,
                    "status": item.status,
                    "trigger": item.trigger,
                    "graph_version": item.graph_version,
                    "started_at": item.started_at.isoformat() if item.started_at else None,
                    "ended_at": item.ended_at.isoformat() if item.ended_at else None,
                }
                for item in executions
            ],
            "goal": current_goal.to_dict() if current_goal else {},
            "goal_stack": list(session_state.get("goal_stack") or []),
            "runtime_status": session_state.get("runtime_status", ""),
            "plan": dict(session_state.get("plan") or {}),
            "budget": dict(session_state.get("budget") or {}),
            # Which agents ran is a fact about this run, read from the decision
            # trace and the registry. There is no fixed roster to enumerate.
            "agents": _agents_from_trace(decisions, sidecars),
            "decisions": decisions,
            "artifacts": self._artifact_snapshot(record),
            "quiz_submission": await _submission_snapshot(self.repo, record.id),
            "error": record.error,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    async def list_agent_tasks(
        self, learner_id: str, *, scope: str = "active"
    ) -> list[dict[str, Any]]:
        return await self.repo.list_agent_tasks(learner_id, scope=scope)

    async def agent_execution_snapshot(self, execution_id: str, learner_id: str) -> dict[str, Any]:
        row = await self.repo.get_agent_execution(execution_id, learner_id)
        if row is None:
            raise KeyError(f"unknown execution: {execution_id}")
        started = row.started_at
        ended = row.ended_at
        duration = int((ended - started).total_seconds() * 1000) if ended and started else None
        return {
            "executionId": row.id,
            "workflowId": "lingxi-agent",
            "workflowName": "LingxiGraph · Sim runtime",
            "status": row.status,
            "taskId": row.task_id,
            "graphVersion": row.graph_version,
            "projectionVersion": (row.workflow_state or {}).get("version", "sim-runtime.v1"),
            "workflowState": row.workflow_state or {},
            "traceSpans": row.trace_spans or [],
            "executionMetadata": {
                "trigger": row.trigger,
                "startedAt": started.isoformat() if started else None,
                "endedAt": ended.isoformat() if ended else None,
                "totalDurationMs": duration,
                "cost": None,
                "totalTokens": None,
                "scheduleId": row.schedule_id,
                "scheduledFor": row.scheduled_for.isoformat() if row.scheduled_for else None,
            },
        }

    async def update_agent_task(
        self,
        task_id: str,
        learner_id: str,
        *,
        title: str | None = None,
        is_pinned: bool | None = None,
        is_unread: bool | None = None,
        resources: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if title is not None:
            title = " ".join(title.strip().split())
            if not title:
                raise ValueError("title must not be empty")
        if resources is not None and len(resources) > 100:
            raise ValueError("too many resources")
        row = await self.repo.update_agent_task_metadata(
            task_id,
            learner_id,
            title=title,
            is_pinned=is_pinned,
            is_unread=is_unread,
            resources=resources,
        )
        if row is None:
            raise KeyError(f"unknown agent task: {task_id}")
        return {
            "id": row.id,
            "title": row.title,
            "is_pinned": row.is_pinned,
            "is_unread": row.is_unread,
            "resources": row.resources or [],
        }

    async def delete_agent_task(self, task_id: str, learner_id: str) -> dict[str, Any]:
        row = await self.repo.set_agent_task_deleted(task_id, learner_id, True)
        if row is None:
            raise KeyError(f"unknown agent task: {task_id}")
        return {"id": row.id, "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None}

    async def restore_agent_task(self, task_id: str, learner_id: str) -> dict[str, Any]:
        row = await self.repo.set_agent_task_deleted(task_id, learner_id, False)
        if row is None:
            raise KeyError(f"unknown agent task: {task_id}")
        return {"id": row.id, "deleted_at": None}

    async def fork_agent_task(self, task_id: str, learner_id: str) -> dict[str, Any]:
        source = await self.repo.get_agent_task_for_learner(task_id, learner_id)
        if source is None:
            raise KeyError(f"unknown agent task: {task_id}")
        new_id = f"t-{uuid.uuid4().hex[:20]}"
        result = await self.create_agent_task(
            task_id=new_id,
            learner_id=learner_id,
            prompt=source.prompt,
            resources=list(source.resources or []),
        )
        await self.repo.update_agent_task_metadata(new_id, learner_id, title=source.title)
        return result

    async def project_agent_artifacts(self, learner_id: str, task_id: str | None = None) -> int:
        """Project completed LingxiGraph artifacts into read-only Workspace Files.

        The graph keeps its original audit files under ``agent_task_dir``. A
        second immutable copy in the learner workspace gives native Files a
        stable resource identity without making the graph output editable or
        coupling file deletion to task-audit retention.
        """

        async with self._workspace_projection_lock:
            async with self.db.session() as session:
                workspace = await session.scalar(
                    select(Workspace).where(Workspace.learner_id == learner_id)
                )
                if workspace is None:
                    workspace = Workspace(
                        id=f"ws_{secrets.token_urlsafe(18)}",
                        learner_id=learner_id,
                        name="灵犀智学",
                        appearance={},
                    )
                    session.add(workspace)
                    await session.flush()

                tasks = []
                for scope in ("active", "archived"):
                    for item in await self.repo.list_agent_tasks(learner_id, scope=scope):
                        if task_id is None or item["id"] == task_id:
                            tasks.append(item)
                projected = 0
                for task in tasks:
                    task_key = str(task["id"])
                    title = str(
                        task.get("title") or task.get("intent", {}).get("topic") or task_key
                    )
                    candidates = (
                        (self.agent_artifacts.lesson_intro_path(task_key), "lesson-intro.html"),
                        (self.agent_artifacts.deck_path(task_key), "lecture.html"),
                        (self.agent_artifacts.html_path(task_key), "visual-explainer.html"),
                    )
                    for source, filename in candidates:
                        if not source.is_file():
                            continue
                        path = f"学习产物/{task_key}/{filename}"
                        existing = await session.scalar(
                            select(WorkspaceFile).where(
                                WorkspaceFile.workspace_id == workspace.id,
                                WorkspaceFile.path == path,
                            )
                        )
                        if existing is not None:
                            continue
                        raw = source.read_bytes()
                        storage_key = f"{learner_id}/{secrets.token_urlsafe(24)}"
                        target_root = self.settings.var_dir / "workspaces" / learner_id
                        target_root.mkdir(parents=True, exist_ok=True)
                        target = target_root / storage_key.split("/", 1)[1]
                        target.write_bytes(raw)
                        session.add(
                            WorkspaceFile(
                                id=f"file_{uuid.uuid4().hex}",
                                workspace_id=workspace.id,
                                name=filename,
                                mime_type=mimetypes.guess_type(filename)[0]
                                or "application/octet-stream",
                                size=len(raw),
                                storage_key=storage_key,
                                path=path,
                                metadata_payload={
                                    "source": "lingxigraph",
                                    "taskId": task_key,
                                    "taskTitle": title,
                                    "readOnly": True,
                                },
                            )
                        )
                        projected += 1
                # Knowledge graphs are durable LingxiGraph sidecars, not
                # editable workflow canvases. Mirror each revision as a
                # searchable JSON document in a private read-only base.
                graphs = (
                    (
                        await session.execute(
                            select(KnowledgeGraph).where(KnowledgeGraph.learner_id == learner_id)
                        )
                    )
                    .scalars()
                    .all()
                )
                if graphs:
                    graph_base = await session.scalar(
                        select(KnowledgeBase).where(
                            KnowledgeBase.learner_id == learner_id,
                            KnowledgeBase.name == "LingxiGraph 知识图谱",
                        )
                    )
                    if graph_base is None:
                        graph_base = KnowledgeBase(
                            id=f"kb_{uuid.uuid4().hex}",
                            learner_id=learner_id,
                            name="LingxiGraph 知识图谱",
                            description="由学习任务生成的只读知识图谱快照。",
                            metadata_payload={"source": "lingxigraph", "readOnly": True},
                        )
                        session.add(graph_base)
                        await session.flush()
                    existing_documents = (
                        (
                            await session.execute(
                                select(KnowledgeDocument).where(
                                    KnowledgeDocument.base_id == graph_base.id
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                    existing_graph_revisions = {
                        str((document.metadata_payload or {}).get("graphId"))
                        + ":"
                        + str((document.metadata_payload or {}).get("revision")): document
                        for document in existing_documents
                    }
                    for graph in graphs:
                        graph_key = f"{graph.graph_id}:{graph.revision}"
                        if graph_key in existing_graph_revisions:
                            continue
                        nodes = (
                            (
                                await session.execute(
                                    select(KnowledgeGraphNode).where(
                                        KnowledgeGraphNode.graph_id == graph.graph_id
                                    )
                                )
                            )
                            .scalars()
                            .all()
                        )
                        edges = (
                            (
                                await session.execute(
                                    select(KnowledgeGraphEdge).where(
                                        KnowledgeGraphEdge.graph_id == graph.graph_id
                                    )
                                )
                            )
                            .scalars()
                            .all()
                        )
                        content = json.dumps(
                            {
                                "graphId": graph.graph_id,
                                "revision": graph.revision,
                                "title": graph.title,
                                "domain": graph.domain,
                                "nodes": [
                                    {"id": node.node_id, "label": node.label, "type": node.type}
                                    for node in nodes
                                ],
                                "edges": [
                                    {
                                        "id": edge.edge_id,
                                        "source": edge.source_node_id,
                                        "target": edge.target_node_id,
                                        "relation": edge.relation,
                                    }
                                    for edge in edges
                                ],
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        document = KnowledgeDocument(
                            id=f"doc_{uuid.uuid4().hex}",
                            base_id=graph_base.id,
                            name=f"{graph.title} · Revision {graph.revision}",
                            mime_type="application/json",
                            content=content,
                            metadata_payload={
                                "source": "lingxigraph",
                                "readOnly": True,
                                "graphId": graph.graph_id,
                                "revision": graph.revision,
                            },
                        )
                        session.add(document)
                        for ordinal, start in enumerate(range(0, len(content), 1200)):
                            session.add(
                                KnowledgeChunk(
                                    id=f"chunk_{uuid.uuid4().hex}",
                                    document_id=document.id,
                                    ordinal=ordinal,
                                    text=content[start : start + 1200],
                                    metadata_payload={"source": "lingxigraph"},
                                )
                            )
                        projected += 1
                if projected or workspace not in session.new:
                    await session.commit()
                return projected

    async def cancel_agent_task(self, task_id: str, learner_id: str) -> dict[str, Any]:
        record = await self.repo.get_agent_task_for_learner(task_id, learner_id)
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        if record.status in {"completed", "partial", "handed_off", "failed", "cancelled"}:
            return {"id": task_id, "status": record.status}
        await self.repo.set_agent_task_status(task_id, "cancelled")
        await self.repo.append_agent_events(
            task_id, [{"kind": "task.cancelled", "agent": "coordinator", "payload": {}}]
        )
        self._notify_agent(task_id)
        return {"id": task_id, "status": "cancelled"}

    async def upload_attachment(
        self, *, learner_id: str, filename: str, media_type: str, size: int, encoded: str
    ) -> dict[str, Any]:
        if size > 20 * 1024 * 1024:
            raise ValueError("attachment too large")
        try:
            content = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("invalid attachment data") from exc
        if len(content) != size:
            raise ValueError("attachment size mismatch")
        attachment_id = uuid.uuid4().hex
        root = self.settings.agent_task_dir / "uploads" / learner_id
        root.mkdir(parents=True, exist_ok=True)
        path = root / attachment_id
        path.write_bytes(content)
        return {
            "key": f"{learner_id}/{attachment_id}",
            "path": f"/api/attachments/{learner_id}/{attachment_id}",
            "filename": filename,
            "media_type": media_type,
            "size": size,
        }

    def attachment_path(self, learner_id: str, attachment_id: str) -> tuple[Path, str, str]:
        if not attachment_id.isalnum() or len(attachment_id) != 32:
            raise KeyError("unknown attachment")
        path = (self.settings.agent_task_dir / "uploads" / learner_id / attachment_id).resolve()
        root = (self.settings.agent_task_dir / "uploads" / learner_id).resolve()
        if root not in path.parents or not path.is_file():
            raise KeyError("unknown attachment")
        return path, "application/octet-stream", attachment_id

    def agent_waiter(self, task_id: str) -> asyncio.Event:
        return self._agent_waiters[task_id]

    def _notify_agent(self, task_id: str) -> None:
        event = self._agent_waiters[task_id]
        event.set()
        event.clear()

    async def agent_artifact(
        self, task_id: str, kind: str, learner_id: str | None = None
    ) -> tuple[bytes, str, str]:
        record = (
            await self.repo.get_agent_task_for_learner(task_id, learner_id)
            if learner_id is not None
            else await self.repo.get_agent_task(task_id)
        )
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        if kind == "lecture-deck":
            try:
                return (
                    self.agent_artifacts.deck_path(task_id).read_bytes(),
                    "text/html; charset=utf-8",
                    "lecture.html",
                )
            except OSError as exc:
                raise KeyError("lecture deck is not ready") from exc
        if kind == "lesson-intro":
            try:
                return (
                    self.agent_artifacts.lesson_intro_path(task_id).read_bytes(),
                    "text/html; charset=utf-8",
                    "lesson-intro.html",
                )
            except OSError as exc:
                raise KeyError("lesson intro is not ready") from exc
        if kind == "visual":
            try:
                return (
                    self.agent_artifacts.read_html(task_id),
                    "text/html; charset=utf-8",
                    "visual-explainer.html",
                )
            except ArtifactError as exc:
                raise KeyError(str(exc)) from exc
        raise KeyError(f"unknown artifact kind: {kind}")

    async def agent_knowledge_graph(self, task_id: str, learner_id: str) -> dict[str, Any] | None:
        """Return the graph target recorded by this task, owned by the learner."""

        record = await self.repo.get_agent_task_for_learner(task_id, learner_id)
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        sidecars = await self.repo.list_agent_sidecars(task_id, learner_id)
        for sidecar in reversed(sidecars):
            if sidecar["kind"] != "knowledge_graph":
                continue
            graph_id = (sidecar.get("output") or {}).get("graph_id")
            if graph_id:
                return await self.repo.get_knowledge_graph(graph_id, learner_id)
        return None

    def _artifact_snapshot(self, record: Any) -> list[dict[str, Any]]:
        """The artifacts this task actually produced, read from disk.

        Derived rather than declared: an artifact kind that a provider stops
        producing disappears from the response instead of lingering as a key
        that is permanently ``available: false``.
        """

        found: list[dict[str, Any]] = []
        for kind, exists in (
            ("lesson-intro", self.agent_artifacts.lesson_intro_path(record.id).exists()),
            ("lecture-deck", self.agent_artifacts.deck_path(record.id).exists()),
            ("visual", self.agent_artifacts.html_path(record.id).exists()),
        ):
            if exists:
                found.append(
                    {
                        "kind": kind,
                        "url": f"/api/agent-tasks/{record.id}/artifacts/{kind}",
                    }
                )
        if record.quiz_result:
            found.append({"kind": "quiz", "data": quiz_public(record.quiz_result)})
        return found

    async def _knowledge_graph_artifact_snapshot(self, record: Any) -> dict[str, Any]:
        sidecars = await self.repo.list_agent_sidecars(record.id, record.learner_id)
        sidecar = next(
            (item for item in reversed(sidecars) if item["kind"] == "knowledge_graph"),
            None,
        )
        output = (sidecar or {}).get("output") or {}
        return {
            "available": bool(output.get("graph_id")),
            "graph_id": output.get("graph_id"),
            "revision": output.get("revision"),
            "url": f"/api/agent-tasks/{record.id}/knowledge-graph",
            "status": (sidecar or {}).get("status", "pending"),
            **({"error": sidecar["error"]} if sidecar and sidecar.get("error") else {}),
        }

    async def agent_message(
        self,
        task_id: str,
        message: str,
        *,
        attachments: list[dict[str, Any]] | None = None,
        learner_id: str | None = None,
    ) -> None:
        record = await (
            self.repo.get_agent_task_for_learner(task_id, learner_id)
            if learner_id
            else self.repo.get_agent_task(task_id)
        )
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        if record.status != "awaiting_user":
            raise ValueError(f"task_not_waiting:{record.status}")
        if not message.strip():
            raise ValueError("message must not be empty")
        attachment_refs = _normalize_attachment_refs(attachments, record.learner_id)
        self._spawn(
            self._drive_agent_task(
                task_id,
                record.learner_id,
                "",
                resume={"message": message, "kind": "chat", "attachments": attachment_refs},
            )
        )

    async def submit_agent_quiz(
        self,
        task_id: str,
        *,
        submission_id: str,
        answers: dict[str, Any],
        learner_id: str | None = None,
    ) -> dict[str, Any]:
        record = await (
            self.repo.get_agent_task_for_learner(task_id, learner_id)
            if learner_id
            else self.repo.get_agent_task(task_id)
        )
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        existing = await self.repo.get_quiz_submission(task_id)
        if existing is not None:
            if existing.submission_id == submission_id:
                return {
                    "status": "duplicate",
                    "submission": await _submission_snapshot(self.repo, task_id),
                }
            raise ValueError("already_submitted")
        if record.status != "awaiting_user":
            raise ValueError(f"task_not_waiting:{record.status}")
        result = _grade_agent_quiz(record.quiz_result or {}, answers)
        await self.repo.create_quiz_submission(
            task_id=task_id,
            submission_id=submission_id,
            answers=answers,
            per_question=result["per_question"],
            total_score=result["total_score"],
            total_points=result["total_points"],
        )
        self._spawn(
            self._drive_agent_task(
                task_id,
                record.learner_id,
                "",
                resume={"message": "已提交答题", "kind": "quiz_submit", "answers": answers},
            )
        )
        return {"status": "accepted", "submission": await _submission_snapshot(self.repo, task_id)}

    async def _drive_agent_task(
        self,
        task_id: str,
        learner_id: str,
        prompt: str,
        *,
        resume: dict[str, Any] | None = None,
        schedule_id: str | None = None,
        scheduled_for: datetime | None = None,
    ) -> None:
        # Keep the public task launcher cheap: queued tasks wait here instead
        # of all retaining graph state and provider response buffers at once.
        async with self._agent_slots:
            await self._run_agent_task(
                task_id,
                learner_id,
                prompt,
                resume=resume,
                schedule_id=schedule_id,
                scheduled_for=scheduled_for,
            )

    async def _run_agent_task(
        self,
        task_id: str,
        learner_id: str,
        prompt: str,
        *,
        resume: dict[str, Any] | None = None,
        schedule_id: str | None = None,
        scheduled_for: datetime | None = None,
    ) -> None:
        if self.agent_model is None:
            await self.repo.set_agent_task_status(task_id, "failed", "DS_API_KEY is not configured")
            self._notify_agent(task_id)
            return
        record = await self.repo.get_agent_task_for_learner(task_id, learner_id)
        if record is None:
            return
        if resume is not None and resume.get("message"):
            await self.repo.update_agent_task_output(
                task_id,
                "user_message",
                {
                    "message": str(resume.get("message")),
                    "kind": str(resume.get("kind") or "chat"),
                    "answers": _json_safe(resume.get("answers"))
                    if resume.get("answers") is not None
                    else None,
                    "attachments": _json_safe(resume.get("attachments") or []),
                },
            )
        latest = await self.repo.get_agent_task_for_learner(task_id, learner_id)
        if latest is None or latest.status == "cancelled":
            return
        await self.repo.set_agent_task_status(task_id, "running")
        execution_id = f"exec-{uuid.uuid4().hex}"
        await self.repo.create_agent_execution(
            execution_id=execution_id,
            task_id=task_id,
            learner_id=learner_id,
            graph_version=record.graph_version,
            trigger="resume"
            if resume is not None
            else ("schedule" if schedule_id else "agent-task"),
            schedule_id=schedule_id,
            scheduled_for=scheduled_for,
        )
        projector = SimRunProjector(
            execution_id=execution_id,
            task_id=task_id,
            graph_version=record.graph_version,
        )
        start_runtime = {
            "execution_id": execution_id,
            "task_id": task_id,
            "graph_version": record.graph_version,
        }
        start_events = [
            {
                "kind": "run.started",
                "agent": "coordinator",
                "execution_id": execution_id,
                "runtime": start_runtime,
                "payload": {"status": "running", "runtime": start_runtime},
            }
        ]
        if resume is not None:
            start_events.append(
                {
                    "kind": "run.resumed",
                    "agent": "coordinator",
                    "execution_id": execution_id,
                    "runtime": start_runtime,
                    "payload": {"status": "running", "runtime": start_runtime},
                }
            )
        await self.repo.append_agent_events(task_id, start_events)

        async def persist_buffer(events: list[dict[str, Any]]) -> None:
            if not events:
                return
            for item in events:
                item.setdefault("execution_id", execution_id)
                item.setdefault("runtime", (item.get("payload") or {}).get("runtime") or {})
            await self.repo.append_agent_events(task_id, events)
            await self.repo.update_agent_execution(
                execution_id,
                workflow_state=projector.snapshot()["workflowState"],
                trace_spans=projector.snapshot()["traceSpans"],
                event_count=await self.repo.agent_event_count_for_execution(execution_id),
            )
            self._notify_agent(task_id)

        async def persist_result(agent: str, value: dict[str, Any]) -> None:
            await self.repo.update_agent_task_output(task_id, agent, value)
            self._notify_agent(task_id)

        # One runtime for every task. There is no second topology to choose
        # between, and no graph_version branch to pick it with.
        config = {
            "configurable": {
                "thread_id": task_id,
                "checkpoint_ns": f"{LOOP_GRAPH_NAME}@{LOOP_GRAPH_VERSION}",
            },
            "recursion_limit": 80,
        }
        buffer: list[dict[str, Any]] = []
        current_agent = "coordinator"
        graph: Any | None = None

        def emit_runtime_event(kind: str, payload: dict[str, Any]) -> None:
            buffer.append(
                {
                    "kind": kind,
                    "agent": str(payload.pop("agent", "orchestrator")),
                    "payload": _json_safe(payload),
                    "execution_id": execution_id,
                }
            )

        session_state = await self.runtime_state.ensure_session_state(
            learner_id=learner_id,
            task_id=task_id,
            budget=new_budget(),
        )
        prior_results, prior_artifacts = self._task_results(record)

        try:
            graph = self.loop_for(
                learner_id=learner_id,
                task_id=task_id,
                execution_id=execution_id,
                emit=emit_runtime_event,
                confirmed_actions=frozenset(
                    (session_state.get("plan") or {}).get("confirmed_actions") or ()
                ),
                prior_results=prior_results,
                prior_artifacts=prior_artifacts,
            )
            graph_input: Any = (
                Command(resume=resume)
                if resume is not None
                else initial_loop_state(
                    learner_id=learner_id,
                    task_id=task_id,
                    utterance=prompt,
                    budget=session_state.get("budget") or new_budget(),
                )
            )
            async for streamed in graph.astream(
                graph_input,
                config,
                stream_mode=("events", "messages"),
                context={
                    "learner_id": learner_id,
                    "locale": "zh-CN",
                    "resource_refs": list(record.resources or []),
                },
            ):
                current_record = await self.repo.get_agent_task_for_learner(task_id, learner_id)
                if current_record is None:
                    return
                if current_record.status == "cancelled":
                    snapshot = projector.snapshot()
                    await self.repo.update_agent_execution(
                        execution_id,
                        status="cancelled",
                        workflow_state=snapshot["workflowState"],
                        trace_spans=snapshot["traceSpans"],
                        ended=True,
                    )
                    self._notify_agent(task_id)
                    return
                mode, event = streamed
                force_flush = False
                if mode == "messages":
                    message_events = _message_trace_events(event, current_agent)
                    buffer.extend(message_events)
                    for item in message_events:
                        item["execution_id"] = execution_id
                    if len(buffer) >= AGENT_FLUSH_EVERY:
                        await persist_buffer(list(buffer))
                        buffer.clear()
                    continue
                node = str(event.node or "")
                if node and node not in _LOOP_NODES:
                    # A child agent's node: attribute to it until it completes.
                    if event.kind is EventKind.NODE_STARTED:
                        current_agent = node
                    elif event.kind is EventKind.NODE_COMPLETED:
                        current_agent = "coordinator"
                projected = projector.consume(event, agent=current_agent)
                if event.kind is EventKind.CUSTOM:
                    data = dict(event.data or {})
                    if data.get("channel") == EVENT_CHANNEL:
                        value = data.get("value") or {}
                        if isinstance(value, dict) and value.get("type"):
                            event_type = str(value["type"])
                            buffer.append(
                                {
                                    "kind": event_type,
                                    "agent": str(value.get("agent") or "coordinator"),
                                    "payload": {
                                        str(k): _json_safe(v)
                                        for k, v in value.items()
                                        if k not in {"type", "agent"}
                                    },
                                    "execution_id": execution_id,
                                    "runtime": projected.get("runtime") or {},
                                }
                            )
                            force_flush = event_type in _AGENT_FORCE_FLUSH
                    else:
                        projected["agent"] = current_agent
                        buffer.append(projected)
                elif projected.get("kind"):
                    projected["agent"] = projected.get("agent") or current_agent
                    buffer.append(projected)
                if force_flush or len(buffer) >= AGENT_FLUSH_EVERY:
                    await persist_buffer(list(buffer))
                    buffer.clear()
        except Exception as exc:  # noqa: BLE001 - task failures are user-visible state
            logger.exception("agent task failed: %s", task_id)
            detail = _safe_agent_error(exc, self.settings)
            recovered_intro = await self.agent_artifacts.recover_lesson_intro_draft(task_id)
            if recovered_intro is not None:
                buffer.append(
                    {
                        "kind": "artifact.recovered",
                        "agent": "lecture_hook",
                        "payload": {
                            "artifact": "lesson-intro",
                            "relative_path": recovered_intro["relative_path"],
                            "message": "课程引入生成被中断，已从已写入草稿恢复可用页面。",
                        },
                    }
                )
            recovered_deck = await self.agent_artifacts.recover_deck_draft(task_id)
            if recovered_deck is not None:
                buffer.append(
                    {
                        "kind": "artifact.recovered",
                        "agent": "interactive_lecture_deck",
                        "payload": {
                            "artifact": "lecture-deck",
                            "relative_path": f"{task_id}/lecture-deck/dist/lecture.html",
                            "message": "课件生成被中断或校验失败，已从已写入源文件恢复可用发布物。",
                            "validation": recovered_deck["validation"],
                        },
                    }
                )
            buffer.append(
                {
                    "kind": "task.failed",
                    "agent": "coordinator",
                    "payload": {
                        "error_type": type(exc).__name__,
                        "message": f"运行失败：{type(exc).__name__}: {detail}",
                    },
                }
            )
            await persist_buffer(buffer)
            buffer.clear()
            await self.repo.set_agent_task_status(
                task_id, "failed", f"运行失败：{type(exc).__name__}: {detail}"
            )
            snapshot = projector.snapshot()
            await self.repo.update_agent_execution(
                execution_id,
                status="failed",
                error=f"运行失败：{type(exc).__name__}: {detail}",
                workflow_state=snapshot["workflowState"],
                trace_spans=snapshot["traceSpans"],
                ended=True,
            )
            self._notify_agent(task_id)
            return

        if buffer:
            await persist_buffer(buffer)
        if graph is None:  # pragma: no cover - the try/except above returns on failure
            return
        state = await graph.aget_state(config)
        values = dict(getattr(state, "values", None) or {})
        status = str(
            values.get("status")
            or ("awaiting_user" if getattr(state, "interrupts", None) else "partial")
        )
        errors = [str(item) for item in values.get("errors") or []]
        await self.repo.set_agent_task_status(
            task_id, "handed_off" if status == "handed_off" else status, "; ".join(errors)
        )
        await self.repo.update_agent_execution(
            execution_id,
            status="awaiting_user"
            if status == "awaiting_user"
            else ("completed" if status in {"completed", "handed_off"} else status),
            workflow_state=projector.snapshot()["workflowState"],
            trace_spans=projector.snapshot()["traceSpans"],
            error="; ".join(errors),
            ended=status not in {"awaiting_user", "partial"},
        )
        # Publish generated HTML artifacts as native read-only workspace files
        # while retaining the original task-audit files and URLs.
        try:
            await self.project_agent_artifacts(learner_id, task_id)
        except Exception:  # noqa: BLE001 - projection must not fail the task
            logger.exception("failed to project task artifacts: %s", task_id)
        self._notify_agent(task_id)
    async def schedule_capability(
        self, task_id: str, learner_id: str, capability: str, inputs: dict[str, Any] | None = None
    ) -> None:
        """Queue one non-blocking capability run outside the learner's turn.

        Background work is scheduled by capability, resolved through the same
        registry the loop uses. There is no per-kind branch here: adding a
        background capability means registering a skill, not editing this method.
        """

        record = await self.repo.get_agent_task_for_learner(task_id, learner_id)
        if record is None:
            return
        try:
            capability_info = capability_details(capability)
        except UnknownCapability:
            logger.warning("refusing to schedule unknown capability: %s", capability)
            return

        sidecar_id = f"{task_id}:{capability.replace('.', '-')}"
        sidecar = await self.repo.upsert_agent_sidecar(
            sidecar_id=sidecar_id,
            task_id=task_id,
            learner_id=learner_id,
            kind=capability,
            input={
                "capability": capability,
                "label": capability_info.label,
                "inputs": _json_safe(inputs or {}),
                "queued_at": datetime.now(UTC).isoformat(),
            },
        )
        if sidecar["status"] == "queued":
            self._spawn(self._run_capability_sidecar(sidecar["id"]))

    async def _run_capability_sidecar(self, sidecar_id: str) -> None:
        async with self._sidecar_slots:
            await self._run_capability_sidecar_inner(sidecar_id)

    async def _run_capability_sidecar_inner(self, sidecar_id: str) -> None:
        """Run one queued capability through the same dispatcher the loop uses."""

        sidecar = await self.repo.claim_agent_sidecar(sidecar_id)
        if sidecar is None:
            return
        task_id = sidecar["task_id"]
        learner_id = sidecar["learner_id"]
        capability = str(sidecar["kind"])
        payload = dict(sidecar.get("input") or {})

        await self.repo.append_agent_events(
            task_id,
            [{"kind": "sidecar.started", "agent": capability,
              "payload": {"sidecar_id": sidecar_id, "capability": capability}}],
        )
        self._notify_agent(task_id)
        try:
            record = await self.repo.get_agent_task_for_learner(task_id, learner_id)
            if record is None:
                raise KeyError("agent task not found")
            if self.agent_model is None:
                raise RuntimeError("agent model is not configured")

            skills = await self.runtime_state.list_skills(
                learner_id=learner_id, enabled_only=True
            )
            stack = await self.runtime_state.goal_stack(task_id)
            goal = stack.current() or Goal(goal_type="learn", topic=record.prompt)
            prior_results, prior_artifacts = self._task_results(record)

            dispatcher = Dispatcher(
                DispatchDeps(
                    runtime_state=self.runtime_state,
                    learner_id=learner_id,
                    task_id=task_id,
                    goal=goal,
                    skills=skills,
                    model=self.agent_model,
                    settings=self.settings,
                    artifacts=self.agent_artifacts,
                    registry=self.registry,
                )
            )
            dispatcher.seed_results(prior_results)
            dispatcher.seed_artifacts(prior_artifacts)

            task = PlannedTask(
                id=f"bg-{capability}",
                capability=capability,
                knowledge_point_id=goal.knowledge_points[0] if goal.knowledge_points else "",
                inputs=dict(payload.get("inputs") or {}),
                done_when=DoneCondition(kind="always"),
                rationale=str(payload.get("label") or capability),
                estimated_cost=Cost(blocking=False),
            )
            profile = {
                str(row["knowledge_point_id"]): row
                for row in await self.runtime_state.profile_for(learner_id)
            }
            outcome = await dispatcher.run(task, profile=profile, budget=Budget())

            if outcome.status == "failed":
                raise RuntimeError(outcome.detail or f"{capability} failed")

            for key, value in dispatcher.results.items():
                if key not in prior_results:
                    await self.repo.update_agent_task_output(task_id, key, _json_safe(value))

            await self.repo.finish_agent_sidecar(
                sidecar_id,
                status="succeeded",
                output={"capability": capability, "detail": outcome.detail,
                        "artifacts": outcome.artifacts},
            )
            await self.repo.append_agent_events(
                task_id,
                [{"kind": "sidecar.completed", "agent": capability,
                  "payload": {"sidecar_id": sidecar_id, "capability": capability,
                              "detail": outcome.detail}}],
            )
        except Exception as exc:  # sidecars never fail the learner-facing run
            logger.exception("capability sidecar failed: %s", sidecar_id)
            detail = f"{type(exc).__name__}: {exc}"
            await self.repo.finish_agent_sidecar(sidecar_id, status="failed", error=detail)
            await self.repo.append_agent_events(
                task_id,
                [{"kind": "sidecar.failed", "agent": capability,
                  "payload": {"sidecar_id": sidecar_id, "error": detail}}],
            )
        finally:
            self._notify_agent(task_id)

    async def answer(self, session_id: str, payload: Any, learner_id: str | None = None) -> None:
        record = (
            await self.repo.get_session_for_learner(session_id, learner_id)
            if learner_id is not None
            else await self.repo.get_session(session_id)
        )
        if record is None:
            raise KeyError(f"unknown session: {session_id}")
        pack = self.packs.get(record.pack_id)
        if pack is None:
            raise KeyError(f"unknown pack: {record.pack_id}")
        await self.repo.set_status(session_id, "running")
        self._spawn(self._drive(session_id, pack, record.learner_id, Command(resume=payload)))

    async def snapshot(self, session_id: str, learner_id: str | None = None) -> dict[str, Any]:
        record = (
            await self.repo.get_session_for_learner(session_id, learner_id)
            if learner_id is not None
            else await self.repo.get_session(session_id)
        )
        if record is None:
            raise KeyError(f"unknown session: {session_id}")
        pack = self.packs[record.pack_id]
        session_state = await self.runtime_state.get_session_state(session_id) or {}
        stack = await self.runtime_state.goal_stack(session_id)
        current_goal = stack.current()
        decisions = await self.runtime_state.decisions_for_task(session_id)
        profile = await self.runtime_state.profile_for(record.learner_id)
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
        """Run the loop to its next pause, persisting projections as it goes."""

        async with self._run_locks[session_id]:
            buffer: list[dict[str, Any]] = []

            async def flush() -> None:
                if buffer:
                    await self.repo.append_events(session_id, list(buffer))
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

            session_state = await self.runtime_state.ensure_session_state(
                learner_id=learner_id, task_id=session_id, session_id=session_id
            )
            graph = self.loop_for(
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

            latest = await self.runtime_state.get_session_state(session_id) or {}
            runtime_status = str(latest.get("runtime_status") or RuntimeStatus.PLANNING)
            if status == "awaiting_learner":
                status = await self._finalize(
                    session_id, pack, learner_id, runtime_status
                )
            elif status in {"failed", "cancelled"}:
                await self._finalize(
                    session_id, pack, learner_id, runtime_status, outcome_override="failed"
                )
            await self.repo.set_status(session_id, status, error)
            if error:
                await self.repo.append_events(
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

        completed = outcome_override is None and runtime_status == str(
            RuntimeStatus.COMPLETED
        )
        rows = await self.runtime_state.profile_for(learner_id)
        mastery = {
            str(row["knowledge_point_id"]): float(row.get("mastery") or 0.0) for row in rows
        }
        misconceptions = sorted(
            {
                str(tag)
                for row in rows
                for tag in ((row.get("system") or {}).get("misconceptions") or [])
            }
        )
        evidence = await self.runtime_state.evidence_for_task(session_id)
        decisions = await self.runtime_state.decisions_for_task(session_id)
        report = {
            "session_id": session_id,
            "pack_id": pack.id,
            "decisions": len(decisions),
            "mastery": mastery,
            "misconceptions": misconceptions,
        }

        try:
            context = await self.learners.context_for_learner_id(learner_id)
        except LookupError:
            # Anonymous records created before the identity boundary remain
            # readable only to legacy internal tooling and are never mapped
            # automatically to a new Identity user.
            if completed:
                await self.repo.save_mastery(learner_id, mastery)
                await self.repo.save_report(
                    session_id=session_id,
                    learner_id=learner_id,
                    mission_id="",
                    report=report,
                )
                return "done"
            return "failed"

        session_record = await self.repo.get_session(session_id)
        await self.learners.record_session_outcome(
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


def _public_step(step: dict[str, Any]) -> dict[str, Any]:
    """Strip the answer key before a step ever crosses the wire."""
    return {
        k: v
        for k, v in step.items()
        if k not in {"grader", "walkthrough", "leak_guard", "hint_ladder"}
    }


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="json"))
    return str(value)


def _agents_from_trace(
    decisions: list[dict[str, Any]], sidecars: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Which agents ran this task, derived rather than enumerated.

    The old snapshot hard-coded one key per specialist, which meant every new
    capability needed an edit here and every removed one left a dead key. This
    reads what actually happened.
    """

    seen: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        for task in (decision.get("outcome") or {}).get("tasks") or []:
            name = str(task.get("provider") or task.get("capability") or "")
            if not name:
                continue
            entry = seen.setdefault(
                name,
                {
                    "agent": name,
                    "capability": task.get("capability"),
                    "skill_id": task.get("skill_id"),
                    "runs": 0,
                    "status": "pending",
                    "detail": "",
                },
            )
            entry["runs"] += 1
            entry["status"] = str(task.get("status") or "completed")
            entry["detail"] = str(task.get("detail") or "")
    for sidecar in sidecars:
        name = str(sidecar.get("kind") or "")
        entry = seen.setdefault(
            name,
            {"agent": name, "capability": name, "skill_id": "", "runs": 0,
             "status": "pending", "detail": ""},
        )
        entry["status"] = str(sidecar.get("status") or entry["status"])
        entry["background"] = True
    return sorted(seen.values(), key=lambda item: str(item["agent"]))


def _lesson_intro_metadata(result: dict[str, Any]) -> dict[str, Any]:
    """Expose lesson metadata without duplicating the learner-facing HTML in snapshots."""
    return {
        key: result[key] for key in ("topic", "status", "warnings", "validation") if key in result
    }


async def _submission_snapshot(repo: Repository, task_id: str) -> dict[str, Any] | None:
    row = await repo.get_quiz_submission(task_id)
    if row is None:
        return None
    return {
        "submission_id": row.submission_id,
        "submitted_at": row.created_at.isoformat() if row.created_at else None,
        "total_score": row.total_score,
        "total_points": row.total_points,
        "per_question": row.per_question or [],
        "handoff_reason": row.handoff_reason,
    }


def _grade_agent_quiz(quiz: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    per_question: list[dict[str, Any]] = []
    total_score = 0.0
    total_points = 0
    for question in quiz.get("questions", []):
        qid = str(question.get("id", ""))
        points = int(question.get("points", 1))
        total_points += points
        actual = answers.get(qid)
        expected = question.get("answer")
        qtype = question.get("type")
        expected_options = (
            expected.get("option_ids", []) if isinstance(expected, dict) else expected
        )
        if qtype == "multi_choice":
            correct = set(actual or []) == set(expected_options or [])
        elif qtype == "short_text":
            text = str(actual or "").strip().casefold()
            rubric_keywords = expected.get("keywords", []) if isinstance(expected, dict) else []
            keywords = [
                str(item).strip().casefold()
                for item in (rubric_keywords or question.get("keywords", []))
                if str(item).strip()
                and not str(item).startswith(("concept:", "bloom:", "difficulty:", "purpose:"))
            ]
            correct = bool(keywords) and all(keyword in text for keyword in keywords)
        else:
            correct = str(actual or "") in {str(item) for item in (expected_options or [])}
        score = points if correct else 0
        total_score += score
        per_question.append({"id": qid, "correct": correct, "score": score, "points": points})
    return {"per_question": per_question, "total_score": total_score, "total_points": total_points}
