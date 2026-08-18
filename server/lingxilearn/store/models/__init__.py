"""Domain models organized by functional area.

All models share a single Base.metadata for Alembic migrations.
Import from domain-specific modules for clear dependency boundaries.
"""

from .base import Base, utcnow
from .identity import IdentityUser, Learner, LearnerProfile
from .workspace import (
    Session,
    Workspace,
    WorkspaceActivityEvent,
    WorkspaceFile,
    WorkspaceFolder,
    WorkspaceUploadSession,
)
from .learning import (
    LearningEvent,
    LearningEvidence,
    LearningPreference,
    LearningProfile,
    Mastery,
    Misconception,
    ReportRecord,
)
from .agent import AgentTask, AgentTurn, CandidateSnapshot, CommandInbox, DecisionTrace
from .runtime import (
    AgentExecution,
    AgentInteraction,
    AgentInteractionAnswer,
    AgentRun,
    AgentSchedule,
    AgentScheduleRun,
    RunEvent,
    SkillRun,
)
from .knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeTag
from .table import (
    WorkspaceTable,
    WorkspaceTableColumn,
    WorkspaceTableRow,
    WorkspaceTableView,
)
from .work import (
    BudgetLedger,
    FactSnapshot,
    SessionState,
    SessionStateEvent,
    SkillRegistryEntry,
    WorkDependency,
    WorkItem,
    WorkResult,
)

__all__ = [
    # Base
    "Base",
    "utcnow",
    # Identity
    "Learner",
    "IdentityUser",
    "LearnerProfile",
    # Workspace
    "Session",
    "Workspace",
    "WorkspaceFolder",
    "WorkspaceFile",
    "WorkspaceUploadSession",
    "WorkspaceActivityEvent",
    # Learning
    "Mastery",
    "Misconception",
    "LearningEvidence",
    "LearningProfile",
    "LearningPreference",
    "LearningEvent",
    "ReportRecord",
    # Agent
    "AgentTask",
    "AgentTurn",
    "CandidateSnapshot",
    "CommandInbox",
    "DecisionTrace",
    # Runtime
    "AgentExecution",
    "AgentRun",
    "SkillRun",
    "AgentInteraction",
    "AgentInteractionAnswer",
    "AgentSchedule",
    "AgentScheduleRun",
    "RunEvent",
    # Knowledge
    "KnowledgeBase",
    "KnowledgeDocument",
    "KnowledgeChunk",
    "KnowledgeTag",
    # Table
    "WorkspaceTable",
    "WorkspaceTableColumn",
    "WorkspaceTableRow",
    "WorkspaceTableView",
    # Work
    "WorkItem",
    "WorkDependency",
    "WorkResult",
    "FactSnapshot",
    "BudgetLedger",
    "SessionState",
    "SessionStateEvent",
    "SkillRegistryEntry",
]