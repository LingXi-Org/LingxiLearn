"""Public V1 REST response models.

Every class is bound to a current endpoint through ``response_model`` and is
therefore part of the generated OpenAPI contract.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkspaceUpdateRequest(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    appearance: dict[str, Any] | None = None


class ArtifactRenameRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=255)


class SkillCreateRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    content: str = Field(min_length=1)
    version: str = Field(default="1.0.0", min_length=1, max_length=32)


class SkillUpdateRequest(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    content: str | None = Field(default=None, min_length=1)
    version: str | None = Field(default=None, min_length=1, max_length=32)


class SuccessResponse(BaseModel):
    success: bool


class LivenessResponse(BaseModel):
    status: Literal["live"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    services: bool
    database: bool


class NativeSkillInfo(BaseModel):
    id: str
    name: str = ""
    display_name: str = ""
    description: str | None = None
    version: str = ""
    license: str | None = None
    content: str = ""
    source: str = "system"
    is_system: bool = False
    capabilities: list[str] | None = None
    ownership: str | None = None
    provider: str | None = None
    cost: dict[str, Any] | None = None
    enabled: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SkillsResponse(BaseModel):
    skills: list[NativeSkillInfo]


class SkillRegistryEntryInfo(BaseModel):
    skill_id: str
    source: str
    learner_id: str | None = None
    display_name: str | None = None
    description: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    preconditions: dict[str, Any] = Field(default_factory=dict)
    cost: dict[str, Any] = Field(default_factory=dict)
    ownership: str | None = None
    provider: str | None = None
    version: str = ""
    enabled: bool = False
    checksum: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: str | None = None


class SkillRegistryCapabilityInfo(BaseModel):
    capability: str
    label: str
    learner_facing: bool
    heavy_artifact: bool
    irreversible: bool
    providers: list[str]


class SkillRegistryResponse(BaseModel):
    skills: list[SkillRegistryEntryInfo]
    capabilities: list[SkillRegistryCapabilityInfo]


class PersonalSkillInfo(BaseModel):
    id: str
    name: str
    display_name: str
    description: str = ""
    content: str = ""
    version: str = "1.0.0"
    source: Literal["personal"] = "personal"
    is_system: Literal[False] = False
    created_at: str | None = None
    updated_at: str | None = None


class SkillCreateResponse(BaseModel):
    skill: PersonalSkillInfo


class SkillUpdateResponse(BaseModel):
    skill: PersonalSkillInfo


class WorkspaceInfo(BaseModel):
    id: str
    name: str
    appearance: dict[str, Any] = Field(default_factory=dict)
    createdAt: str | None = None
    updatedAt: str | None = None


class WorkspaceListResponse(BaseModel):
    workspaces: list[WorkspaceInfo] = Field(default_factory=list)


class WorkspaceResponse(BaseModel):
    workspace: WorkspaceInfo


class ArtifactInfo(BaseModel):
    id: str
    workspaceId: str
    name: str
    mimeType: str
    size: int
    source: Literal["upload", "agent"]
    taskId: str | None = None
    kind: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


class ArtifactListResponse(BaseModel):
    artifacts: list[ArtifactInfo] = Field(default_factory=list)


class ArtifactResponse(BaseModel):
    artifact: ArtifactInfo


class AgentTaskCreateResponse(BaseModel):
    id: str
    status: str
    error: str | None = None


class AgentTaskListItemInfo(BaseModel):
    id: str
    prompt: str
    title: str = ""
    status: str
    intent: dict[str, Any] = Field(default_factory=dict)
    is_pinned: bool = False
    is_unread: bool = False
    deleted_at: str | None = None
    resources: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class AgentTaskListResponse(BaseModel):
    tasks: list[AgentTaskListItemInfo] = Field(default_factory=list)


class AgentWorkItemInfo(BaseModel):
    id: str
    candidateId: str = ""
    capability: str = ""
    dependsOn: list[str] = Field(default_factory=list)
    status: str = "queued"
    planRevision: int = 0
    provider: str = ""
    payloadDigest: str | None = None


class AgentTaskRuntimeGraphSummary(BaseModel):
    id: str
    type: Literal["runtime-graph"] = "runtime-graph"
    taskId: str
    latestExecutionId: str | None = None
    status: str
    updatedAt: str | None = None


class AgentTaskExecutionInfo(BaseModel):
    id: str
    status: str
    trigger: str
    graph_version: str
    started_at: str | None = None
    ended_at: str | None = None


class AgentIntentInfo(BaseModel):
    topic: str = ""
    learning_objective: str | None = None
    learner_level: str | None = None
    course_context: str | None = None
    language: str | None = None
    target_duration_sec: float | None = None


class ArtifactSnapshotInfo(BaseModel):
    available: bool
    url: str = ""
    metadata: dict[str, Any] | None = None


class QuizArtifactInfo(BaseModel):
    available: bool
    data: dict[str, Any] | None = None


class AgentArtifactsInfo(BaseModel):
    lesson_intro: ArtifactSnapshotInfo
    lecture_deck: ArtifactSnapshotInfo
    quiz: QuizArtifactInfo
    visual: ArtifactSnapshotInfo


class AgentDeliveryInfo(BaseModel):
    order: list[str] = Field(default_factory=list)
    queue: list[dict[str, Any]] = Field(default_factory=list)
    cursor: int = 0


class QuizSubmissionSnapshotInfo(BaseModel):
    submission_id: str
    submitted_at: str | None = None
    total_score: float = 0.0
    total_points: int = 0
    per_question: list[dict[str, Any]] = Field(default_factory=list)
    handoff_reason: str = ""


class AgentRunInfo(BaseModel):
    agent: str
    capability: Any = None
    skill_id: Any = None
    runs: int = 0
    status: str = "pending"
    detail: str = ""


class AgentTaskSnapshotResponse(BaseModel):
    id: str
    status: str
    threadStatus: str = "open"
    prompt: str
    title: str = ""
    is_pinned: bool = False
    is_unread: bool = False
    deleted_at: str | None = None
    resources: list[dict[str, Any]] = Field(default_factory=list)
    graph_version: str
    current_execution_id: str | None = None
    latest_execution_id: str | None = None
    runtime_graph: AgentTaskRuntimeGraphSummary
    executions: list[AgentTaskExecutionInfo] = Field(default_factory=list)
    goal: dict[str, Any] = Field(default_factory=dict)
    goal_stack: list[Any] = Field(default_factory=list)
    runtime_status: str = ""
    turnStatus: str = ""
    goalStatus: str = "open"
    phase: str = ""
    executionMode: str = "normal"
    currentTurnId: str = ""
    planRevision: int = 0
    workItems: list[AgentWorkItemInfo] = Field(default_factory=list)
    plan: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    intent: AgentIntentInfo
    agents: dict[str, AgentRunInfo] = Field(default_factory=dict)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: AgentArtifactsInfo
    delivery: AgentDeliveryInfo
    quiz_submission: QuizSubmissionSnapshotInfo | None = None
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AgentMessageResponse(BaseModel):
    status: str
    turnId: str = ""


class InteractionAnswerResponse(BaseModel):
    status: str
    interactionId: str


class AgentTaskMetaResponse(BaseModel):
    id: str
    title: str | None = ""
    is_pinned: bool = False
    is_unread: bool = False
    resources: list[dict[str, Any]] = Field(default_factory=list)


class AgentTaskDeleteResponse(BaseModel):
    id: str
    deleted_at: str | None = None


class AgentTaskRestoreResponse(BaseModel):
    id: str
    deleted_at: None = None


class AgentTaskForkResponse(BaseModel):
    id: str
    status: str


class AgentTaskCancelResponse(BaseModel):
    id: str
    status: str


class QuizSubmissionResponse(BaseModel):
    status: str
    submission: QuizSubmissionSnapshotInfo | None = None


class ConfirmWorkResponse(BaseModel):
    status: str
    workItemId: str
    payloadDigest: str | None = None


class AckDeliveryResponse(BaseModel):
    artifact: str
    status: str | None = None
    cursor: int = 0
    delivery: list[dict[str, Any]] = Field(default_factory=list)


class AgentDecisionsResponse(BaseModel):
    decisions: list[dict[str, Any]] = Field(default_factory=list)


class AgentEvidenceResponse(BaseModel):
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class AgentTaskEventsResponse(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)
    protocol: Literal["v1"]


class NativeExecutionNodeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    label: str
    kind: str
    capability: str
    provider: str | None = None
    status: str
    step: int
    taskId: str | None = None
    namespace: Any = None
    details: dict[str, Any] = Field(default_factory=dict)
    output: Any = None


class NativeExecutionDependencyResponse(BaseModel):
    id: str
    sourceNodeId: str
    targetNodeId: str
    kind: str
    status: str
    label: str


class NativeExecutionSnapshotResponse(BaseModel):
    schemaVersion: Literal["lingxilearn.execution.v1"]
    executionId: str
    taskId: str
    graphVersion: str
    status: str
    paused: bool = False
    terminal: bool = False
    nodes: dict[str, NativeExecutionNodeResponse] = Field(default_factory=dict)
    dependencies: list[NativeExecutionDependencyResponse] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    groups: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeGraphResponse(BaseModel):
    id: str
    type: Literal["runtime-graph"] = "runtime-graph"
    taskId: str
    latestExecutionId: str | None = None
    status: str
    updatedAt: str | None = None
    executionSnapshot: NativeExecutionSnapshotResponse | None = None
    executionGraph: dict[str, Any] = Field(default_factory=dict)


class SchedulePermissionResult(BaseModel):
    proposalId: str
    decision: str
    applied: bool = False
    status: str = "unknown"
    scope: Any = None


class SchedulePermissionResponse(BaseModel):
    success: bool
    results: list[SchedulePermissionResult] = Field(default_factory=list)
