"""Application layer: focused use-case services and the composition root.

Module dependency direction (no cycles):

    container
      ├── conversation ──→ graph_factory
      ├── agent_tasks ──→ agent_events, artifacts, runtime_port
      ├── runtime_adapter ──→ agent_events, artifacts, graph_factory
      ├── agent_events
      ├── artifacts
      ├── learner_state
      └── runtime_port (Protocol only)
"""

from __future__ import annotations

from .agent_events import AgentEventService
from .agent_tasks import AgentTaskService, agent_task_create_payload_digest
from .artifacts import ArtifactResourceService
from .container import ApplicationServices
from .conversation import ConversationService
from .learner_state import LearnerStateService
from .runtime_adapter import LingxiGraphRuntimeAdapter
from .runtime_port import RuntimeInputPort
from .shared import BackgroundTasks

__all__ = [
    "AgentEventService",
    "AgentTaskService",
    "ApplicationServices",
    "ArtifactResourceService",
    "BackgroundTasks",
    "ConversationService",
    "LearnerStateService",
    "LingxiGraphRuntimeAdapter",
    "RuntimeInputPort",
    "agent_task_create_payload_digest",
]
