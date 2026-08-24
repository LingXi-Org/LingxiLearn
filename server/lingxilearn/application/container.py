"""Application composition root.

``ApplicationServices`` builds the database, the #56 domain repositories, the
focused use-case services and the runtime adapter, and owns process lifecycle
(startup/shutdown).  It deliberately exposes no business operations of its own:
callers go to the focused service for their use case.  Repositories stay
reachable as composition references for infrastructure wiring (scheduler
worker, tests); they are not a facade that re-aggregates business logic.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from lingxigraph import PostgresSaver, SqliteSaver

from ..agents.artifact_store import ArtifactStore
from ..agents.model_runtime import model_roles
from ..agents.providers import load_all as load_providers
from ..agents.providers import missing_providers
from ..brains.base import TutorBrain
from ..config import REPO_ROOT, Settings, get_settings
from ..learner import LearnerService
from ..packs.loader import discover_packs, validate_pack
from ..packs.models import Pack
from ..runtime.sim_semantics import PrimitiveCatalog
from ..state.skill_catalog import discover as discover_skill_manifests
from ..store.database import Database
from ..store.learner import LearnerRepository
from ..store.repositories.agent_tasks import AgentTaskRepository
from ..store.repositories.logs import LogRepository
from ..store.repositories.runtime import RuntimeRepository
from ..store.repositories.sessions import SessionRepository
from ..store.repositories.work_ledger import WorkLedgerRepository
from ..store.runtime_state import RuntimeStateRepository
from ..tools import knowledge
from ..tools.registry import ToolRegistry, load_builtin_tools
from .agent_events import AgentEventService
from .agent_tasks import AgentTaskService
from .artifacts import ArtifactResourceService
from .conversation import ConversationService
from .graph_factory import RuntimeGraphFactory
from .learner_state import LearnerStateService
from .runtime_adapter import LingxiGraphRuntimeAdapter
from .shared import BackgroundTasks
from .skills import SkillService
from .workspace_file_service import WorkspaceFileService
from .workspace_knowledge_service import WorkspaceKnowledgeService
from .workspace_table_service import WorkspaceTableService

logger = logging.getLogger(__name__)

# Control-plane and learner-facing graph nodes must answer without hidden
# reasoning. Only detached artifact production benefits from a thinking pass;
# it is allowed to spend that extra latency away from the interactive path.
THINKING_MODEL_ROLES = frozenset(
    {
        "lesson_intro",
        "lecture_deck",
        "visual_explainer",
        "quiz_generator",
        "retrieval_practice",
    }
)


def build_brain(settings: Settings) -> TutorBrain:
    """Pick a brain, falling back to the deterministic one when unconfigured."""
    kind = settings.effective_brain
    if kind == "openai":
        from ..brains.openai_compat import OpenAICompatBrain

        return OpenAICompatBrain(settings)
    if kind == "coze":
        from ..brains.coze import CozeBrain

        return CozeBrain(settings)
    from ..brains.scripted import ScriptedBrain

    return ScriptedBrain()


def build_checkpointer(settings: Settings) -> Any:
    dsn = settings.resolved_checkpoint_url
    if settings.database_url.startswith("postgresql"):
        saver = PostgresSaver(dsn)
        saver.setup()
        return saver
    Path(dsn).parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(dsn)  # constructor runs setup itself


class ApplicationServices:
    """Composition root: wires repositories, services and the runtime."""

    def __init__(self, settings: Settings | None = None, graph_store: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self.registry: ToolRegistry = load_builtin_tools()
        self.packs: dict[str, Pack] = {}
        self.db = Database(self.settings)
        self.agent_task_repository = AgentTaskRepository(self.db)
        self.runtime_repository = RuntimeRepository(self.db)
        self.work_ledger = WorkLedgerRepository(self.db)
        self.session_repository = SessionRepository(self.db)
        self.learner_repository = LearnerRepository(self.db)
        self.runtime_state = RuntimeStateRepository(self.db)
        self.learners = LearnerService(self.learner_repository, self.settings)
        self.brain: TutorBrain | None = None
        # Optional LingxiGraph runtime Store/Memory seam.  Canonical learner
        # data remains in LearnerRepository regardless of whether a host wires
        # this runtime capability in.
        self.graph_store = graph_store
        self.tasks = BackgroundTasks()
        board_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        artifact_store = ArtifactStore(self.settings)
        self.agent_artifacts = artifact_store
        self.graph_factory = RuntimeGraphFactory(
            runtime_state=self.runtime_state,
            work_ledger=self.work_ledger,
            runtime_repository=self.runtime_repository,
            settings=self.settings,
            artifacts=artifact_store,
            registry=self.registry,
            board_locks=board_locks,
            graph_store=graph_store,
        )
        self.artifacts = ArtifactResourceService(
            db=self.db,
            agent_task_repository=self.agent_task_repository,
            artifact_store=artifact_store,
            settings=self.settings,
        )
        self.agent_events = AgentEventService(
            agent_task_repository=self.agent_task_repository,
            runtime_repository=self.runtime_repository,
            work_ledger=self.work_ledger,
            runtime_state=self.runtime_state,
        )
        self.runtime = LingxiGraphRuntimeAdapter(
            agent_task_repository=self.agent_task_repository,
            work_ledger=self.work_ledger,
            runtime_repository=self.runtime_repository,
            runtime_state=self.runtime_state,
            settings=self.settings,
            artifact_service=self.artifacts,
            event_service=self.agent_events,
            graph_factory=self.graph_factory,
            tasks=self.tasks,
            board_locks=board_locks,
        )
        self.agent_tasks = AgentTaskService(
            agent_task_repository=self.agent_task_repository,
            work_ledger=self.work_ledger,
            runtime_repository=self.runtime_repository,
            runtime_state=self.runtime_state,
            learner_repository=self.learner_repository,
            db=self.db,
            artifact_service=self.artifacts,
            event_service=self.agent_events,
            runtime=self.runtime,
            board_locks=board_locks,
        )
        self.conversation = ConversationService(
            session_repository=self.session_repository,
            runtime_state=self.runtime_state,
            learner_repository=self.learner_repository,
            learner_service=self.learners,
            packs=self.packs,
            settings=self.settings,
            graph_factory=self.graph_factory,
            tasks=self.tasks,
        )
        self.learner_state = LearnerStateService(runtime_state=self.runtime_state)
        self.workspace_files = WorkspaceFileService(self.db)
        self.workspace_tables = WorkspaceTableService(self.db)
        self.workspace_knowledge = WorkspaceKnowledgeService(self.db)
        self.skills = SkillService(self.db)
        self.logs = LogRepository(self.db)

    @property
    def agent_model(self) -> dict[str, Any] | None:
        return self.graph_factory.agent_model

    # -- lifecycle -----------------------------------------------------------

    async def startup(self) -> None:
        self.packs.clear()
        self.packs.update(discover_packs(self.settings.packs_dir))
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
            # A capability the orchestrator can plan for but nobody can run is
            # a dead end at run time; surface it at startup instead.
            logger.warning("skills naming an unimplemented provider: %s", ", ".join(gaps))
        chunks = knowledge.configure(
            [p.root / "knowledge" for p in self.packs.values() if (p.root / "knowledge").exists()]
        )
        self.brain = build_brain(self.settings)
        if self.settings.agents_configured:
            from ..brains.traced_openai_compat import TracedOpenAICompatChatModel

            model_options = {
                "base_url": self.settings.agent_base_url,
                "api_key": self.settings.agent_api_key.get_secret_value(),
                "timeout": self.settings.agent_timeout,
                # Keep one shared low-latency default so every current and
                # future specialist avoids expensive hidden reasoning.
                "default_options": {"thinking": {"type": "disabled"}},
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
            self.graph_factory.agent_model = {
                role: TracedOpenAICompatChatModel(
                    self.settings.agent_model,
                    **{
                        **model_options,
                        "default_options": {
                            "thinking": {
                                "type": "enabled"
                                if role in THINKING_MODEL_ROLES
                                else "disabled"
                            }
                        },
                    },
                )
                # One instance per role: each has a different immutable system
                # prompt and tool catalog, and sharing one would break the
                # provider's prompt-cache prefix.
                for role in model_roles()
            }
        self.graph_factory.checkpointer = build_checkpointer(self.settings)
        # V2 work is recovered from the Work Ledger.
        await self.work_ledger.recover_expired_work()
        # Queued agent tasks and answered-but-unresumed interactions are
        # durable inputs; replay them after a restart.
        await self.runtime.recover_pending()
        logger.info(
            "LingxiLearn ready: %d pack(s), %d knowledge chunks, brain=%s",
            len(self.packs),
            chunks,
            self.brain.name,
        )

    async def shutdown(self) -> None:
        await self.tasks.aclose()
        if self.brain is not None:
            await self.brain.aclose()
        for model in (self.graph_factory.agent_model or {}).values():
            closer = getattr(model, "aclose", None)
            if callable(closer):
                await closer()
        if self.graph_factory.checkpointer is not None:
            closer = getattr(self.graph_factory.checkpointer, "close", None)
            if callable(closer):
                result = closer()
                if inspect.isawaitable(result):
                    await result
        await self.db.dispose()
