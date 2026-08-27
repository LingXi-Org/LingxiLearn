// AUTO-GENERATED — do not edit by hand.
// Regenerate:  python scripts/export_openapi.py && bun run web/scripts/generate-rest-contracts.ts
// eslint-disable @typescript-eslint/no-explicit-any

import { z } from "zod";

export const AckDeliveryResponseSchema = z.object({
  artifact: z.string(),
  cursor: z.number().int().default(0),
  delivery: z.array(z.record(z.string(), z.unknown())),
  status: z.string().nullable(),
});
export type AckDeliveryResponse = z.output<typeof AckDeliveryResponseSchema>;

export const ArtifactSnapshotInfoSchema = z.object({
  available: z.boolean(),
  metadata: z.record(z.string(), z.unknown()).nullable(),
  url: z.string().default(""),
});
export type ArtifactSnapshotInfo = z.output<typeof ArtifactSnapshotInfoSchema>;

export const QuizArtifactInfoSchema = z.object({
  available: z.boolean(),
  data: z.record(z.string(), z.unknown()).nullable(),
});
export type QuizArtifactInfo = z.output<typeof QuizArtifactInfoSchema>;

export const AgentArtifactsInfoSchema = z.object({
  lecture_deck: ArtifactSnapshotInfoSchema,
  lesson_intro: ArtifactSnapshotInfoSchema,
  quiz: QuizArtifactInfoSchema,
  visual: ArtifactSnapshotInfoSchema,
});
export type AgentArtifactsInfo = z.output<typeof AgentArtifactsInfoSchema>;

export const AgentAttachmentUploadSchema = z.object({
  data: z.string().min(1),
  filename: z.string().min(1).max(255),
  media_type: z.string().max(128).default("application/octet-stream"),
  size: z.number().int().min(0).max(20971520),
});
export type AgentAttachmentUpload = z.output<typeof AgentAttachmentUploadSchema>;

export const AgentConfirmationSchema = z.object({
  approve: z.boolean(),
  idempotency_key: z.string().min(1).max(192),
  payload_digest: z.string().min(1).max(128),
  work_item_id: z.string().min(1).max(128),
});
export type AgentConfirmation = z.output<typeof AgentConfirmationSchema>;

export const AgentDecisionsResponseSchema = z.object({
  decisions: z.array(z.record(z.string(), z.unknown())),
});
export type AgentDecisionsResponse = z.output<typeof AgentDecisionsResponseSchema>;

export const AgentDeliveryInfoSchema = z.object({
  cursor: z.number().int().default(0),
  order: z.array(z.string()),
  queue: z.array(z.record(z.string(), z.unknown())),
});
export type AgentDeliveryInfo = z.output<typeof AgentDeliveryInfoSchema>;

export const AgentEvidenceResponseSchema = z.object({
  evidence: z.array(z.record(z.string(), z.unknown())),
});
export type AgentEvidenceResponse = z.output<typeof AgentEvidenceResponseSchema>;

export const AgentIntentInfoSchema = z.object({
  course_context: z.string().nullable(),
  language: z.string().nullable(),
  learner_level: z.string().nullable(),
  learning_objective: z.string().nullable(),
  target_duration_sec: z.number().nullable(),
  topic: z.string().default(""),
});
export type AgentIntentInfo = z.output<typeof AgentIntentInfoSchema>;

export const AgentInteractionAnswerRequestSchema = z.object({
  answers: z.array(z.record(z.string(), z.unknown())).min(1).max(20),
  idempotency_key: z.string().min(1).max(192).nullable(),
});
export type AgentInteractionAnswerRequest = z.output<typeof AgentInteractionAnswerRequestSchema>;

export const AgentMessageSchema = z.object({
  attachments: z.array(z.record(z.string(), z.unknown())).max(10),
  idempotency_key: z.string().min(1).max(192).nullable(),
  message: z.string().min(1).max(4000),
  resource_refs: z.array(z.record(z.string(), z.unknown())).max(100),
  skill_ids: z.array(z.string()).max(50),
});
export type AgentMessage = z.output<typeof AgentMessageSchema>;

export const AgentMessageResponseSchema = z.object({
  status: z.string(),
  turnId: z.string().default(""),
});
export type AgentMessageResponse = z.output<typeof AgentMessageResponseSchema>;

export const AgentRunInfoSchema = z.object({
  agent: z.string(),
  capability: z.unknown(),
  detail: z.string().default(""),
  runs: z.number().int().default(0),
  skill_id: z.unknown(),
  status: z.string().default("pending"),
});
export type AgentRunInfo = z.output<typeof AgentRunInfoSchema>;

export const AgentTaskCancelResponseSchema = z.object({
  id: z.string(),
  status: z.string(),
});
export type AgentTaskCancelResponse = z.output<typeof AgentTaskCancelResponseSchema>;

export const AgentTaskCreateResponseSchema = z.object({
  error: z.string().nullable(),
  id: z.string(),
  status: z.string(),
});
export type AgentTaskCreateResponse = z.output<typeof AgentTaskCreateResponseSchema>;

export const AgentTaskDeleteResponseSchema = z.object({
  deleted_at: z.string().nullable(),
  id: z.string(),
});
export type AgentTaskDeleteResponse = z.output<typeof AgentTaskDeleteResponseSchema>;

/** JSON catch-up view of the durable agent event log (``format=json``). */
export const AgentTaskEventsResponseSchema = z.object({
  events: z.array(z.record(z.string(), z.unknown())),
  protocol: z.string(),
});
export type AgentTaskEventsResponse = z.output<typeof AgentTaskEventsResponseSchema>;

export const AgentTaskExecutionInfoSchema = z.object({
  ended_at: z.string().nullable(),
  graph_version: z.string(),
  id: z.string(),
  started_at: z.string().nullable(),
  status: z.string(),
  trigger: z.string(),
});
export type AgentTaskExecutionInfo = z.output<typeof AgentTaskExecutionInfoSchema>;

export const AgentTaskForkResponseSchema = z.object({
  id: z.string(),
  status: z.string(),
});
export type AgentTaskForkResponse = z.output<typeof AgentTaskForkResponseSchema>;

export const AgentTaskListItemInfoSchema = z.object({
  created_at: z.string().nullable(),
  deleted_at: z.string().nullable(),
  id: z.string(),
  intent: z.record(z.string(), z.unknown()),
  is_pinned: z.boolean().default(false),
  is_unread: z.boolean().default(false),
  prompt: z.string(),
  resources: z.array(z.record(z.string(), z.unknown())),
  status: z.string(),
  title: z.string().default(""),
  updated_at: z.string().nullable(),
});
export type AgentTaskListItemInfo = z.output<typeof AgentTaskListItemInfoSchema>;

export const AgentTaskListResponseSchema = z.object({
  tasks: z.array(AgentTaskListItemInfoSchema),
});
export type AgentTaskListResponse = z.output<typeof AgentTaskListResponseSchema>;

export const AgentTaskMetaResponseSchema = z.object({
  id: z.string(),
  is_pinned: z.boolean().default(false),
  is_unread: z.boolean().default(false),
  resources: z.array(z.record(z.string(), z.unknown())),
  title: z.string().nullable().default(""),
});
export type AgentTaskMetaResponse = z.output<typeof AgentTaskMetaResponseSchema>;

export const AgentTaskMetadataPatchSchema = z.object({
  is_pinned: z.boolean().nullable(),
  is_unread: z.boolean().nullable(),
  resources: z.array(z.record(z.string(), z.unknown())).nullable(),
  title: z.string().max(4000).nullable(),
});
export type AgentTaskMetadataPatch = z.output<typeof AgentTaskMetadataPatchSchema>;

export const AgentTaskRestoreResponseSchema = z.object({
  deleted_at: z.unknown(),
  id: z.string(),
});
export type AgentTaskRestoreResponse = z.output<typeof AgentTaskRestoreResponseSchema>;

export const AgentTaskRuntimeGraphSummarySchema = z.object({
  id: z.string(),
  latestExecutionId: z.string().nullable(),
  status: z.string(),
  taskId: z.string(),
  type: z.string().default("runtime-graph"),
  updatedAt: z.string().nullable(),
});
export type AgentTaskRuntimeGraphSummary = z.output<typeof AgentTaskRuntimeGraphSummarySchema>;

export const QuizSubmissionSnapshotInfoSchema = z.object({
  handoff_reason: z.string().default(""),
  per_question: z.array(z.record(z.string(), z.unknown())),
  submission_id: z.string(),
  submitted_at: z.string().nullable(),
  total_points: z.number().int().default(0),
  total_score: z.number().default(0),
});
export type QuizSubmissionSnapshotInfo = z.output<typeof QuizSubmissionSnapshotInfoSchema>;

export const AgentWorkItemInfoSchema = z.object({
  candidateId: z.string().default(""),
  capability: z.string().default(""),
  dependsOn: z.array(z.string()),
  id: z.string(),
  payloadDigest: z.string().nullable(),
  planRevision: z.number().int().default(0),
  provider: z.string().default(""),
  status: z.string().default("queued"),
});
export type AgentWorkItemInfo = z.output<typeof AgentWorkItemInfoSchema>;

/** The runtime-truth agent task snapshot (see ``Service.agent_task_snapshot``). */
export const AgentTaskSnapshotResponseSchema = z.object({
  agents: z.record(z.string(), z.unknown()),
  artifacts: AgentArtifactsInfoSchema,
  budget: z.record(z.string(), z.unknown()),
  created_at: z.string().nullable(),
  current_execution_id: z.string().nullable(),
  currentTurnId: z.string().default(""),
  decisions: z.array(z.record(z.string(), z.unknown())),
  deleted_at: z.string().nullable(),
  delivery: AgentDeliveryInfoSchema,
  error: z.string().nullable(),
  executionMode: z.string().default("normal"),
  executions: z.array(AgentTaskExecutionInfoSchema),
  goal: z.record(z.string(), z.unknown()),
  goal_stack: z.array(z.unknown()),
  goalStatus: z.string().default("open"),
  graph_version: z.string(),
  id: z.string(),
  intent: AgentIntentInfoSchema,
  is_pinned: z.boolean().default(false),
  is_unread: z.boolean().default(false),
  latest_execution_id: z.string().nullable(),
  phase: z.string().default(""),
  plan: z.record(z.string(), z.unknown()),
  planRevision: z.number().int().default(0),
  prompt: z.string(),
  quiz_submission: QuizSubmissionSnapshotInfoSchema.nullable(),
  resources: z.array(z.record(z.string(), z.unknown())),
  runtime_graph: AgentTaskRuntimeGraphSummarySchema,
  runtime_status: z.string().default(""),
  status: z.string(),
  threadStatus: z.string().default("open"),
  title: z.string().default(""),
  turnStatus: z.string().default(""),
  updated_at: z.string().nullable(),
  workItems: z.array(AgentWorkItemInfoSchema),
});
export type AgentTaskSnapshotResponse = z.output<typeof AgentTaskSnapshotResponseSchema>;

export const AttachmentUploadResponseSchema = z.object({
  filename: z.string(),
  key: z.string(),
  media_type: z.string(),
  path: z.string(),
  size: z.number().int(),
});
export type AttachmentUploadResponse = z.output<typeof AttachmentUploadResponseSchema>;

export const Body_download_file_items_api_workspaces__workspace_id__files_download_getSchema = z.object({
  fileIds: z.array(z.string()).nullable(),
  folderIds: z.array(z.string()).nullable(),
});
export type Body_download_file_items_api_workspaces__workspace_id__files_download_get = z.output<typeof Body_download_file_items_api_workspaces__workspace_id__files_download_getSchema>;

export const ConfirmWorkResponseSchema = z.object({
  payloadDigest: z.string().nullable(),
  status: z.string(),
  workItemId: z.string(),
});
export type ConfirmWorkResponse = z.output<typeof ConfirmWorkResponseSchema>;

export const ContextResponseSchema = z.object({
  mastery: z.record(z.string(), z.unknown()),
  misconceptions: z.array(z.record(z.string(), z.unknown())),
  preferences: z.record(z.string(), z.unknown()),
  profile: z.record(z.string(), z.unknown()),
});
export type ContextResponse = z.output<typeof ContextResponseSchema>;

export const CreateAgentTaskSchema = z.object({
  attachments: z.array(z.record(z.string(), z.unknown())).max(10),
  idempotency_key: z.string().min(1).max(192).nullable(),
  prompt: z.string().min(1).max(4000),
  resource_refs: z.array(z.record(z.string(), z.unknown())).max(100),
  skill_ids: z.array(z.string()).max(50),
});
export type CreateAgentTask = z.output<typeof CreateAgentTaskSchema>;

export const UploadSessionInfoSchema = z.object({
  contentType: z.string(),
  error: z.string().nullable(),
  expiresAt: z.string(),
  id: z.string(),
  name: z.string(),
  purpose: z.string().default("workspace_file"),
  result: z.record(z.string(), z.unknown()).nullable(),
  size: z.number().int(),
  status: z.string(),
});
export type UploadSessionInfo = z.output<typeof UploadSessionInfoSchema>;

export const UploadTransferInfoSchema = z.object({
  expiresAt: z.string(),
  headers: z.record(z.string(), z.unknown()),
  method: z.string().default("put"),
  url: z.string(),
});
export type UploadTransferInfo = z.output<typeof UploadTransferInfoSchema>;

export const CreateUploadDataSchema = z.object({
  session: UploadSessionInfoSchema,
  transfer: UploadTransferInfoSchema,
  uploadToken: z.string(),
});
export type CreateUploadData = z.output<typeof CreateUploadDataSchema>;

export const CreateUploadResponseSchema = z.object({
  data: CreateUploadDataSchema,
});
export type CreateUploadResponse = z.output<typeof CreateUploadResponseSchema>;

export const DeletedItemsResultSchema = z.object({
  files: z.number().int().default(0),
  folders: z.number().int().default(0),
});
export type DeletedItemsResult = z.output<typeof DeletedItemsResultSchema>;

export const KnowledgeTagInfoSchema = z.object({
  createdAt: z.string().nullable(),
  displayName: z.string(),
  fieldType: z.string().default("text"),
  id: z.string(),
  name: z.string(),
  tagSlot: z.string().default(""),
  updatedAt: z.string().nullable(),
});
export type KnowledgeTagInfo = z.output<typeof KnowledgeTagInfoSchema>;

export const DocumentTagSaveDataSchema = z.object({
  created: z.array(KnowledgeTagInfoSchema),
  errors: z.array(z.unknown()),
  updated: z.array(KnowledgeTagInfoSchema),
});
export type DocumentTagSaveData = z.output<typeof DocumentTagSaveDataSchema>;

export const DocumentTagSaveResponseSchema = z.object({
  data: DocumentTagSaveDataSchema,
  success: z.boolean().default(true),
});
export type DocumentTagSaveResponse = z.output<typeof DocumentTagSaveResponseSchema>;

export const ExecutionMetadataResponseSchema = z.object({
  cost: z.unknown(),
  endedAt: z.string().nullable(),
  scheduledFor: z.string().nullable(),
  scheduleId: z.string().nullable(),
  startedAt: z.string().nullable(),
  totalDurationMs: z.number().int().nullable(),
  totalTokens: z.number().int().nullable(),
  trigger: z.string().nullable(),
});
export type ExecutionMetadataResponse = z.output<typeof ExecutionMetadataResponseSchema>;

export const NativeExecutionSnapshotResponseSchema = z.object({
  dependencies: z.array(z.record(z.string(), z.unknown())),
  executionId: z.string(),
  graphVersion: z.string(),
  groups: z.record(z.string(), z.unknown()),
  metadata: z.record(z.string(), z.unknown()),
  nodes: z.record(z.string(), z.unknown()),
  paused: z.boolean().default(false),
  schemaVersion: z.string(),
  status: z.string(),
  taskId: z.string(),
  terminal: z.boolean().default(false),
  variables: z.record(z.string(), z.unknown()),
});
export type NativeExecutionSnapshotResponse = z.output<typeof NativeExecutionSnapshotResponseSchema>;

/** One recursive span in the LingxiLearn execution timeline. */
export const ExecutionSpanResponseSchema: z.ZodType<any> = z.lazy(() => z.object({
  children: z.array(ExecutionSpanResponseSchema),
  durationMs: z.number().int(),
  endedAt: z.string(),
  id: z.string(),
  kind: z.string(),
  name: z.string(),
  startedAt: z.string(),
  status: z.string(),
}).catchall(z.unknown()));
export type ExecutionSpanResponse = z.output<typeof ExecutionSpanResponseSchema>;

export const ExecutionTimelineResponseSchema = z.object({
  executionId: z.string(),
  schemaVersion: z.string(),
  spans: z.array(ExecutionSpanResponseSchema),
  totalTokens: z.number().int().default(0),
  waitingForUserMs: z.number().int().default(0),
});
export type ExecutionTimelineResponse = z.output<typeof ExecutionTimelineResponseSchema>;

export const ExecutionSnapshotResponseSchema = z.object({
  eventLog: z.record(z.string(), z.unknown()),
  executionId: z.string(),
  executionMetadata: ExecutionMetadataResponseSchema,
  graphVersion: z.string(),
  schemaVersion: z.string(),
  snapshot: NativeExecutionSnapshotResponseSchema,
  status: z.string(),
  taskId: z.string(),
  timeline: ExecutionTimelineResponseSchema,
  trajectory: z.record(z.string(), z.unknown()),
});
export type ExecutionSnapshotResponse = z.output<typeof ExecutionSnapshotResponseSchema>;

export const FileDownloadUrlResponseSchema = z.object({
  downloadUrl: z.string(),
  expiresIn: z.number().int().nullable(),
  fileName: z.string(),
  success: z.boolean().default(true),
  viewerUrl: z.string(),
});
export type FileDownloadUrlResponse = z.output<typeof FileDownloadUrlResponseSchema>;

export const FolderArchiveResponseSchema = z.object({
  deletedItems: DeletedItemsResultSchema,
  success: z.boolean().default(true),
});
export type FolderArchiveResponse = z.output<typeof FolderArchiveResponseSchema>;

/** Exact ``_folder_public`` wire shape (no ``archived`` key on the wire). */
export const WorkspaceFolderInfoSchema = z.object({
  createdAt: z.string().nullable(),
  deletedAt: z.string().nullable(),
  id: z.string(),
  name: z.string(),
  parentId: z.string().nullable(),
  path: z.string(),
  sortOrder: z.number().int().default(0),
  updatedAt: z.string().nullable(),
  userId: z.string(),
  workspaceId: z.string(),
});
export type WorkspaceFolderInfo = z.output<typeof WorkspaceFolderInfoSchema>;

export const FolderRestoreResponseSchema = z.object({
  folder: WorkspaceFolderInfoSchema,
  restoredItems: DeletedItemsResultSchema,
  success: z.boolean().default(true),
});
export type FolderRestoreResponse = z.output<typeof FolderRestoreResponseSchema>;

export const ValidationErrorSchema = z.object({
  ctx: z.object({}).passthrough(),
  input: z.unknown(),
  loc: z.array(z.union([z.string(), z.number().int()])),
  msg: z.string(),
  type: z.string(),
});
export type ValidationError = z.output<typeof ValidationErrorSchema>;

export const HTTPValidationErrorSchema = z.object({
  detail: z.array(ValidationErrorSchema),
});
export type HTTPValidationError = z.output<typeof HTTPValidationErrorSchema>;

export const InteractionAnswerResponseSchema = z.object({
  interactionId: z.string(),
  status: z.string(),
});
export type InteractionAnswerResponse = z.output<typeof InteractionAnswerResponseSchema>;

export const KnowledgeChunkingConfigInfoSchema = z.object({
  maxSize: z.number().int().default(1200),
  minSize: z.number().int().default(1),
  overlap: z.number().int().default(0),
  strategy: z.string().default("text"),
});
export type KnowledgeChunkingConfigInfo = z.output<typeof KnowledgeChunkingConfigInfoSchema>;

/** Exact ``_knowledge_base_public`` wire shape. */
export const KnowledgeBaseInfoSchema = z.object({
  archived: z.boolean().default(false),
  chunkingConfig: KnowledgeChunkingConfigInfoSchema,
  createdAt: z.string().nullable(),
  deletedAt: z.string().nullable(),
  description: z.string().default(""),
  docCount: z.number().int().default(0),
  documentCount: z.number().int().default(0),
  fileCount: z.number().int().default(0),
  folderId: z.string().nullable(),
  id: z.string(),
  name: z.string(),
  tokenCount: z.number().int().default(0),
  updatedAt: z.string().nullable(),
  userId: z.string(),
  workspaceId: z.string(),
});
export type KnowledgeBaseInfo = z.output<typeof KnowledgeBaseInfoSchema>;

export const KnowledgeBaseResponseSchema = z.object({
  data: KnowledgeBaseInfoSchema,
  knowledgeBase: KnowledgeBaseInfoSchema,
  success: z.boolean().default(true),
});
export type KnowledgeBaseResponse = z.output<typeof KnowledgeBaseResponseSchema>;

export const KnowledgeBasesResponseSchema = z.object({
  data: z.array(KnowledgeBaseInfoSchema),
  knowledgeBases: z.array(KnowledgeBaseInfoSchema),
  success: z.boolean().default(true),
});
export type KnowledgeBasesResponse = z.output<typeof KnowledgeBasesResponseSchema>;

export const KnowledgeBulkChunksDataSchema = z.object({
  errorCount: z.number().int().default(0),
  errors: z.array(z.unknown()),
  operation: z.string(),
  processed: z.number().int().default(0),
  successCount: z.number().int().default(0),
});
export type KnowledgeBulkChunksData = z.output<typeof KnowledgeBulkChunksDataSchema>;

export const KnowledgeBulkChunksResponseSchema = z.object({
  data: KnowledgeBulkChunksDataSchema,
  success: z.boolean().default(true),
});
export type KnowledgeBulkChunksResponse = z.output<typeof KnowledgeBulkChunksResponseSchema>;

export const KnowledgeBulkDocumentUpdateInfoSchema = z.object({
  enabled: z.boolean(),
  id: z.string(),
});
export type KnowledgeBulkDocumentUpdateInfo = z.output<typeof KnowledgeBulkDocumentUpdateInfoSchema>;

export const KnowledgeBulkDocumentsDataSchema = z.object({
  failedCount: z.number().int().default(0),
  operation: z.string(),
  successCount: z.number().int().default(0),
  updatedDocuments: z.array(KnowledgeBulkDocumentUpdateInfoSchema),
});
export type KnowledgeBulkDocumentsData = z.output<typeof KnowledgeBulkDocumentsDataSchema>;

export const KnowledgeBulkDocumentsResponseSchema = z.object({
  data: KnowledgeBulkDocumentsDataSchema,
  success: z.boolean().default(true),
});
export type KnowledgeBulkDocumentsResponse = z.output<typeof KnowledgeBulkDocumentsResponseSchema>;

/** Exact ``_chunk_public`` wire shape, tag slots included. */
export const KnowledgeChunkInfoSchema = z.object({
  boolean1: z.unknown(),
  boolean2: z.unknown(),
  boolean3: z.unknown(),
  chunkIndex: z.number().int().default(0),
  content: z.string().default(""),
  contentLength: z.number().int().default(0),
  createdAt: z.string().nullable(),
  date1: z.unknown(),
  date2: z.unknown(),
  enabled: z.boolean().default(true),
  endOffset: z.number().int().default(0),
  id: z.string(),
  number1: z.unknown(),
  number2: z.unknown(),
  number3: z.unknown(),
  number4: z.unknown(),
  number5: z.unknown(),
  startOffset: z.number().int().default(0),
  tag1: z.unknown(),
  tag2: z.unknown(),
  tag3: z.unknown(),
  tag4: z.unknown(),
  tag5: z.unknown(),
  tag6: z.unknown(),
  tag7: z.unknown(),
  tokenCount: z.number().int().default(0),
  updatedAt: z.string().nullable(),
});
export type KnowledgeChunkInfo = z.output<typeof KnowledgeChunkInfoSchema>;

export const KnowledgeChunkResponseSchema = z.object({
  data: KnowledgeChunkInfoSchema,
  success: z.boolean().default(true),
});
export type KnowledgeChunkResponse = z.output<typeof KnowledgeChunkResponseSchema>;

export const KnowledgePaginationInfoSchema = z.object({
  hasMore: z.boolean().default(false),
  limit: z.number().int().default(50),
  offset: z.number().int().default(0),
  total: z.number().int().default(0),
});
export type KnowledgePaginationInfo = z.output<typeof KnowledgePaginationInfoSchema>;

export const KnowledgeChunksResponseSchema = z.object({
  chunks: z.array(KnowledgeChunkInfoSchema),
  data: z.array(KnowledgeChunkInfoSchema),
  pagination: KnowledgePaginationInfoSchema,
  success: z.boolean().default(true),
});
export type KnowledgeChunksResponse = z.output<typeof KnowledgeChunksResponseSchema>;

/** Exact ``_document_public`` wire shape, tag slots included. */
export const KnowledgeDocumentInfoSchema = z.object({
  archived: z.boolean().default(false),
  boolean1: z.unknown(),
  boolean2: z.unknown(),
  boolean3: z.unknown(),
  characterCount: z.number().int().default(0),
  chunkCount: z.number().int().default(0),
  connectorId: z.unknown(),
  connectorType: z.unknown(),
  content: z.string().default(""),
  createdAt: z.string().nullable(),
  date1: z.unknown(),
  date2: z.unknown(),
  enabled: z.boolean().default(true),
  filename: z.string(),
  fileSize: z.number().int().default(0),
  fileUrl: z.string(),
  id: z.string(),
  knowledgeBaseId: z.string(),
  metadata: z.record(z.string(), z.unknown()),
  mimeType: z.string(),
  name: z.string(),
  number1: z.unknown(),
  number2: z.unknown(),
  number3: z.unknown(),
  number4: z.unknown(),
  number5: z.unknown(),
  processingError: z.string().nullable(),
  processingStatus: z.string().default("completed"),
  readOnly: z.boolean().default(false),
  size: z.number().int().default(0),
  sourceUrl: z.unknown(),
  status: z.string().default("ready"),
  tag1: z.unknown(),
  tag2: z.unknown(),
  tag3: z.unknown(),
  tag4: z.unknown(),
  tag5: z.unknown(),
  tag6: z.unknown(),
  tag7: z.unknown(),
  tokenCount: z.number().int().default(0),
  updatedAt: z.string().nullable(),
  uploadedAt: z.string().nullable(),
});
export type KnowledgeDocumentInfo = z.output<typeof KnowledgeDocumentInfoSchema>;

export const KnowledgeDocumentResponseSchema = z.object({
  data: KnowledgeDocumentInfoSchema,
  document: KnowledgeDocumentInfoSchema,
  success: z.boolean().default(true),
});
export type KnowledgeDocumentResponse = z.output<typeof KnowledgeDocumentResponseSchema>;

export const KnowledgeDocumentSummaryInfoSchema = z.object({
  characterCount: z.number().int().default(0),
  chunkCount: z.number().int().default(0),
  createdAt: z.string().nullable(),
  enabled: z.boolean().default(true),
  filename: z.string(),
  fileSize: z.number().int().default(0),
  id: z.string(),
  knowledgeBaseId: z.string(),
  mimeType: z.string(),
  processingStatus: z.string().default("completed"),
  tokenCount: z.number().int().default(0),
});
export type KnowledgeDocumentSummaryInfo = z.output<typeof KnowledgeDocumentSummaryInfoSchema>;

export const KnowledgeDocumentUpsertCreatedInfoSchema = z.object({
  documentId: z.string(),
  filename: z.string(),
  status: z.string().default("pending"),
});
export type KnowledgeDocumentUpsertCreatedInfo = z.output<typeof KnowledgeDocumentUpsertCreatedInfoSchema>;

export const KnowledgeDocumentUpsertDataSchema = z.object({
  documentsCreated: z.array(KnowledgeDocumentUpsertCreatedInfoSchema),
  isUpdate: z.boolean().default(false),
  previousDocumentId: z.string().nullable(),
  processingConfig: z.record(z.string(), z.unknown()),
  processingMethod: z.string().default("background"),
});
export type KnowledgeDocumentUpsertData = z.output<typeof KnowledgeDocumentUpsertDataSchema>;

export const KnowledgeDocumentUpsertResponseSchema = z.object({
  data: KnowledgeDocumentUpsertDataSchema,
  success: z.boolean().default(true),
});
export type KnowledgeDocumentUpsertResponse = z.output<typeof KnowledgeDocumentUpsertResponseSchema>;

export const KnowledgeDocumentsDataSchema = z.object({
  documents: z.array(KnowledgeDocumentInfoSchema),
  pagination: KnowledgePaginationInfoSchema,
});
export type KnowledgeDocumentsData = z.output<typeof KnowledgeDocumentsDataSchema>;

export const KnowledgeDocumentsResponseSchema = z.object({
  data: KnowledgeDocumentsDataSchema,
  documents: z.array(KnowledgeDocumentInfoSchema),
  success: z.boolean().default(true),
});
export type KnowledgeDocumentsResponse = z.output<typeof KnowledgeDocumentsResponseSchema>;

export const TableMessageDataSchema = z.object({
  message: z.string().default(""),
});
export type TableMessageData = z.output<typeof TableMessageDataSchema>;

export const KnowledgeMessageResponseSchema = z.object({
  data: TableMessageDataSchema,
  success: z.boolean().default(true),
});
export type KnowledgeMessageResponse = z.output<typeof KnowledgeMessageResponseSchema>;

export const KnowledgeNextSlotDataSchema = z.object({
  availableSlots: z.number().int().default(0),
  fieldType: z.string(),
  nextAvailableSlot: z.string().nullable(),
  totalSlots: z.number().int().default(0),
  usedSlots: z.array(z.string()),
});
export type KnowledgeNextSlotData = z.output<typeof KnowledgeNextSlotDataSchema>;

export const KnowledgeNextSlotResponseSchema = z.object({
  data: KnowledgeNextSlotDataSchema,
  success: z.boolean().default(true),
});
export type KnowledgeNextSlotResponse = z.output<typeof KnowledgeNextSlotResponseSchema>;

export const KnowledgeSearchResultInfoSchema = z.object({
  document: KnowledgeDocumentInfoSchema,
  score: z.number().default(0),
  snippet: z.string().default(""),
});
export type KnowledgeSearchResultInfo = z.output<typeof KnowledgeSearchResultInfoSchema>;

export const KnowledgeSearchResponseSchema = z.object({
  data: z.array(KnowledgeSearchResultInfoSchema),
  results: z.array(KnowledgeSearchResultInfoSchema),
  success: z.boolean().default(true),
});
export type KnowledgeSearchResponse = z.output<typeof KnowledgeSearchResponseSchema>;

/** Document-scoped tag list: only ``data`` is present on the wire. */
export const KnowledgeTagListResponseSchema = z.object({
  data: z.array(KnowledgeTagInfoSchema),
  success: z.boolean().default(true),
});
export type KnowledgeTagListResponse = z.output<typeof KnowledgeTagListResponseSchema>;

export const KnowledgeTagResponseSchema = z.object({
  data: KnowledgeTagInfoSchema,
  success: z.boolean().default(true),
});
export type KnowledgeTagResponse = z.output<typeof KnowledgeTagResponseSchema>;

export const KnowledgeTagUsageDocumentInfoSchema = z.object({
  id: z.string(),
  name: z.string(),
  tagValue: z.string().default(""),
});
export type KnowledgeTagUsageDocumentInfo = z.output<typeof KnowledgeTagUsageDocumentInfoSchema>;

export const KnowledgeTagUsageInfoSchema = z.object({
  documentCount: z.number().int().default(0),
  documents: z.array(KnowledgeTagUsageDocumentInfoSchema),
  tagName: z.string(),
  tagSlot: z.string().default(""),
});
export type KnowledgeTagUsageInfo = z.output<typeof KnowledgeTagUsageInfoSchema>;

export const KnowledgeTagUsageResponseSchema = z.object({
  data: z.array(KnowledgeTagUsageInfoSchema),
  success: z.boolean().default(true),
});
export type KnowledgeTagUsageResponse = z.output<typeof KnowledgeTagUsageResponseSchema>;

export const KnowledgeTagsResponseSchema = z.object({
  data: z.array(KnowledgeTagInfoSchema),
  success: z.boolean().default(true),
  tags: z.array(KnowledgeTagInfoSchema),
});
export type KnowledgeTagsResponse = z.output<typeof KnowledgeTagsResponseSchema>;

export const KnowledgeUploadSessionInfoSchema = z.object({
  contentType: z.string(),
  document: KnowledgeDocumentSummaryInfoSchema.nullable(),
  error: z.string().nullable(),
  expiresAt: z.string(),
  id: z.string(),
  knowledgeBaseId: z.string(),
  name: z.string(),
  size: z.number().int(),
  status: z.string(),
});
export type KnowledgeUploadSessionInfo = z.output<typeof KnowledgeUploadSessionInfoSchema>;

export const KnowledgeUploadCreateDataSchema = z.object({
  session: KnowledgeUploadSessionInfoSchema,
  transfer: UploadTransferInfoSchema,
  uploadToken: z.string(),
});
export type KnowledgeUploadCreateData = z.output<typeof KnowledgeUploadCreateDataSchema>;

export const KnowledgeUploadCreateResponseSchema = z.object({
  data: KnowledgeUploadCreateDataSchema,
});
export type KnowledgeUploadCreateResponse = z.output<typeof KnowledgeUploadCreateResponseSchema>;

export const LearningProfileColumnsSchema = z.object({
  learner: z.array(z.string()),
  system: z.array(z.string()),
});
export type LearningProfileColumns = z.output<typeof LearningProfileColumnsSchema>;

export const LearningProfileSystemInfoSchema = z.object({
  confidence: z.number().default(0),
  difficulty: z.number().default(0),
  evidence_count: z.number().int().default(0),
  last_evidence_seq: z.number().int().default(0),
  misconceptions: z.array(z.unknown()),
  override_flag: z.boolean().default(false),
  prerequisites: z.array(z.unknown()),
  review_priority: z.number().default(0),
  revision: z.number().int().default(0),
  source_agent: z.string().nullable(),
  stability: z.number().default(0),
});
export type LearningProfileSystemInfo = z.output<typeof LearningProfileSystemInfoSchema>;

export const LearningProfileRowInfoSchema = z.object({
  knowledge_point: z.string(),
  knowledge_point_id: z.string(),
  last_studied_at: z.string().nullable(),
  learning_state: z.string().nullable(),
  mastery: z.number().default(0),
  my_questions: z.array(z.unknown()),
  next_step: z.record(z.string(), z.unknown()),
  progress: z.number().default(0),
  recent_performance: z.record(z.string(), z.unknown()),
  review_due_at: z.string().nullable(),
  system: LearningProfileSystemInfoSchema,
  updated_at: z.string().nullable(),
});
export type LearningProfileRowInfo = z.output<typeof LearningProfileRowInfoSchema>;

export const LearningProfileResponseSchema = z.object({
  columns: LearningProfileColumnsSchema,
  profile: z.array(LearningProfileRowInfoSchema),
});
export type LearningProfileResponse = z.output<typeof LearningProfileResponseSchema>;

export const LearningRecordResponseSchema = z.object({
  data: z.record(z.string(), z.unknown()),
  success: z.boolean(),
});
export type LearningRecordResponse = z.output<typeof LearningRecordResponseSchema>;

export const LegacyToolPermissionDecisionSchema = z.object({
  decision: z.string(),
  toolCallId: z.string().min(1).max(255),
});
export type LegacyToolPermissionDecision = z.output<typeof LegacyToolPermissionDecisionSchema>;

export const LegacyToolPermissionRequestSchema = z.object({
  decisions: z.array(LegacyToolPermissionDecisionSchema).min(1).max(50),
});
export type LegacyToolPermissionRequest = z.output<typeof LegacyToolPermissionRequestSchema>;

export const LegacyToolPermissionResultSchema = z.object({
  applied: z.boolean().default(false),
  decision: z.string(),
  scope: z.unknown(),
  status: z.string().default("unknown"),
  toolCallId: z.string(),
});
export type LegacyToolPermissionResult = z.output<typeof LegacyToolPermissionResultSchema>;

export const LegacyToolPermissionResponseSchema = z.object({
  results: z.array(LegacyToolPermissionResultSchema),
  success: z.boolean(),
});
export type LegacyToolPermissionResponse = z.output<typeof LegacyToolPermissionResponseSchema>;

export const LivenessResponseSchema = z.object({
  status: z.string(),
});
export type LivenessResponse = z.output<typeof LivenessResponseSchema>;

export const SessionListItemInfoSchema = z.object({
  created_at: z.string().nullable(),
  id: z.string(),
  mission_id: z.string(),
  pack_id: z.string(),
  status: z.string(),
});
export type SessionListItemInfo = z.output<typeof SessionListItemInfoSchema>;

export const MasteryResponseSchema = z.object({
  mastery: z.record(z.string(), z.unknown()),
  sessions: z.array(SessionListItemInfoSchema),
});
export type MasteryResponse = z.output<typeof MasteryResponseSchema>;

export const MessageResponseSchema = z.object({
  message: z.string(),
});
export type MessageResponse = z.output<typeof MessageResponseSchema>;

export const MoveItemsResultSchema = z.object({
  files: z.number().int().default(0),
  folders: z.number().int().default(0),
});
export type MoveItemsResult = z.output<typeof MoveItemsResultSchema>;

export const MoveItemsResponseSchema = z.object({
  movedItems: MoveItemsResultSchema,
  success: z.boolean().default(true),
});
export type MoveItemsResponse = z.output<typeof MoveItemsResponseSchema>;

/** Union of the registry-backed and personal skill wire shapes.

The ``/skills`` catalogue merges two sources; fields present in only one
source stay optional so the merged list remains one schema. */
export const NativeSkillInfoSchema = z.object({
  capabilities: z.array(z.string()).nullable(),
  compatibility: z.string().nullable(),
  content: z.string().default(""),
  cost: z.record(z.string(), z.unknown()).nullable(),
  created_at: z.string().nullable(),
  description: z.string().nullable(),
  display_name: z.string().default(""),
  enabled: z.boolean().nullable(),
  id: z.string(),
  is_system: z.boolean().default(false),
  license: z.string().nullable(),
  name: z.string().default(""),
  ownership: z.string().nullable(),
  provider: z.string().nullable(),
  source: z.string().default("system"),
  updated_at: z.string().nullable(),
  version: z.string().default(""),
});
export type NativeSkillInfo = z.output<typeof NativeSkillInfoSchema>;

export const PackConceptInfoSchema = z.object({
  id: z.string(),
  requires: z.array(z.string()),
  summary: z.string(),
  title: z.string(),
});
export type PackConceptInfo = z.output<typeof PackConceptInfoSchema>;

export const PackMissionInfoSchema = z.object({
  concepts: z.array(z.string()),
  estimated_minutes: z.number().int(),
  id: z.string(),
  steps: z.number().int(),
  subtitle: z.string(),
  summary: z.string(),
  title: z.string(),
  why_not_chat: z.string(),
});
export type PackMissionInfo = z.output<typeof PackMissionInfoSchema>;

export const PackInfoSchema = z.object({
  concepts: z.array(PackConceptInfoSchema),
  description: z.string(),
  id: z.string(),
  missions: z.array(PackMissionInfoSchema),
  title: z.string(),
  version: z.string(),
});
export type PackInfo = z.output<typeof PackInfoSchema>;

export const PacksResponseSchema = z.object({
  packs: z.array(PackInfoSchema),
});
export type PacksResponse = z.output<typeof PacksResponseSchema>;

/** Exact ``_skill_public`` wire shape. */
export const PersonalSkillInfoSchema = z.object({
  content: z.string().default(""),
  created_at: z.string().nullable(),
  description: z.string().default(""),
  display_name: z.string(),
  id: z.string(),
  is_system: z.boolean().default(false),
  name: z.string(),
  source: z.string().default("personal"),
  updated_at: z.string().nullable(),
  version: z.string().default("1.0.0"),
});
export type PersonalSkillInfo = z.output<typeof PersonalSkillInfoSchema>;

export const PinnedItemInfoSchema = z.object({
  id: z.string(),
  pinnedAt: z.string().nullable(),
  resourceId: z.string(),
  resourceType: z.string(),
  userId: z.string(),
  workspaceId: z.string(),
});
export type PinnedItemInfo = z.output<typeof PinnedItemInfoSchema>;

export const PinnedItemResponseSchema = z.object({
  pinnedItem: PinnedItemInfoSchema,
});
export type PinnedItemResponse = z.output<typeof PinnedItemResponseSchema>;

export const PinnedItemsResponseSchema = z.object({
  pinnedItems: z.array(PinnedItemInfoSchema),
});
export type PinnedItemsResponse = z.output<typeof PinnedItemsResponseSchema>;

export const PreferencesResponseSchema = z.object({
  preferences: z.record(z.string(), z.unknown()),
});
export type PreferencesResponse = z.output<typeof PreferencesResponseSchema>;

export const ProfileChangeResponseSchema = z.object({
  after: z.record(z.string(), z.unknown()),
  before: z.record(z.string(), z.unknown()),
  evidence_ids: z.array(z.string()),
  knowledge_point_id: z.string(),
  learner_id: z.string(),
  reason: z.string().default(""),
  source_agent: z.string().default(""),
});
export type ProfileChangeResponse = z.output<typeof ProfileChangeResponseSchema>;

/** A learner correcting their own record. Not an agent write. */
export const ProfileOverrideSchema = z.object({
  learning_state: z.string().max(48).nullable(),
  mastery: z.number().min(0).max(1).nullable(),
  override: z.boolean().default(true),
  progress: z.number().min(0).max(1).nullable(),
});
export type ProfileOverride = z.output<typeof ProfileOverrideSchema>;

export const QuizSubmissionBodySchema = z.object({
  answers: z.record(z.string(), z.unknown()),
  idempotency_key: z.string().min(1).max(192).nullable(),
  submission_id: z.string().min(1).max(128),
});
export type QuizSubmissionBody = z.output<typeof QuizSubmissionBodySchema>;

export const QuizSubmissionResponseSchema = z.object({
  status: z.string(),
  submission: QuizSubmissionSnapshotInfoSchema.nullable(),
});
export type QuizSubmissionResponse = z.output<typeof QuizSubmissionResponseSchema>;

export const ReadinessResponseSchema = z.object({
  database: z.boolean(),
  services: z.boolean(),
  status: z.string(),
});
export type ReadinessResponse = z.output<typeof ReadinessResponseSchema>;

export const RuntimeGraphResponseSchema = z.object({
  executionGraph: z.record(z.string(), z.unknown()),
  executionSnapshot: z.record(z.string(), z.unknown()),
  id: z.string(),
  latestExecutionId: z.string().nullable(),
  status: z.string(),
  taskId: z.string(),
  type: z.string().default("runtime-graph"),
  updatedAt: z.string().nullable(),
});
export type RuntimeGraphResponse = z.output<typeof RuntimeGraphResponseSchema>;

export const SchedulePermissionDecisionSchema = z.object({
  decision: z.string(),
  proposalId: z.string().min(1).max(255),
});
export type SchedulePermissionDecision = z.output<typeof SchedulePermissionDecisionSchema>;

export const SchedulePermissionRequestSchema = z.object({
  decisions: z.array(SchedulePermissionDecisionSchema).min(1).max(50),
});
export type SchedulePermissionRequest = z.output<typeof SchedulePermissionRequestSchema>;

export const SchedulePermissionResultSchema = z.object({
  applied: z.boolean().default(false),
  decision: z.string(),
  proposalId: z.string(),
  scope: z.unknown(),
  status: z.string().default("unknown"),
});
export type SchedulePermissionResult = z.output<typeof SchedulePermissionResultSchema>;

export const SchedulePermissionResponseSchema = z.object({
  results: z.array(SchedulePermissionResultSchema),
  success: z.boolean(),
});
export type SchedulePermissionResponse = z.output<typeof SchedulePermissionResponseSchema>;

export const SkillCreateResponseSchema = z.object({
  data: PersonalSkillInfoSchema,
  skill: PersonalSkillInfoSchema,
  skills: z.array(PersonalSkillInfoSchema),
});
export type SkillCreateResponse = z.output<typeof SkillCreateResponseSchema>;

export const SkillRegistryCapabilityInfoSchema = z.object({
  capability: z.string(),
  heavy_artifact: z.boolean(),
  irreversible: z.boolean(),
  label: z.string(),
  learner_facing: z.boolean(),
  providers: z.array(z.string()),
});
export type SkillRegistryCapabilityInfo = z.output<typeof SkillRegistryCapabilityInfoSchema>;

/** Machine view of one registry row (``skill_dict`` wire shape). */
export const SkillRegistryEntryInfoSchema = z.object({
  capabilities: z.array(z.string()),
  checksum: z.string().nullable(),
  cost: z.record(z.string(), z.unknown()),
  description: z.string().nullable(),
  display_name: z.string().nullable(),
  enabled: z.boolean().default(false),
  input_schema: z.record(z.string(), z.unknown()),
  learner_id: z.string().nullable(),
  metadata: z.record(z.string(), z.unknown()),
  output_schema: z.record(z.string(), z.unknown()),
  ownership: z.string().nullable(),
  preconditions: z.record(z.string(), z.unknown()),
  provider: z.string().nullable(),
  skill_id: z.string(),
  source: z.string(),
  updated_at: z.string().nullable(),
  version: z.string().default(""),
});
export type SkillRegistryEntryInfo = z.output<typeof SkillRegistryEntryInfoSchema>;

export const SkillRegistryResponseSchema = z.object({
  capabilities: z.array(SkillRegistryCapabilityInfoSchema),
  skills: z.array(SkillRegistryEntryInfoSchema),
});
export type SkillRegistryResponse = z.output<typeof SkillRegistryResponseSchema>;

export const SkillUpdateResponseSchema = z.object({
  data: PersonalSkillInfoSchema,
  skill: PersonalSkillInfoSchema,
});
export type SkillUpdateResponse = z.output<typeof SkillUpdateResponseSchema>;

export const SkillsResponseSchema = z.object({
  skills: z.array(NativeSkillInfoSchema),
});
export type SkillsResponse = z.output<typeof SkillsResponseSchema>;

export const StorageStatusResponseSchema = z.object({
  cloudConfigured: z.boolean().default(false),
});
export type StorageStatusResponse = z.output<typeof StorageStatusResponseSchema>;

export const SuccessResponseSchema = z.object({
  success: z.boolean(),
});
export type SuccessResponse = z.output<typeof SuccessResponseSchema>;

export const TableColumnInfoSchema = z.object({
  currencyCode: z.string().nullable(),
  id: z.string(),
  key: z.string(),
  multiple: z.boolean().default(false),
  name: z.string(),
  options: z.array(z.unknown()),
  position: z.number().int().default(0),
  required: z.boolean().default(false),
  type: z.string().default("string"),
  unique: z.boolean().default(false),
});
export type TableColumnInfo = z.output<typeof TableColumnInfoSchema>;

export const TableColumnsDataSchema = z.object({
  columns: z.array(TableColumnInfoSchema),
});
export type TableColumnsData = z.output<typeof TableColumnsDataSchema>;

export const TableColumnsResponseSchema = z.object({
  data: TableColumnsDataSchema,
  success: z.boolean().default(true),
});
export type TableColumnsResponse = z.output<typeof TableColumnsResponseSchema>;

export const TableLocksInfoSchema = z.object({
  deleteLocked: z.boolean().default(false),
  insertLocked: z.boolean().default(false),
  schemaLocked: z.boolean().default(false),
  updateLocked: z.boolean().default(false),
});
export type TableLocksInfo = z.output<typeof TableLocksInfoSchema>;

export const TableSchemaInfoSchema = z.object({
  columns: z.array(TableColumnInfoSchema),
});
export type TableSchemaInfo = z.output<typeof TableSchemaInfoSchema>;

/** Exact ``_table_public`` wire shape. */
export const WorkspaceTableInfoSchema = z.object({
  archived: z.boolean().default(false),
  archivedAt: z.string().nullable(),
  columns: z.array(TableColumnInfoSchema),
  createdAt: z.string().nullable(),
  createdBy: z.string().nullable(),
  description: z.string().default(""),
  folderId: z.string().nullable(),
  id: z.string(),
  locks: TableLocksInfoSchema,
  metadata: z.record(z.string(), z.unknown()),
  name: z.string(),
  rowCount: z.number().int().default(0),
  schema: TableSchemaInfoSchema,
  totalRows: z.number().int().default(0),
  updatedAt: z.string().nullable(),
  workspaceId: z.string(),
});
export type WorkspaceTableInfo = z.output<typeof WorkspaceTableInfoSchema>;

export const TableDataSchema = z.object({
  message: z.string().nullable(),
  table: WorkspaceTableInfoSchema,
});
export type TableData = z.output<typeof TableDataSchema>;

export const TableEmptyDataResponseSchema = z.object({
  data: z.record(z.string(), z.unknown()),
  success: z.boolean().default(true),
});
export type TableEmptyDataResponse = z.output<typeof TableEmptyDataResponseSchema>;

export const TableImportCsvTableInfoSchema = z.object({
  id: z.string(),
  name: z.string(),
});
export type TableImportCsvTableInfo = z.output<typeof TableImportCsvTableInfoSchema>;

export const TableImportCsvDataSchema = z.object({
  importedRows: z.number().int().default(0),
  table: TableImportCsvTableInfoSchema,
});
export type TableImportCsvData = z.output<typeof TableImportCsvDataSchema>;

export const TableImportCsvResponseSchema = z.object({
  data: TableImportCsvDataSchema,
  success: z.boolean().default(true),
});
export type TableImportCsvResponse = z.output<typeof TableImportCsvResponseSchema>;

export const TableImportRowsDataSchema = z.object({
  importedRows: z.number().int().default(0),
});
export type TableImportRowsData = z.output<typeof TableImportRowsDataSchema>;

export const TableImportRowsResponseSchema = z.object({
  data: TableImportRowsDataSchema,
  success: z.boolean().default(true),
});
export type TableImportRowsResponse = z.output<typeof TableImportRowsResponseSchema>;

export const TableListDataSchema = z.object({
  tables: z.array(WorkspaceTableInfoSchema),
  totalCount: z.number().int().default(0),
});
export type TableListData = z.output<typeof TableListDataSchema>;

export const TableListResponseSchema = z.object({
  data: TableListDataSchema,
  success: z.boolean().default(true),
  tables: z.array(WorkspaceTableInfoSchema),
  totalCount: z.number().int().default(0),
});
export type TableListResponse = z.output<typeof TableListResponseSchema>;

export const TableMessageResponseSchema = z.object({
  data: TableMessageDataSchema,
  success: z.boolean().default(true),
});
export type TableMessageResponse = z.output<typeof TableMessageResponseSchema>;

export const TableResponseSchema = z.object({
  data: TableDataSchema,
  success: z.boolean().default(true),
});
export type TableResponse = z.output<typeof TableResponseSchema>;

export const TableRowInfoSchema = z.object({
  createdAt: z.string().nullable(),
  data: z.record(z.string(), z.unknown()),
  id: z.string(),
  position: z.number().int().default(0),
  updatedAt: z.string().nullable(),
  values: z.record(z.string(), z.unknown()),
});
export type TableRowInfo = z.output<typeof TableRowInfoSchema>;

export const TableRowDataSchema = z.object({
  row: TableRowInfoSchema,
});
export type TableRowData = z.output<typeof TableRowDataSchema>;

export const TableRowMatchInfoSchema = z.object({
  column: z.string(),
  ordinal: z.number().int(),
  rowId: z.string(),
});
export type TableRowMatchInfo = z.output<typeof TableRowMatchInfoSchema>;

export const TableRowResponseSchema = z.object({
  data: TableRowDataSchema,
  success: z.boolean().default(true),
});
export type TableRowResponse = z.output<typeof TableRowResponseSchema>;

export const TableRowsCreateDataSchema = z.object({
  row: TableRowInfoSchema.nullable(),
  rows: z.array(TableRowInfoSchema),
});
export type TableRowsCreateData = z.output<typeof TableRowsCreateDataSchema>;

export const TableRowsCreateResponseSchema = z.object({
  data: TableRowsCreateDataSchema,
  success: z.boolean().default(true),
});
export type TableRowsCreateResponse = z.output<typeof TableRowsCreateResponseSchema>;

export const TableRowsDataSchema = z.object({
  limit: z.number().int().default(100),
  nextCursor: z.string().nullable(),
  offset: z.number().int().default(0),
  rowCount: z.number().int().default(0),
  rows: z.array(TableRowInfoSchema),
  totalCount: z.number().int().default(0),
});
export type TableRowsData = z.output<typeof TableRowsDataSchema>;

export const TableRowsFindDataSchema = z.object({
  matches: z.array(TableRowMatchInfoSchema),
  truncated: z.boolean().default(false),
});
export type TableRowsFindData = z.output<typeof TableRowsFindDataSchema>;

export const TableRowsFindResponseSchema = z.object({
  data: TableRowsFindDataSchema,
  success: z.boolean().default(true),
});
export type TableRowsFindResponse = z.output<typeof TableRowsFindResponseSchema>;

export const TableRowsQueryDataSchema = z.object({
  nextCursor: z.string().nullable(),
  rowCount: z.number().int().default(0),
  rows: z.array(TableRowInfoSchema),
  totalCount: z.number().int().default(0),
});
export type TableRowsQueryData = z.output<typeof TableRowsQueryDataSchema>;

export const TableRowsQueryResponseSchema = z.object({
  data: TableRowsQueryDataSchema,
  success: z.boolean().default(true),
});
export type TableRowsQueryResponse = z.output<typeof TableRowsQueryResponseSchema>;

export const TableRowsResponseSchema = z.object({
  data: TableRowsDataSchema,
  success: z.boolean().default(true),
});
export type TableRowsResponse = z.output<typeof TableRowsResponseSchema>;

export const TableRowsUpsertDataSchema = z.object({
  rows: z.array(TableRowInfoSchema),
});
export type TableRowsUpsertData = z.output<typeof TableRowsUpsertDataSchema>;

export const TableRowsUpsertResponseSchema = z.object({
  data: TableRowsUpsertDataSchema,
  success: z.boolean().default(true),
});
export type TableRowsUpsertResponse = z.output<typeof TableRowsUpsertResponseSchema>;

export const TableViewInfoSchema = z.object({
  config: z.record(z.string(), z.unknown()),
  createdAt: z.string().nullable(),
  createdBy: z.string().nullable(),
  id: z.string(),
  isDefault: z.boolean().default(false),
  name: z.string(),
  tableId: z.string(),
  updatedAt: z.string().nullable(),
});
export type TableViewInfo = z.output<typeof TableViewInfoSchema>;

export const TableViewDataSchema = z.object({
  view: TableViewInfoSchema,
});
export type TableViewData = z.output<typeof TableViewDataSchema>;

export const TableViewDeletedDataSchema = z.object({
  deleted: z.boolean().default(true),
});
export type TableViewDeletedData = z.output<typeof TableViewDeletedDataSchema>;

export const TableViewDeletedResponseSchema = z.object({
  data: TableViewDeletedDataSchema,
  success: z.boolean().default(true),
});
export type TableViewDeletedResponse = z.output<typeof TableViewDeletedResponseSchema>;

export const TableViewResponseSchema = z.object({
  data: TableViewDataSchema,
  success: z.boolean().default(true),
});
export type TableViewResponse = z.output<typeof TableViewResponseSchema>;

export const TableViewsDataSchema = z.object({
  views: z.array(TableViewInfoSchema),
});
export type TableViewsData = z.output<typeof TableViewsDataSchema>;

export const TableViewsResponseSchema = z.object({
  data: TableViewsDataSchema,
  success: z.boolean().default(true),
});
export type TableViewsResponse = z.output<typeof TableViewsResponseSchema>;

export const UploadCompletedInfoSchema = z.object({
  contentType: z.string(),
  error: z.string().nullable(),
  expiresAt: z.string(),
  id: z.string(),
  name: z.string(),
  purpose: z.string().default("workspace_file"),
  result: z.record(z.string(), z.unknown()).nullable(),
  size: z.number().int(),
  status: z.string(),
});
export type UploadCompletedInfo = z.output<typeof UploadCompletedInfoSchema>;

export const UploadPartInfoSchema = z.object({
  expiresAt: z.string(),
  headers: z.record(z.string(), z.unknown()),
  partNumber: z.number().int(),
  url: z.string(),
});
export type UploadPartInfo = z.output<typeof UploadPartInfoSchema>;

export const UploadPartsDataSchema = z.object({
  parts: z.array(UploadPartInfoSchema),
});
export type UploadPartsData = z.output<typeof UploadPartsDataSchema>;

export const UploadPartsResponseSchema = z.object({
  data: UploadPartsDataSchema,
});
export type UploadPartsResponse = z.output<typeof UploadPartsResponseSchema>;

export const UploadStateResponseSchema = z.object({
  data: UploadCompletedInfoSchema,
});
export type UploadStateResponse = z.output<typeof UploadStateResponseSchema>;

/** Exact ``_settings_public`` wire shape. */
export const UserSettingsInfoSchema = z.object({
  autoConnect: z.boolean().default(true),
  billingUsageNotificationsEnabled: z.boolean().default(true),
  copilotAutoAllowedTools: z.array(z.string()),
  emailPreferences: z.record(z.string(), z.unknown()),
  errorNotificationsEnabled: z.boolean().default(true),
  lastActiveWorkspaceId: z.string().nullable(),
  mothershipEnvironment: z.string().default("default"),
  showActionBar: z.boolean().default(true),
  snapToGridSize: z.number().default(0),
  superUserModeEnabled: z.boolean().default(false),
  telemetryEnabled: z.boolean().default(true),
  theme: z.string().default("system"),
  timezone: z.string().nullable(),
});
export type UserSettingsInfo = z.output<typeof UserSettingsInfoSchema>;

export const UserSettingsResponseSchema = z.object({
  data: UserSettingsInfoSchema,
});
export type UserSettingsResponse = z.output<typeof UserSettingsResponseSchema>;

export const UserSettingsUpdateResponseSchema = z.object({
  data: UserSettingsInfoSchema,
  success: z.boolean(),
});
export type UserSettingsUpdateResponse = z.output<typeof UserSettingsUpdateResponseSchema>;

/** Exact ``_file_public`` wire shape — the public file DTO, never the ORM row. */
export const WorkspaceFileInfoSchema = z.object({
  context: z.string().default("workspace"),
  deletedAt: z.string().nullable(),
  folderId: z.string().nullable(),
  height: z.number().int().nullable(),
  id: z.string(),
  key: z.string(),
  metadata: z.record(z.string(), z.unknown()),
  mimeType: z.string(),
  name: z.string(),
  path: z.string(),
  readOnly: z.boolean().default(false),
  size: z.number().int().default(0),
  storageContext: z.string().default("workspace"),
  type: z.string(),
  updatedAt: z.string().nullable(),
  uploadedAt: z.string().nullable(),
  uploadedBy: z.string().nullable(),
  url: z.string(),
  width: z.number().int().nullable(),
  workspaceId: z.string(),
});
export type WorkspaceFileInfo = z.output<typeof WorkspaceFileInfoSchema>;

export const WorkspaceFileContentResponseSchema = z.object({
  content: z.string(),
  encoding: z.string(),
  file: WorkspaceFileInfoSchema,
  success: z.boolean().default(true),
});
export type WorkspaceFileContentResponse = z.output<typeof WorkspaceFileContentResponseSchema>;

export const WorkspaceFileResponseSchema = z.object({
  data: WorkspaceFileInfoSchema.nullable(),
  file: WorkspaceFileInfoSchema,
  success: z.boolean().default(true),
});
export type WorkspaceFileResponse = z.output<typeof WorkspaceFileResponseSchema>;

export const WorkspaceFilesResponseSchema = z.object({
  files: z.array(WorkspaceFileInfoSchema),
  success: z.boolean().default(true),
});
export type WorkspaceFilesResponse = z.output<typeof WorkspaceFilesResponseSchema>;

export const WorkspaceFolderResponseSchema = z.object({
  folder: WorkspaceFolderInfoSchema,
  success: z.boolean().default(true),
});
export type WorkspaceFolderResponse = z.output<typeof WorkspaceFolderResponseSchema>;

export const WorkspaceFoldersResponseSchema = z.object({
  data: z.array(WorkspaceFolderInfoSchema),
  folders: z.array(WorkspaceFolderInfoSchema),
  success: z.boolean().default(true),
});
export type WorkspaceFoldersResponse = z.output<typeof WorkspaceFoldersResponseSchema>;

export const WorkspaceOwnerBillingInfoSchema = z.object({
  isPaid: z.boolean().default(false),
  isPro: z.boolean().default(false),
  plan: z.string().default("internal"),
});
export type WorkspaceOwnerBillingInfo = z.output<typeof WorkspaceOwnerBillingInfoSchema>;

export const WorkspaceInfoSchema = z.object({
  appearance: z.record(z.string(), z.unknown()),
  createdAt: z.string().nullable(),
  id: z.string(),
  membershipId: z.string(),
  name: z.string(),
  organizationId: z.string().nullable(),
  ownerBilling: WorkspaceOwnerBillingInfoSchema,
  ownerId: z.string(),
  permissions: z.string().default("admin"),
  role: z.string().default("admin"),
  slug: z.string(),
  updatedAt: z.string().nullable(),
  workspaceId: z.string(),
  workspaceMode: z.string().default("personal"),
});
export type WorkspaceInfo = z.output<typeof WorkspaceInfoSchema>;

export const WorkspaceListResponseSchema = z.object({
  creationPolicy: z.record(z.string(), z.unknown()).nullable(),
  lastActiveWorkspaceId: z.string().nullable(),
  pinnedWorkspaceIds: z.array(z.string()),
  workspaces: z.array(WorkspaceInfoSchema),
});
export type WorkspaceListResponse = z.output<typeof WorkspaceListResponseSchema>;

export const WorkspaceMemberInfoSchema = z.object({
  image: z.string().nullable(),
  name: z.string(),
  userId: z.string(),
});
export type WorkspaceMemberInfo = z.output<typeof WorkspaceMemberInfoSchema>;

export const WorkspaceMembersResponseSchema = z.object({
  members: z.array(WorkspaceMemberInfoSchema),
});
export type WorkspaceMembersResponse = z.output<typeof WorkspaceMembersResponseSchema>;

export const WorkspacePermissionUserInfoSchema = z.object({
  email: z.string(),
  image: z.string().nullable(),
  isBilledAccount: z.boolean().default(true),
  isExternal: z.boolean().default(false),
  joinedAt: z.string().nullable(),
  name: z.string(),
  permissionType: z.string().default("admin"),
  roleSource: z.string().default("owner"),
  userId: z.string(),
});
export type WorkspacePermissionUserInfo = z.output<typeof WorkspacePermissionUserInfoSchema>;

export const WorkspacePermissionViewerInfoSchema = z.object({
  isAdmin: z.boolean().default(true),
  permissionType: z.string().default("admin"),
  userId: z.string(),
});
export type WorkspacePermissionViewerInfo = z.output<typeof WorkspacePermissionViewerInfoSchema>;

export const WorkspacePermissionsResponseSchema = z.object({
  total: z.number().int().default(0),
  users: z.array(WorkspacePermissionUserInfoSchema),
  viewer: WorkspacePermissionViewerInfoSchema,
});
export type WorkspacePermissionsResponse = z.output<typeof WorkspacePermissionsResponseSchema>;

export const WorkspaceResponseSchema = z.object({
  data: WorkspaceInfoSchema,
  workspace: WorkspaceInfoSchema,
});
export type WorkspaceResponse = z.output<typeof WorkspaceResponseSchema>;
