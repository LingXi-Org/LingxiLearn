"""Public REST wire models for the Lingxi-native FastAPI surface.

These Pydantic models are the single source of truth for the REST contract
(issue #41): each model is bound to a real endpoint via ``response_model=...``
so ``app.openapi()`` expresses exactly what the wire carries.  The TypeScript
client contract under ``web/lib/api/contracts/lingxi/generated/`` is produced
from that OpenAPI document by ``web/scripts/generate-rest-contracts.ts`` — it
is never hand-maintained.

Modelling rules:

- A model declares every key the handler actually returns, no more and no
  less.  Free-form JSON sub-documents (row values, metadata payloads, runtime
  state projections) stay ``dict[str, Any]`` on purpose: that is the wire
  truth, not modelling laziness.
- Datetimes are already rendered as ISO strings by the ``_*_public``
  serializers, so the wire type is ``str`` (or ``str | None``) — never
  ``datetime``.  Frontend domain adapters may re-parse them.
- Fields that are always present are required; fields some branches omit use
  ``None`` defaults so response validation stays total.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------


class SuccessResponse(BaseModel):
    success: bool


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Health & catalogue
# ---------------------------------------------------------------------------


class HealthAgentInfo(BaseModel):
    configured: bool
    model: str


class HealthResponse(BaseModel):
    status: str
    database: bool
    brain: str
    agent: HealthAgentInfo
    packs: list[str]
    tools: int


class PackConceptInfo(BaseModel):
    id: str
    title: str
    summary: str
    requires: list[str]


class PackMissionInfo(BaseModel):
    id: str
    title: str
    subtitle: str
    summary: str
    why_not_chat: str
    concepts: list[str]
    estimated_minutes: int
    steps: int


class PackInfo(BaseModel):
    id: str
    title: str
    version: str
    description: str
    concepts: list[PackConceptInfo]
    missions: list[PackMissionInfo]


class PacksResponse(BaseModel):
    packs: list[PackInfo]


class NativeSkillInfo(BaseModel):
    """Union of the registry-backed and personal skill wire shapes.

    The ``/skills`` catalogue merges two sources; fields present in only one
    source stay optional so the merged list remains one schema.
    """

    id: str
    name: str = ""
    display_name: str = ""
    description: str | None = None
    version: str = ""
    license: str | None = None
    compatibility: str | None = None
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
    """Machine view of one registry row (``skill_dict`` wire shape)."""

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


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


SessionStatus = Literal[
    "created", "running", "awaiting_learner", "done", "failed", "cancelled"
]


class SessionCreateResponse(BaseModel):
    id: str
    mission_id: str
    pack_id: str
    status: str


class AnswerResponse(BaseModel):
    status: str


class SessionMissionInfo(BaseModel):
    id: str = ""
    title: str = ""
    subtitle: str = ""
    why_not_chat: str = ""
    concepts: list[str] = Field(default_factory=list)


class LearningProfileSystemInfo(BaseModel):
    confidence: float = 0.0
    evidence_count: int = 0
    misconceptions: list[Any] = Field(default_factory=list)
    prerequisites: list[Any] = Field(default_factory=list)
    difficulty: float = 0.0
    review_priority: float = 0.0
    stability: float = 0.0
    source_agent: str | None = None
    revision: int = 0
    override_flag: bool = False
    last_evidence_seq: int = 0


class LearningProfileRowInfo(BaseModel):
    knowledge_point_id: str
    knowledge_point: str
    mastery: float = 0.0
    learning_state: str | None = None
    progress: float = 0.0
    my_questions: list[Any] = Field(default_factory=list)
    recent_performance: dict[str, Any] = Field(default_factory=dict)
    last_studied_at: str | None = None
    review_due_at: str | None = None
    next_step: dict[str, Any] = Field(default_factory=dict)
    system: LearningProfileSystemInfo = Field(default_factory=LearningProfileSystemInfo)
    updated_at: str | None = None


class SessionInterruptInfo(BaseModel):
    id: Any = None
    resumable: bool = True
    value: dict[str, Any] = Field(default_factory=dict)


class SessionSnapshotResponse(BaseModel):
    """The runtime-truth session snapshot (see ``Service.snapshot``)."""

    id: str
    status: str = "created"
    error: str | None = None
    pack_id: str = ""
    pack_version: str = ""
    mission: SessionMissionInfo = Field(default_factory=SessionMissionInfo)
    runtime_status: str = ""
    goal: dict[str, Any] = Field(default_factory=dict)
    goal_stack: list[Any] = Field(default_factory=list)
    plan: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    profile: list[LearningProfileRowInfo] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    interrupts: list[SessionInterruptInfo] = Field(default_factory=list)


class SessionListItemInfo(BaseModel):
    id: str
    mission_id: str
    pack_id: str
    status: str
    created_at: str | None = None


class MasteryResponse(BaseModel):
    mastery: dict[str, float] = Field(default_factory=dict)
    sessions: list[SessionListItemInfo] = Field(default_factory=list)


class PreferencesResponse(BaseModel):
    preferences: dict[str, Any] = Field(default_factory=dict)


class ContextResponse(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    mastery: dict[str, float] = Field(default_factory=dict)
    misconceptions: list[dict[str, Any]] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)


class LearningProfileColumns(BaseModel):
    learner: list[str]
    system: list[str]


class LearningProfileResponse(BaseModel):
    profile: list[LearningProfileRowInfo] = Field(default_factory=list)
    columns: LearningProfileColumns


class ProfileChangeResponse(BaseModel):
    learner_id: str
    knowledge_point_id: str
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    source_agent: str = ""
    reason: str = ""


# ---------------------------------------------------------------------------
# Agent tasks
# ---------------------------------------------------------------------------


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
    type: str = "runtime-graph"
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
    """The runtime-truth agent task snapshot (see ``Service.agent_task_snapshot``)."""

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


class AttachmentUploadResponse(BaseModel):
    key: str
    path: str
    filename: str
    media_type: str
    size: int


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
    """JSON catch-up view of the durable agent event log (``format=json``)."""

    events: list[dict[str, Any]] = Field(default_factory=list)


class RuntimeGraphResponse(BaseModel):
    id: str
    type: str = "runtime-graph"
    taskId: str
    latestExecutionId: str | None = None
    status: str
    updatedAt: str | None = None
    workflowState: dict[str, Any] = Field(default_factory=dict)
    executionGraph: dict[str, Any] = Field(default_factory=dict)


class CopilotToolPermissionResult(BaseModel):
    toolCallId: str
    decision: str
    applied: bool = False
    status: str = "unknown"
    scope: Any = None


class CopilotToolPermissionResponse(BaseModel):
    success: bool
    results: list[CopilotToolPermissionResult] = Field(default_factory=list)


class LearningRecordResponse(BaseModel):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Workspaces & pins
# ---------------------------------------------------------------------------


class WorkspaceOwnerBillingInfo(BaseModel):
    plan: str = "internal"
    isPaid: bool = False
    isPro: bool = False


class WorkspaceInfo(BaseModel):
    id: str
    workspaceId: str
    name: str
    ownerId: str
    organizationId: str | None = None
    slug: str
    workspaceMode: str = "personal"
    role: str = "admin"
    membershipId: str
    permissions: str = "admin"
    appearance: dict[str, Any] = Field(default_factory=dict)
    ownerBilling: WorkspaceOwnerBillingInfo = Field(
        default_factory=WorkspaceOwnerBillingInfo
    )
    createdAt: str | None = None
    updatedAt: str | None = None


class WorkspaceListResponse(BaseModel):
    workspaces: list[WorkspaceInfo] = Field(default_factory=list)
    lastActiveWorkspaceId: str | None = None
    pinnedWorkspaceIds: list[str] = Field(default_factory=list)
    creationPolicy: dict[str, Any] | None = None


class WorkspaceResponse(BaseModel):
    workspace: WorkspaceInfo
    data: WorkspaceInfo


class WorkspaceMemberInfo(BaseModel):
    userId: str
    name: str
    image: str | None = None


class WorkspaceMembersResponse(BaseModel):
    members: list[WorkspaceMemberInfo] = Field(default_factory=list)


class WorkspacePermissionUserInfo(BaseModel):
    userId: str
    email: str
    name: str
    image: str | None = None
    permissionType: str = "admin"
    isExternal: bool = False
    joinedAt: str | None = None
    roleSource: str = "owner"
    isBilledAccount: bool = True


class WorkspacePermissionViewerInfo(BaseModel):
    userId: str
    isAdmin: bool = True
    permissionType: str = "admin"


class WorkspacePermissionsResponse(BaseModel):
    users: list[WorkspacePermissionUserInfo] = Field(default_factory=list)
    total: int = 0
    viewer: WorkspacePermissionViewerInfo


class PinnedItemInfo(BaseModel):
    id: str
    userId: str
    workspaceId: str
    resourceType: str
    resourceId: str
    pinnedAt: str | None = None


class PinnedItemsResponse(BaseModel):
    pinnedItems: list[PinnedItemInfo] = Field(default_factory=list)


class PinnedItemResponse(BaseModel):
    pinnedItem: PinnedItemInfo


# ---------------------------------------------------------------------------
# Workspace folders & files
# ---------------------------------------------------------------------------


class WorkspaceFolderInfo(BaseModel):
    """Exact ``_folder_public`` wire shape (no ``archived`` key on the wire)."""

    id: str
    workspaceId: str
    userId: str
    name: str
    parentId: str | None = None
    path: str
    sortOrder: int = 0
    deletedAt: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


class WorkspaceFoldersResponse(BaseModel):
    success: bool = True
    folders: list[WorkspaceFolderInfo] = Field(default_factory=list)
    data: list[WorkspaceFolderInfo] = Field(default_factory=list)


class WorkspaceFolderResponse(BaseModel):
    success: bool = True
    folder: WorkspaceFolderInfo


class WorkspaceFileInfo(BaseModel):
    """Exact ``_file_public`` wire shape — the public file DTO, never the ORM row."""

    id: str
    workspaceId: str
    name: str
    key: str
    path: str
    url: str
    size: int = 0
    type: str
    mimeType: str
    width: int | None = None
    height: int | None = None
    uploadedBy: str = "learner"
    folderId: str | None = None
    folderPath: str = "/"
    uploadedByEmail: str = "learner@lingxilearn.local"
    deletedAt: str | None = None
    uploadedAt: str | None = None
    updatedAt: str | None = None
    storageContext: str = "workspace"
    context: str = "workspace"
    readOnly: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceFilesResponse(BaseModel):
    success: bool = True
    files: list[WorkspaceFileInfo] = Field(default_factory=list)


class WorkspaceFileResponse(BaseModel):
    success: bool = True
    file: WorkspaceFileInfo
    data: WorkspaceFileInfo | None = None


class WorkspaceFileContentResponse(BaseModel):
    success: bool = True
    content: str
    encoding: str
    file: WorkspaceFileInfo


class MoveItemsResult(BaseModel):
    files: int = 0
    folders: int = 0


class MoveItemsResponse(BaseModel):
    success: bool = True
    movedItems: MoveItemsResult


class DeletedItemsResult(BaseModel):
    files: int = 0
    folders: int = 0


class FolderArchiveResponse(BaseModel):
    success: bool = True
    deletedItems: DeletedItemsResult = Field(default_factory=DeletedItemsResult)


class FolderRestoreResponse(BaseModel):
    success: bool = True
    folder: WorkspaceFolderInfo
    restoredItems: DeletedItemsResult = Field(default_factory=DeletedItemsResult)


class FileDownloadUrlResponse(BaseModel):
    success: bool = True
    downloadUrl: str
    viewerUrl: str
    fileName: str
    expiresIn: int | None = None


class StorageStatusResponse(BaseModel):
    cloudConfigured: bool = False


class UsageLimitsResponse(BaseModel):
    success: bool = True
    rateLimit: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    storage: dict[str, Any] = Field(default_factory=dict)


# Upload sessions (local single-process transfer)


class UploadSessionInfo(BaseModel):
    id: str
    purpose: str = "workspace_file"
    status: str
    name: str
    contentType: str
    size: int
    expiresAt: str
    error: str | None = None
    result: dict[str, Any] | None = None


class UploadTransferInfo(BaseModel):
    method: str = "put"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    expiresAt: str


class CreateUploadData(BaseModel):
    session: UploadSessionInfo
    uploadToken: str
    transfer: UploadTransferInfo


class CreateUploadResponse(BaseModel):
    data: CreateUploadData


class UploadPartInfo(BaseModel):
    partNumber: int
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    expiresAt: str


class UploadPartsData(BaseModel):
    parts: list[UploadPartInfo] = Field(default_factory=list)


class UploadPartsResponse(BaseModel):
    data: UploadPartsData


class UploadCompletedInfo(BaseModel):
    id: str
    purpose: str = "workspace_file"
    status: str
    name: str
    contentType: str
    size: int
    expiresAt: str
    error: str | None = None
    result: dict[str, Any] | None = None


class UploadStateResponse(BaseModel):
    data: UploadCompletedInfo


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class TableColumnInfo(BaseModel):
    id: str
    name: str
    key: str
    type: str = "string"
    position: int = 0
    required: bool = False
    unique: bool = False
    options: list[Any] = Field(default_factory=list)
    multiple: bool = False
    currencyCode: str | None = None


class TableLocksInfo(BaseModel):
    schemaLocked: bool = False
    insertLocked: bool = False
    updateLocked: bool = False
    deleteLocked: bool = False


class TableSchemaInfo(BaseModel):
    columns: list[TableColumnInfo] = Field(default_factory=list)


class WorkspaceTableInfo(BaseModel):
    """Exact ``_table_public`` wire shape."""

    id: str
    name: str
    description: str = ""
    workspaceId: str
    folderId: str | None = None
    schema_: TableSchemaInfo = Field(default_factory=TableSchemaInfo, alias="schema")
    columns: list[TableColumnInfo] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    rowCount: int = 0
    totalRows: int = 0
    maxRows: int = 100_000
    createdBy: str = "lingxi-user"
    locks: TableLocksInfo = Field(default_factory=TableLocksInfo)
    archivedAt: str | None = None
    archived: bool = False
    createdAt: str | None = None
    updatedAt: str | None = None

    model_config = {"populate_by_name": True}


class TableListData(BaseModel):
    tables: list[WorkspaceTableInfo] = Field(default_factory=list)
    totalCount: int = 0


class TableListResponse(BaseModel):
    success: bool = True
    data: TableListData
    tables: list[WorkspaceTableInfo] = Field(default_factory=list)
    totalCount: int = 0


class TableData(BaseModel):
    table: WorkspaceTableInfo
    message: str | None = None


class TableResponse(BaseModel):
    success: bool = True
    data: TableData


class TableMessageData(BaseModel):
    message: str = ""


class TableMessageResponse(BaseModel):
    success: bool = True
    data: TableMessageData = Field(default_factory=TableMessageData)


class TableRowInfo(BaseModel):
    id: str
    data: dict[str, Any] = Field(default_factory=dict)
    values: dict[str, Any] = Field(default_factory=dict)
    executions: dict[str, Any] = Field(default_factory=dict)
    position: int = 0
    createdAt: str | None = None
    updatedAt: str | None = None


class TableRowsData(BaseModel):
    rows: list[TableRowInfo] = Field(default_factory=list)
    rowCount: int = 0
    totalCount: int = 0
    limit: int = 100
    offset: int = 0
    nextCursor: str | None = None


class TableRowsResponse(BaseModel):
    success: bool = True
    data: TableRowsData


class TableRowsQueryData(BaseModel):
    rows: list[TableRowInfo] = Field(default_factory=list)
    rowCount: int = 0
    totalCount: int = 0
    nextCursor: str | None = None


class TableRowsQueryResponse(BaseModel):
    success: bool = True
    data: TableRowsQueryData


class TableRowMatchInfo(BaseModel):
    ordinal: int
    rowId: str
    column: str


class TableRowsFindData(BaseModel):
    matches: list[TableRowMatchInfo] = Field(default_factory=list)
    truncated: bool = False


class TableRowsFindResponse(BaseModel):
    success: bool = True
    data: TableRowsFindData


class TableRowsCreateData(BaseModel):
    rows: list[TableRowInfo] = Field(default_factory=list)
    row: TableRowInfo | None = None


class TableRowsCreateResponse(BaseModel):
    success: bool = True
    data: TableRowsCreateData


class TableRowData(BaseModel):
    row: TableRowInfo


class TableRowResponse(BaseModel):
    success: bool = True
    data: TableRowData


class TableRowsUpsertData(BaseModel):
    rows: list[TableRowInfo] = Field(default_factory=list)


class TableRowsUpsertResponse(BaseModel):
    success: bool = True
    data: TableRowsUpsertData


class TableEmptyDataResponse(BaseModel):
    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)


class TableColumnsData(BaseModel):
    columns: list[TableColumnInfo] = Field(default_factory=list)


class TableColumnsResponse(BaseModel):
    success: bool = True
    data: TableColumnsData


class TableViewInfo(BaseModel):
    id: str
    tableId: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    isDefault: bool = False
    createdBy: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


class TableViewsData(BaseModel):
    views: list[TableViewInfo] = Field(default_factory=list)


class TableViewsResponse(BaseModel):
    success: bool = True
    data: TableViewsData


class TableViewData(BaseModel):
    view: TableViewInfo


class TableViewResponse(BaseModel):
    success: bool = True
    data: TableViewData


class TableViewDeletedData(BaseModel):
    deleted: bool = True


class TableViewDeletedResponse(BaseModel):
    success: bool = True
    data: TableViewDeletedData = Field(default_factory=TableViewDeletedData)


class TableImportCsvTableInfo(BaseModel):
    id: str
    name: str


class TableImportCsvData(BaseModel):
    table: TableImportCsvTableInfo
    importedRows: int = 0


class TableImportCsvResponse(BaseModel):
    success: bool = True
    data: TableImportCsvData


class TableImportRowsData(BaseModel):
    importedRows: int = 0


class TableImportRowsResponse(BaseModel):
    success: bool = True
    data: TableImportRowsData


# ---------------------------------------------------------------------------
# Knowledge
# ---------------------------------------------------------------------------


class KnowledgeChunkingConfigInfo(BaseModel):
    maxSize: int = 1200
    minSize: int = 1
    overlap: int = 0
    strategy: str = "text"


class KnowledgeBaseInfo(BaseModel):
    """Exact ``_knowledge_base_public`` wire shape."""

    id: str
    userId: str
    name: str
    description: str = ""
    workspaceId: str
    documentCount: int = 0
    docCount: int = 0
    fileCount: int = 0
    tokenCount: int = 0
    embeddingModel: str = "none"
    embeddingDimension: int = 0
    chunkingConfig: KnowledgeChunkingConfigInfo = Field(
        default_factory=KnowledgeChunkingConfigInfo
    )
    folderId: str | None = None
    deletedAt: str | None = None
    archived: bool = False
    createdAt: str | None = None
    updatedAt: str | None = None


class KnowledgeBasesResponse(BaseModel):
    success: bool = True
    data: list[KnowledgeBaseInfo] = Field(default_factory=list)
    knowledgeBases: list[KnowledgeBaseInfo] = Field(default_factory=list)


class KnowledgeBaseResponse(BaseModel):
    success: bool = True
    data: KnowledgeBaseInfo
    knowledgeBase: KnowledgeBaseInfo


class KnowledgeMessageResponse(BaseModel):
    success: bool = True
    data: TableMessageData = Field(default_factory=TableMessageData)


class KnowledgeDocumentInfo(BaseModel):
    """Exact ``_document_public`` wire shape, tag slots included."""

    id: str
    knowledgeBaseId: str
    name: str
    filename: str
    fileUrl: str
    fileSize: int = 0
    mimeType: str
    chunkCount: int = 0
    tokenCount: int = 0
    characterCount: int = 0
    processingStatus: str = "completed"
    processingError: str | None = None
    enabled: bool = True
    uploadedAt: str | None = None
    content: str = ""
    size: int = 0
    status: str = "ready"
    archived: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    readOnly: bool = False
    tag1: Any = None
    tag2: Any = None
    tag3: Any = None
    tag4: Any = None
    tag5: Any = None
    tag6: Any = None
    tag7: Any = None
    number1: Any = None
    number2: Any = None
    number3: Any = None
    number4: Any = None
    number5: Any = None
    date1: Any = None
    date2: Any = None
    boolean1: Any = None
    boolean2: Any = None
    boolean3: Any = None
    connectorId: Any = None
    connectorType: Any = None
    sourceUrl: Any = None
    createdAt: str | None = None
    updatedAt: str | None = None


class KnowledgePaginationInfo(BaseModel):
    total: int = 0
    limit: int = 50
    offset: int = 0
    hasMore: bool = False


class KnowledgeDocumentsData(BaseModel):
    documents: list[KnowledgeDocumentInfo] = Field(default_factory=list)
    pagination: KnowledgePaginationInfo = Field(default_factory=KnowledgePaginationInfo)


class KnowledgeDocumentsResponse(BaseModel):
    success: bool = True
    data: KnowledgeDocumentsData
    documents: list[KnowledgeDocumentInfo] = Field(default_factory=list)


class KnowledgeDocumentResponse(BaseModel):
    success: bool = True
    data: KnowledgeDocumentInfo
    document: KnowledgeDocumentInfo


class KnowledgeSearchResultInfo(BaseModel):
    document: KnowledgeDocumentInfo
    score: float = 0.0
    snippet: str = ""


class KnowledgeSearchResponse(BaseModel):
    success: bool = True
    data: list[KnowledgeSearchResultInfo] = Field(default_factory=list)
    results: list[KnowledgeSearchResultInfo] = Field(default_factory=list)


class KnowledgeChunkInfo(BaseModel):
    """Exact ``_chunk_public`` wire shape, tag slots included."""

    id: str
    chunkIndex: int = 0
    content: str = ""
    contentLength: int = 0
    tokenCount: int = 0
    enabled: bool = True
    startOffset: int = 0
    endOffset: int = 0
    tag1: Any = None
    tag2: Any = None
    tag3: Any = None
    tag4: Any = None
    tag5: Any = None
    tag6: Any = None
    tag7: Any = None
    number1: Any = None
    number2: Any = None
    number3: Any = None
    number4: Any = None
    number5: Any = None
    date1: Any = None
    date2: Any = None
    boolean1: Any = None
    boolean2: Any = None
    boolean3: Any = None
    createdAt: str | None = None
    updatedAt: str | None = None


class KnowledgeChunksResponse(BaseModel):
    success: bool = True
    data: list[KnowledgeChunkInfo] = Field(default_factory=list)
    chunks: list[KnowledgeChunkInfo] = Field(default_factory=list)
    pagination: KnowledgePaginationInfo


class KnowledgeChunkResponse(BaseModel):
    success: bool = True
    data: KnowledgeChunkInfo


class KnowledgeTagInfo(BaseModel):
    id: str
    tagSlot: str = ""
    displayName: str
    name: str
    fieldType: str = "text"
    createdAt: str | None = None
    updatedAt: str | None = None


class KnowledgeTagsResponse(BaseModel):
    success: bool = True
    data: list[KnowledgeTagInfo] = Field(default_factory=list)
    tags: list[KnowledgeTagInfo] = Field(default_factory=list)


class KnowledgeTagListResponse(BaseModel):
    """Document-scoped tag list: only ``data`` is present on the wire."""

    success: bool = True
    data: list[KnowledgeTagInfo] = Field(default_factory=list)


class KnowledgeTagResponse(BaseModel):
    success: bool = True
    data: KnowledgeTagInfo


class KnowledgeTagUsageDocumentInfo(BaseModel):
    id: str
    name: str
    tagValue: str = ""


class KnowledgeTagUsageInfo(BaseModel):
    tagName: str
    tagSlot: str = ""
    documentCount: int = 0
    documents: list[KnowledgeTagUsageDocumentInfo] = Field(default_factory=list)


class KnowledgeTagUsageResponse(BaseModel):
    success: bool = True
    data: list[KnowledgeTagUsageInfo] = Field(default_factory=list)


class KnowledgeNextSlotData(BaseModel):
    nextAvailableSlot: str | None = None
    fieldType: str
    usedSlots: list[str] = Field(default_factory=list)
    totalSlots: int = 0
    availableSlots: int = 0


class KnowledgeNextSlotResponse(BaseModel):
    success: bool = True
    data: KnowledgeNextSlotData


class DocumentTagSaveData(BaseModel):
    created: list[KnowledgeTagInfo] = Field(default_factory=list)
    updated: list[KnowledgeTagInfo] = Field(default_factory=list)
    errors: list[Any] = Field(default_factory=list)


class DocumentTagSaveResponse(BaseModel):
    success: bool = True
    data: DocumentTagSaveData


class KnowledgeDocumentUpsertCreatedInfo(BaseModel):
    documentId: str
    filename: str
    status: str = "pending"


class KnowledgeDocumentUpsertData(BaseModel):
    documentsCreated: list[KnowledgeDocumentUpsertCreatedInfo] = Field(default_factory=list)
    isUpdate: bool = False
    previousDocumentId: str | None = None
    processingMethod: str = "background"
    processingConfig: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentUpsertResponse(BaseModel):
    success: bool = True
    data: KnowledgeDocumentUpsertData


class KnowledgeBulkDocumentUpdateInfo(BaseModel):
    id: str
    enabled: bool


class KnowledgeBulkDocumentsData(BaseModel):
    operation: str
    successCount: int = 0
    failedCount: int = 0
    updatedDocuments: list[KnowledgeBulkDocumentUpdateInfo] = Field(default_factory=list)


class KnowledgeBulkDocumentsResponse(BaseModel):
    success: bool = True
    data: KnowledgeBulkDocumentsData


class KnowledgeBulkChunksData(BaseModel):
    operation: str
    successCount: int = 0
    errorCount: int = 0
    processed: int = 0
    errors: list[Any] = Field(default_factory=list)


class KnowledgeBulkChunksResponse(BaseModel):
    success: bool = True
    data: KnowledgeBulkChunksData


class KnowledgeDocumentSummaryInfo(BaseModel):
    id: str
    knowledgeBaseId: str
    filename: str
    fileSize: int = 0
    mimeType: str
    processingStatus: str = "completed"
    chunkCount: int = 0
    tokenCount: int = 0
    characterCount: int = 0
    enabled: bool = True
    createdAt: str | None = None


class KnowledgeUploadSessionInfo(BaseModel):
    id: str
    knowledgeBaseId: str
    status: str
    name: str
    contentType: str
    size: int
    expiresAt: str
    error: str | None = None
    document: KnowledgeDocumentSummaryInfo | None = None


class KnowledgeUploadCreateData(BaseModel):
    session: KnowledgeUploadSessionInfo
    uploadToken: str
    transfer: UploadTransferInfo


class KnowledgeUploadCreateResponse(BaseModel):
    data: KnowledgeUploadCreateData


class KnowledgeUploadStateResponse(BaseModel):
    data: KnowledgeUploadSessionInfo


# ---------------------------------------------------------------------------
# Personal skills (workspace skill CRUD)
# ---------------------------------------------------------------------------


class PersonalSkillInfo(BaseModel):
    """Exact ``_skill_public`` wire shape."""

    id: str
    name: str
    display_name: str
    description: str = ""
    content: str = ""
    version: str = "1.0.0"
    source: str = "personal"
    is_system: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class SkillCreateResponse(BaseModel):
    skills: list[PersonalSkillInfo] = Field(default_factory=list)
    skill: PersonalSkillInfo
    data: PersonalSkillInfo


class SkillUpdateResponse(BaseModel):
    skill: PersonalSkillInfo
    data: PersonalSkillInfo


# ---------------------------------------------------------------------------
# Settings / account / billing
# ---------------------------------------------------------------------------


class IntegrationAvailabilityInfo(BaseModel):
    type: str
    state: str
    oauthAvailable: bool = False


class AllowedIntegrationsResponse(BaseModel):
    """``null`` means no env-derived allowlist (unrestricted)."""

    allowedIntegrations: list[str] | None = None
    integrationAvailability: list[IntegrationAvailabilityInfo] = Field(default_factory=list)


class AllowedProvidersResponse(BaseModel):
    blacklistedProviders: list[str] = Field(default_factory=list)


class VoiceSettingsResponse(BaseModel):
    sttAvailable: bool = False


class TelemetryResponse(BaseModel):
    success: bool
    forwarded: bool = False


class UserProfileInfo(BaseModel):
    id: str
    name: str
    email: str
    image: str | None = None
    emailVerified: bool = False


class UserProfileResponse(BaseModel):
    user: UserProfileInfo


class UserProfileUpdateResponse(BaseModel):
    success: bool
    user: UserProfileInfo


class UserSettingsInfo(BaseModel):
    """Exact ``_settings_public`` wire shape."""

    theme: str = "system"
    autoConnect: bool = True
    telemetryEnabled: bool = True
    emailPreferences: dict[str, Any] = Field(default_factory=dict)
    billingUsageNotificationsEnabled: bool = True
    superUserModeEnabled: bool = False
    mothershipEnvironment: str = "default"
    errorNotificationsEnabled: bool = True
    snapToGridSize: float = 0
    showActionBar: bool = True
    copilotAutoAllowedTools: list[str] = Field(default_factory=list)
    timezone: str | None = None
    lastActiveWorkspaceId: str | None = None


class UserSettingsResponse(BaseModel):
    data: UserSettingsInfo


class UserSettingsUpdateResponse(BaseModel):
    success: bool
    data: UserSettingsInfo


class OrganizationsResponse(BaseModel):
    organizations: list[dict[str, Any]] = Field(default_factory=list)
    isMemberOfAnyOrg: bool = False


class BillingUsageInfo(BaseModel):
    current: int = 0
    limit: int = 0
    percentUsed: float = 0
    isWarning: bool = False
    isExceeded: bool = False
    billingPeriodStart: str | None = None
    billingPeriodEnd: str | None = None
    lastPeriodCost: float = 0
    lastPeriodCopilotCost: float = 0
    daysRemaining: int = 0
    copilotCost: float = 0


class BillingInfoData(BaseModel):
    type: str = "individual"
    plan: str = "internal"
    currentUsage: int = 0
    usageLimit: int = 0
    percentUsed: float = 0
    isWarning: bool = False
    isExceeded: bool = False
    daysRemaining: int = 0
    creditBalance: int = 0
    billingInterval: str = "month"
    isPaid: bool = False
    isPro: bool = False
    isTeam: bool = False
    isEnterprise: bool = False
    isOrgScoped: bool = False
    organizationId: str | None = None
    status: str = "inactive"
    seats: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    stripeSubscriptionId: str | None = None
    periodEnd: str | None = None
    cancelAtPeriodEnd: bool = False
    usage: BillingUsageInfo = Field(default_factory=BillingUsageInfo)
    billingBlocked: bool = False
    billingBlockedReason: str | None = None
    blockedByOrgOwner: bool = False
    upgradeWorkspaceId: str | None = None


class BillingInfoResponse(BaseModel):
    success: bool
    context: str = "user"
    data: BillingInfoData = Field(default_factory=BillingInfoData)


class BillingOrgData(BaseModel):
    organizationId: str
    organizationName: str = ""
    subscriptionState: str = "free"
    hasSubscription: bool = False
    subscriptionPlan: str = "internal"
    subscriptionStatus: str | None = None
    creditBalance: int = 0
    billingInterval: str = "month"
    cancelAtPeriodEnd: bool = False
    totalSeats: int = 1
    usedSeats: int = 1
    seatsCount: int = 1
    totalCurrentUsage: int = 0
    totalUsageLimit: int = 0
    minimumBillingAmount: float = 0
    averageUsagePerMember: float = 0
    billingPeriodStart: str | None = None
    billingPeriodEnd: str | None = None
    members: list[dict[str, Any]] = Field(default_factory=list)
    billingBlocked: bool = False
    billingBlockedReason: str | None = None
    blockedByOrgOwner: bool = False
    upgradeWorkspaceId: str | None = None


class BillingOrgResponse(BaseModel):
    success: bool
    context: str = "organization"
    data: BillingOrgData
    userRole: str = "owner"
    billingBlocked: bool = False
    billingBlockedReason: str | None = None
    blockedByOrgOwner: bool = False


class V2BillingPeriodInfo(BaseModel):
    start: str
    end: str


class V2BillingCreditsInfo(BaseModel):
    used: int = 0
    limit: int = 0
    remaining: int = 0


class V2BillingStorageInfo(BaseModel):
    usedBytes: int = 0
    limitBytes: int = 0
    percentUsed: float = 0


class V2BillingStatusData(BaseModel):
    workspaceId: str
    period: V2BillingPeriodInfo
    plan: str = "internal"
    status: str = "active"
    credits: V2BillingCreditsInfo = Field(default_factory=V2BillingCreditsInfo)
    storage: V2BillingStorageInfo = Field(default_factory=V2BillingStorageInfo)


class V2BillingStatusResponse(BaseModel):
    data: V2BillingStatusData


class V2BillingLogEntry(BaseModel):
    id: str
    createdAt: str | None = None
    source: str = ""
    workspaceId: str = "lingxi"
    workflow: None = None
    runId: None = None
    creditCost: float = 0


class V2BillingLogsResponse(BaseModel):
    data: list[V2BillingLogEntry] = Field(default_factory=list)
    nextCursor: str | None = None
