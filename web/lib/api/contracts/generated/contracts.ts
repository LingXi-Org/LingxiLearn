// 117 contracts generated from 105 paths.
// AUTO-GENERATED — do not edit by hand.
// Regenerate:  python scripts/export_openapi.py && bun run web/scripts/generate-rest-contracts.ts
// eslint-disable @typescript-eslint/no-explicit-any

import { z } from "zod";
import { defineRouteContract } from "@/lib/api/contracts/types";
import * as S from "./schemas";

export const decideSchedulePermissionsApiAgentInteractionsSchedulePermissionsPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/agent-interactions/schedule-permissions",
  response: {
    mode: "json" as const,
    schema: S.SchedulePermissionResponseSchema,
  },
});

export const listAgentTasksApiAgentTasksGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/agent-tasks",
  query: z.object({
    scope: z.string().default("active"),
  }),
  response: {
    mode: "json" as const,
    schema: S.AgentTaskListResponseSchema,
  },
});

export const getAgentTaskApiAgentTasks_TaskId_GetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/agent-tasks/[task_id]",
  params: z.object({
    task_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.AgentTaskSnapshotResponseSchema,
  },
});

export const patchAgentTaskApiAgentTasks_TaskId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/agent-tasks/[task_id]",
  params: z.object({
    task_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.AgentTaskMetaResponseSchema,
  },
});

export const deleteAgentTaskApiAgentTasks_TaskId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/agent-tasks/[task_id]",
  params: z.object({
    task_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.AgentTaskDeleteResponseSchema,
  },
});

export const cancelAgentTaskApiAgentTasks_TaskId_CancelPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/agent-tasks/[task_id]/cancel",
  params: z.object({
    task_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.AgentTaskCancelResponseSchema,
  },
});

export const agentTaskDecisionsApiAgentTasks_TaskId_DecisionsGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/agent-tasks/[task_id]/decisions",
  params: z.object({
    task_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.AgentDecisionsResponseSchema,
  },
});

export const ackAgentDeliveryApiAgentTasks_TaskId_Delivery_Artifact_AckPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/agent-tasks/[task_id]/delivery/[artifact]/ack",
  params: z.object({
    artifact: z.string(),
    task_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.AckDeliveryResponseSchema,
  },
});

export const streamAgentEventsApiAgentTasks_TaskId_EventsGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/agent-tasks/[task_id]/events",
  params: z.object({
    task_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.AgentTaskEventsResponseSchema,
  },
});

export const agentTaskEvidenceApiAgentTasks_TaskId_EvidenceGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/agent-tasks/[task_id]/evidence",
  params: z.object({
    task_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.AgentEvidenceResponseSchema,
  },
});

export const restoreAgentTaskApiAgentTasks_TaskId_RestorePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/agent-tasks/[task_id]/restore",
  params: z.object({
    task_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.AgentTaskRestoreResponseSchema,
  },
});

export const agentTaskRuntimeGraphApiAgentTasks_TaskId_RuntimeGraphGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/agent-tasks/[task_id]/runtime-graph",
  params: z.object({
    task_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.RuntimeGraphResponseSchema,
  },
});

export const legacyCopilotToolPermissionApiCopilotToolPermissionPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/copilot/tool-permission",
  response: {
    mode: "json" as const,
    schema: S.LegacyToolPermissionResponseSchema,
  },
});

export const storageStatusApiFilesStorageStatusGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/files/storage-status",
  response: {
    mode: "json" as const,
    schema: S.StorageStatusResponseSchema,
  },
});

export const createUploadApiFilesUploadsPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/files/uploads",
  response: {
    mode: "json" as const,
    schema: S.CreateUploadResponseSchema,
  },
});

export const abortUploadApiFilesUploads_UploadId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/files/uploads/[upload_id]",
  params: z.object({
    upload_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.UploadStateResponseSchema,
  },
});

export const completeUploadApiFilesUploads_UploadId_CompletePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/files/uploads/[upload_id]/complete",
  params: z.object({
    upload_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.UploadStateResponseSchema,
  },
});

export const createUploadPartUrlsApiFilesUploads_UploadId_PartsPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/files/uploads/[upload_id]/parts",
  params: z.object({
    upload_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.UploadPartsResponseSchema,
  },
});

export const listKnowledgeApiKnowledgeGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/knowledge",
  query: z.object({
    includeArchived: z.boolean().default(false),
    scope: z.string().default("active"),
    workspaceId: z.string().nullable(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeBasesResponseSchema,
  },
});

export const createKnowledgeApiKnowledgePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/knowledge",
  response: {
    mode: "json" as const,
    schema: S.KnowledgeBaseResponseSchema,
  },
});

export const searchKnowledgeApiKnowledgeSearchGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/knowledge/search",
  query: z.object({
    limit: z.number().int().default(20),
    q: z.string().default(""),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeSearchResponseSchema,
  },
});

export const getKnowledgeApiKnowledge_BaseId_GetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/knowledge/[base_id]",
  params: z.object({
    base_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeBaseResponseSchema,
  },
});

export const updateKnowledgeApiKnowledge_BaseId_PutContract = defineRouteContract({
  method: "PUT" as const,
  path: "/api/knowledge/[base_id]",
  params: z.object({
    base_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeBaseResponseSchema,
  },
});

export const updateKnowledgeApiKnowledge_BaseId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/knowledge/[base_id]",
  params: z.object({
    base_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeBaseResponseSchema,
  },
});

export const archiveKnowledgeApiKnowledge_BaseId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/knowledge/[base_id]",
  params: z.object({
    base_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeMessageResponseSchema,
  },
});

export const listDocumentsApiKnowledge_BaseId_DocumentsGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/knowledge/[base_id]/documents",
  params: z.object({
    base_id: z.string(),
  }),
  query: z.object({
    enabledFilter: z.string().nullable(),
    includeArchived: z.boolean().default(false),
    limit: z.number().int().default(50),
    offset: z.number().int().default(0),
    search: z.string().nullable(),
    sortBy: z.string().nullable(),
    sortOrder: z.string().nullable(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeDocumentsResponseSchema,
  },
});

export const createDocumentApiKnowledge_BaseId_DocumentsPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/knowledge/[base_id]/documents",
  params: z.object({
    base_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeDocumentResponseSchema,
  },
});

export const bulkUpdateDocumentsApiKnowledge_BaseId_DocumentsPatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/knowledge/[base_id]/documents",
  params: z.object({
    base_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeBulkDocumentsResponseSchema,
  },
});

export const completeKnowledgeUploadApiKnowledge_BaseId_DocumentsUploads_UploadId_CompletePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/knowledge/[base_id]/documents/uploads/[upload_id]/complete",
  params: z.object({
    base_id: z.string(),
    upload_id: z.string(),
  }),
  query: z.object({
    workspaceId: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.UploadStateResponseSchema,
  },
});

export const upsertDocumentApiKnowledge_BaseId_DocumentsUpsertPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/knowledge/[base_id]/documents/upsert",
  params: z.object({
    base_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeDocumentUpsertResponseSchema,
  },
});

export const getDocumentApiKnowledge_BaseId_Documents_DocumentId_GetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]",
  params: z.object({
    base_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeDocumentResponseSchema,
  },
});

export const updateDocumentApiKnowledge_BaseId_Documents_DocumentId_PutContract = defineRouteContract({
  method: "PUT" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]",
  params: z.object({
    base_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeDocumentResponseSchema,
  },
});

export const updateDocumentApiKnowledge_BaseId_Documents_DocumentId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]",
  params: z.object({
    base_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeDocumentResponseSchema,
  },
});

export const archiveDocumentApiKnowledge_BaseId_Documents_DocumentId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]",
  params: z.object({
    base_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeMessageResponseSchema,
  },
});

export const listChunksApiKnowledge_BaseId_Documents_DocumentId_ChunksGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]/chunks",
  params: z.object({
    base_id: z.string(),
    document_id: z.string(),
  }),
  query: z.object({
    enabled: z.string().nullable(),
    limit: z.number().int().default(50),
    offset: z.number().int().default(0),
    search: z.string().nullable(),
    sortBy: z.string().nullable(),
    sortOrder: z.string().nullable(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeChunksResponseSchema,
  },
});

export const createChunkApiKnowledge_BaseId_Documents_DocumentId_ChunksPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]/chunks",
  params: z.object({
    base_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeChunkResponseSchema,
  },
});

export const bulkUpdateChunksApiKnowledge_BaseId_Documents_DocumentId_ChunksPatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]/chunks",
  params: z.object({
    base_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeBulkChunksResponseSchema,
  },
});

export const getChunkApiKnowledge_BaseId_Documents_DocumentId_Chunks_ChunkId_GetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]/chunks/[chunk_id]",
  params: z.object({
    base_id: z.string(),
    chunk_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeChunkResponseSchema,
  },
});

export const updateChunkApiKnowledge_BaseId_Documents_DocumentId_Chunks_ChunkId_PutContract = defineRouteContract({
  method: "PUT" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]/chunks/[chunk_id]",
  params: z.object({
    base_id: z.string(),
    chunk_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeChunkResponseSchema,
  },
});

export const updateChunkApiKnowledge_BaseId_Documents_DocumentId_Chunks_ChunkId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]/chunks/[chunk_id]",
  params: z.object({
    base_id: z.string(),
    chunk_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeChunkResponseSchema,
  },
});

export const deleteChunkApiKnowledge_BaseId_Documents_DocumentId_Chunks_ChunkId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]/chunks/[chunk_id]",
  params: z.object({
    base_id: z.string(),
    chunk_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeMessageResponseSchema,
  },
});

export const restoreDocumentApiKnowledge_BaseId_Documents_DocumentId_RestorePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]/restore",
  params: z.object({
    base_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeDocumentResponseSchema,
  },
});

export const listDocumentTagDefinitionsApiKnowledge_BaseId_Documents_DocumentId_TagDefinitionsGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]/tag-definitions",
  params: z.object({
    base_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeTagListResponseSchema,
  },
});

export const saveDocumentTagDefinitionsApiKnowledge_BaseId_Documents_DocumentId_TagDefinitionsPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]/tag-definitions",
  params: z.object({
    base_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.DocumentTagSaveResponseSchema,
  },
});

export const deleteDocumentTagDefinitionsApiKnowledge_BaseId_Documents_DocumentId_TagDefinitionsDeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/knowledge/[base_id]/documents/[document_id]/tag-definitions",
  params: z.object({
    base_id: z.string(),
    document_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.SuccessResponseSchema,
  },
});

export const nextAvailableTagSlotApiKnowledge_BaseId_NextAvailableSlotGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/knowledge/[base_id]/next-available-slot",
  params: z.object({
    base_id: z.string(),
  }),
  query: z.object({
    fieldType: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeNextSlotResponseSchema,
  },
});

export const restoreKnowledgeApiKnowledge_BaseId_RestorePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/knowledge/[base_id]/restore",
  params: z.object({
    base_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeBaseResponseSchema,
  },
});

export const listTagDefinitionsApiKnowledge_BaseId_TagDefinitionsGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/knowledge/[base_id]/tag-definitions",
  params: z.object({
    base_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeTagsResponseSchema,
  },
});

export const updateTagDefinitionApiKnowledge_BaseId_TagDefinitions_TagId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/knowledge/[base_id]/tag-definitions/[tag_id]",
  params: z.object({
    base_id: z.string(),
    tag_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeTagResponseSchema,
  },
});

export const deleteTagDefinitionApiKnowledge_BaseId_TagDefinitions_TagId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/knowledge/[base_id]/tag-definitions/[tag_id]",
  params: z.object({
    base_id: z.string(),
    tag_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.SuccessResponseSchema,
  },
});

export const tagUsageApiKnowledge_BaseId_TagUsageGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/knowledge/[base_id]/tag-usage",
  params: z.object({
    base_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.KnowledgeTagUsageResponseSchema,
  },
});

export const recordLearningEventApiLingxiLearningRecordsPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/lingxi/learning-records",
  response: {
    mode: "json" as const,
    schema: S.LearningRecordResponseSchema,
  },
});

export const executionSnapshotApiLogsExecution_ExecutionId_GetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/logs/execution/[execution_id]",
  params: z.object({
    execution_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.ExecutionSnapshotResponseSchema,
  },
});

export const meContextApiMeContextGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/me/context",
  response: {
    mode: "json" as const,
    schema: S.ContextResponseSchema,
  },
});

export const learningProfileApiMeLearningProfileGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/me/learning-profile",
  response: {
    mode: "json" as const,
    schema: S.LearningProfileResponseSchema,
  },
});

export const overrideLearningProfileApiMeLearningProfile_KnowledgePointId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/me/learning-profile/[knowledge_point_id]",
  params: z.object({
    knowledge_point_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.ProfileChangeResponseSchema,
  },
});

export const meMasteryApiMeMasteryGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/me/mastery",
  response: {
    mode: "json" as const,
    schema: S.MasteryResponseSchema,
  },
});

export const getPreferencesApiMePreferencesGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/me/preferences",
  response: {
    mode: "json" as const,
    schema: S.PreferencesResponseSchema,
  },
});

export const patchPreferencesApiMePreferencesPatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/me/preferences",
  response: {
    mode: "json" as const,
    schema: S.PreferencesResponseSchema,
  },
});

export const listPacksApiPacksGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/packs",
  response: {
    mode: "json" as const,
    schema: S.PacksResponseSchema,
  },
});

export const listPinnedItemsApiPinnedItemsGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/pinned-items",
  query: z.object({
    resourceType: z.string().nullable(),
    workspaceId: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.PinnedItemsResponseSchema,
  },
});

export const createPinnedItemApiPinnedItemsPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/pinned-items",
  response: {
    mode: "json" as const,
    schema: S.PinnedItemResponseSchema,
  },
});

export const deletePinnedItemApiPinnedItems_ResourceType__ResourceId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/pinned-items/[resource_type]/[resource_id]",
  params: z.object({
    resource_id: z.string(),
    resource_type: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.SuccessResponseSchema,
  },
});

export const skillRegistryApiSkillRegistryGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/skill-registry",
  response: {
    mode: "json" as const,
    schema: S.SkillRegistryResponseSchema,
  },
});

export const listSkillsApiSkillsGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/skills",
  response: {
    mode: "json" as const,
    schema: S.SkillsResponseSchema,
  },
});

export const createSkillApiSkillsPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/skills",
  response: {
    mode: "json" as const,
    schema: S.SkillCreateResponseSchema,
  },
});

export const updateSkillApiSkills_SkillId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/skills/[skill_id]",
  params: z.object({
    skill_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.SkillUpdateResponseSchema,
  },
});

export const deleteSkillApiSkills_SkillId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/skills/[skill_id]",
  params: z.object({
    skill_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.SuccessResponseSchema,
  },
});

export const listTablesApiTableGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/table",
  query: z.object({
    includeArchived: z.boolean().nullable(),
    scope: z.string().default("active"),
    workspaceId: z.string().default("lingxi"),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableListResponseSchema,
  },
});

export const createTableApiTablePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/table",
  response: {
    mode: "json" as const,
    schema: S.TableResponseSchema,
  },
});

export const getTableApiTable_TableId_GetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/table/[table_id]",
  params: z.object({
    table_id: z.string(),
  }),
  query: z.object({
    workspaceId: z.string().default("lingxi"),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableResponseSchema,
  },
});

export const updateTableApiTable_TableId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/table/[table_id]",
  params: z.object({
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableResponseSchema,
  },
});

export const archiveTableApiTable_TableId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/table/[table_id]",
  params: z.object({
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableMessageResponseSchema,
  },
});

export const addColumnApiTable_TableId_ColumnsPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/table/[table_id]/columns",
  params: z.object({
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableColumnsResponseSchema,
  },
});

export const updateColumnApiTable_TableId_ColumnsPatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/table/[table_id]/columns",
  params: z.object({
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableColumnsResponseSchema,
  },
});

export const deleteColumnApiTable_TableId_ColumnsDeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/table/[table_id]/columns",
  params: z.object({
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableColumnsResponseSchema,
  },
});

export const importTableRowsApiTable_TableId_ImportPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/table/[table_id]/import",
  params: z.object({
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableImportRowsResponseSchema,
  },
});

export const queryRowsApiTable_TableId_QueryGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/table/[table_id]/query",
  params: z.object({
    table_id: z.string(),
  }),
  query: z.object({
    limit: z.number().int().default(100),
    offset: z.number().int().default(0),
    q: z.string().default(""),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableRowsQueryResponseSchema,
  },
});

export const restoreTableApiTable_TableId_RestorePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/table/[table_id]/restore",
  params: z.object({
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableResponseSchema,
  },
});

export const listRowsApiTable_TableId_RowsGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/table/[table_id]/rows",
  params: z.object({
    table_id: z.string(),
  }),
  query: z.object({
    limit: z.number().int().default(100),
    offset: z.number().int().default(0),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableRowsResponseSchema,
  },
});

export const createRowsApiTable_TableId_RowsPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/table/[table_id]/rows",
  params: z.object({
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableRowsCreateResponseSchema,
  },
});

export const findRowsApiTable_TableId_RowsFindGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/table/[table_id]/rows/find",
  params: z.object({
    table_id: z.string(),
  }),
  query: z.object({
    q: z.string().default(""),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableRowsFindResponseSchema,
  },
});

export const upsertRowsApiTable_TableId_RowsUpsertPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/table/[table_id]/rows/upsert",
  params: z.object({
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableRowsUpsertResponseSchema,
  },
});

export const updateRowApiTable_TableId_Rows_RowId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/table/[table_id]/rows/[row_id]",
  params: z.object({
    row_id: z.string(),
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableRowResponseSchema,
  },
});

export const deleteRowApiTable_TableId_Rows_RowId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/table/[table_id]/rows/[row_id]",
  params: z.object({
    row_id: z.string(),
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableEmptyDataResponseSchema,
  },
});

export const listViewsApiTable_TableId_ViewsGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/table/[table_id]/views",
  params: z.object({
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableViewsResponseSchema,
  },
});

export const createViewApiTable_TableId_ViewsPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/table/[table_id]/views",
  params: z.object({
    table_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableViewResponseSchema,
  },
});

export const updateViewApiTable_TableId_Views_ViewId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/table/[table_id]/views/[view_id]",
  params: z.object({
    table_id: z.string(),
    view_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableViewResponseSchema,
  },
});

export const deleteViewApiTable_TableId_Views_ViewId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/table/[table_id]/views/[view_id]",
  params: z.object({
    table_id: z.string(),
    view_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.TableViewDeletedResponseSchema,
  },
});

export const getUserSettingsApiUsersMeSettingsGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/users/me/settings",
  response: {
    mode: "json" as const,
    schema: S.UserSettingsResponseSchema,
  },
});

export const updateUserSettingsApiUsersMeSettingsPatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/users/me/settings",
  response: {
    mode: "json" as const,
    schema: S.UserSettingsUpdateResponseSchema,
  },
});

export const listWorkspacesApiWorkspacesGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/workspaces",
  response: {
    mode: "json" as const,
    schema: S.WorkspaceListResponseSchema,
  },
});

export const getWorkspaceApiWorkspaces_WorkspaceId_GetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/workspaces/[workspace_id]",
  params: z.object({
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspaceResponseSchema,
  },
});

export const updateWorkspaceApiWorkspaces_WorkspaceId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/workspaces/[workspace_id]",
  params: z.object({
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspaceResponseSchema,
  },
});

export const listFilesApiWorkspaces_WorkspaceId_FilesGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/workspaces/[workspace_id]/files",
  params: z.object({
    workspace_id: z.string(),
  }),
  query: z.object({
    folderId: z.string().nullable(),
    scope: z.string().default("active"),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspaceFilesResponseSchema,
  },
});

export const bulkArchiveFileItemsApiWorkspaces_WorkspaceId_FilesBulkArchivePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/workspaces/[workspace_id]/files/bulk-archive",
  params: z.object({
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.FolderArchiveResponseSchema,
  },
});

export const listFoldersApiWorkspaces_WorkspaceId_FilesFoldersGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/workspaces/[workspace_id]/files/folders",
  params: z.object({
    workspace_id: z.string(),
  }),
  query: z.object({
    scope: z.string().default("active"),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspaceFoldersResponseSchema,
  },
});

export const updateFolderApiWorkspaces_WorkspaceId_FilesFolders_FolderId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/workspaces/[workspace_id]/files/folders/[folder_id]",
  params: z.object({
    folder_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspaceFolderResponseSchema,
  },
});

export const archiveFolderApiWorkspaces_WorkspaceId_FilesFolders_FolderId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/workspaces/[workspace_id]/files/folders/[folder_id]",
  params: z.object({
    folder_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.FolderArchiveResponseSchema,
  },
});

export const restoreFolderApiWorkspaces_WorkspaceId_FilesFolders_FolderId_RestorePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/workspaces/[workspace_id]/files/folders/[folder_id]/restore",
  params: z.object({
    folder_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.FolderRestoreResponseSchema,
  },
});

export const moveFileItemsApiWorkspaces_WorkspaceId_FilesMovePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/workspaces/[workspace_id]/files/move",
  params: z.object({
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.MoveItemsResponseSchema,
  },
});

export const getFileApiWorkspaces_WorkspaceId_Files_FileId_GetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/workspaces/[workspace_id]/files/[file_id]",
  params: z.object({
    file_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspaceFileResponseSchema,
  },
});

export const updateFileApiWorkspaces_WorkspaceId_Files_FileId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/workspaces/[workspace_id]/files/[file_id]",
  params: z.object({
    file_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspaceFileResponseSchema,
  },
});

export const deleteFileApiWorkspaces_WorkspaceId_Files_FileId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/workspaces/[workspace_id]/files/[file_id]",
  params: z.object({
    file_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.SuccessResponseSchema,
  },
});

export const getFileContentApiWorkspaces_WorkspaceId_Files_FileId_ContentGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/workspaces/[workspace_id]/files/[file_id]/content",
  params: z.object({
    file_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspaceFileContentResponseSchema,
  },
});

export const updateFileContentApiWorkspaces_WorkspaceId_Files_FileId_ContentPutContract = defineRouteContract({
  method: "PUT" as const,
  path: "/api/workspaces/[workspace_id]/files/[file_id]/content",
  params: z.object({
    file_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspaceFileResponseSchema,
  },
});

export const updateFileDimensionsApiWorkspaces_WorkspaceId_Files_FileId_DimensionsPatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/workspaces/[workspace_id]/files/[file_id]/dimensions",
  params: z.object({
    file_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.SuccessResponseSchema,
  },
});

export const fileDownloadUrlApiWorkspaces_WorkspaceId_Files_FileId_DownloadPostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/workspaces/[workspace_id]/files/[file_id]/download",
  params: z.object({
    file_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.FileDownloadUrlResponseSchema,
  },
});

export const restoreFileApiWorkspaces_WorkspaceId_Files_FileId_RestorePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/workspaces/[workspace_id]/files/[file_id]/restore",
  params: z.object({
    file_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.SuccessResponseSchema,
  },
});

export const listFoldersApiWorkspaces_WorkspaceId_FoldersGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/workspaces/[workspace_id]/folders",
  params: z.object({
    workspace_id: z.string(),
  }),
  query: z.object({
    scope: z.string().default("active"),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspaceFoldersResponseSchema,
  },
});

export const updateFolderApiWorkspaces_WorkspaceId_Folders_FolderId_PatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/workspaces/[workspace_id]/folders/[folder_id]",
  params: z.object({
    folder_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspaceFolderResponseSchema,
  },
});

export const archiveFolderApiWorkspaces_WorkspaceId_Folders_FolderId_DeleteContract = defineRouteContract({
  method: "DELETE" as const,
  path: "/api/workspaces/[workspace_id]/folders/[folder_id]",
  params: z.object({
    folder_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.FolderArchiveResponseSchema,
  },
});

export const restoreFolderApiWorkspaces_WorkspaceId_Folders_FolderId_RestorePostContract = defineRouteContract({
  method: "POST" as const,
  path: "/api/workspaces/[workspace_id]/folders/[folder_id]/restore",
  params: z.object({
    folder_id: z.string(),
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.FolderRestoreResponseSchema,
  },
});

export const listWorkspaceMembersApiWorkspaces_WorkspaceId_MembersGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/workspaces/[workspace_id]/members",
  params: z.object({
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspaceMembersResponseSchema,
  },
});

export const getWorkspacePermissionsApiWorkspaces_WorkspaceId_PermissionsGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/api/workspaces/[workspace_id]/permissions",
  params: z.object({
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.WorkspacePermissionsResponseSchema,
  },
});

export const updateWorkspacePermissionsApiWorkspaces_WorkspaceId_PermissionsPatchContract = defineRouteContract({
  method: "PATCH" as const,
  path: "/api/workspaces/[workspace_id]/permissions",
  params: z.object({
    workspace_id: z.string(),
  }),
  response: {
    mode: "json" as const,
    schema: S.MessageResponseSchema,
  },
});

export const liveLiveGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/live",
  response: {
    mode: "json" as const,
    schema: S.LivenessResponseSchema,
  },
});

export const readyReadyGetContract = defineRouteContract({
  method: "GET" as const,
  path: "/ready",
  response: {
    mode: "json" as const,
    schema: S.ReadinessResponseSchema,
  },
});
