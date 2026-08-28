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
from typing import Any

from lingxigraph import PostgresSaver

from ..agents.artifact_source import GeneratedArtifactSource
from ..agents.artifact_store import ArtifactStore
from ..agents.model_runtime import model_roles
from ..agents.providers import load_all as load_providers
from ..agents.providers import missing_providers
from ..brains.base import TutorBrain
from ..config import REPO_ROOT, Settings, get_settings
from ..learner import LearnerService
from ..packs.loader import discover_packs, validate_pack
from ..packs.models import Pack
from ..runtime.execution import PrimitiveCatalog
from ..state.skill_catalog import discover as discover_skill_manifests
from ..store.artifact_storage import LocalArtifactStorage
from ..store.database import Database
from ..store.learner import LearnerRepository
from ..store.repositories.agent_tasks import AgentTaskRepository
from ..store.repositories.artifacts import ArtifactRepository
from ..store.repositories.runtime import RuntimeRepository
from ..store.repositories.skills import SkillRepository
from ..store.repositories.work_ledger import WorkLedgerRepository
from ..store.repositories.workspaces import WorkspaceRepository
from ..store.runtime_state import RuntimeStateRepository
from ..store.system_skill_catalog import SystemSkillCatalog
from ..tools import knowledge
from ..tools.registry import ToolRegistry, load_builtin_tools
from .agent_events import AgentEventService
from .agent_tasks import AgentTaskService
from .artifacts import ArtifactResourceService
from .graph_factory import RuntimeGraphFactory
from .learner_state import LearnerStateService
from .runtime_adapter import LingxiGraphRuntimeAdapter
from .shared import BackgroundTasks
from .skills import SkillService
from .workspace_artifacts import WorkspaceArtifactService
from .workspaces import WorkspaceService

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
    """Build the explicitly selected tutor brain."""
    kind = settings.brain
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
    if not dsn:
        raise RuntimeError("A PostgreSQL checkpoint URL is required")
    saver = PostgresSaver(dsn)
    saver.setup()
    return saver


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
        self.learner_repository = LearnerRepository(self.db)
        self.runtime_state = RuntimeStateRepository(self.db)
        self.skill_repository = SkillRepository(self.db)
        self.workspace_repository = WorkspaceRepository(self.db)
        self.artifact_repository = ArtifactRepository(self.db)
        self.artifact_storage = LocalArtifactStorage(self.settings.var_dir)
        self.learners = LearnerService(self.learner_repository, self.settings)
        self.workspaces = WorkspaceService(self.workspace_repository)
        self.workspace_artifacts = WorkspaceArtifactService(
            self.artifact_repository,
            self.artifact_storage,
            max_bytes=self.settings.max_artifact_bytes,
        )
        self.skills = SkillService(
            self.skill_repository,
            SystemSkillCatalog(self.runtime_state, REPO_ROOT / "skills"),
        )
        self.brain: TutorBrain | None = None
        # Optional LingxiGraph runtime Store/Memory seam.  Canonical learner
        # data remains in LearnerRepository regardless of whether a host wires
        # this runtime capability in.
        self.graph_store = graph_store
        self.tasks = BackgroundTasks()
        board_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        artifact_store = ArtifactStore(self.settings)
        self.agent_artifacts = artifact_store
        self.generated_artifact_source = GeneratedArtifactSource(artifact_store)
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
            agent_task_repository=self.agent_task_repository,
            repository=self.artifact_repository,
            storage=self.artifact_storage,
            source=self.generated_artifact_source,
            workspaces=self.workspaces,
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
            workspace_service=self.workspaces,
            artifact_repository=self.artifact_repository,
            skill_repository=self.skill_repository,
            artifact_service=self.artifacts,
            event_service=self.agent_events,
            runtime=self.runtime,
            board_locks=board_locks,
        )
        self.learner_state = LearnerStateService(runtime_state=self.runtime_state)

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
        # A tool without an execution capability mapping is a startup error.
        PrimitiveCatalog().validate(self.registry.names())
        # Seed the capability registry from the SKILL.md manifests on disk, so
        # the orchestrator plans against declared capabilities rather than a
        # hard-coded agent list.
        manifests = discover_skill_manifests(REPO_ROOT / "skills")
        await self.runtime_state.sync_skill_manifests(manifests)
        load_providers()
        gaps = missing_providers([manifest.to_row() for manifest in manifests])
        if gaps:
            raise RuntimeError("skills name providers with no implementation: " + ", ".join(gaps))
        chunks = knowledge.configure(
            [p.root / "knowledge" for p in self.packs.values() if (p.root / "knowledge").exists()]
        )
        self.brain = build_brain(self.settings)
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
                            "type": "enabled" if role in THINKING_MODEL_ROLES else "disabled"
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
