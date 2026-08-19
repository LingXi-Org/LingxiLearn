/**
 * Lingxi API — compatibility facade.
 *
 * The God API object has been decomposed into domain clients under
 * ``lib/api/domains/``. This module re-exports the public surface so
 * existing callers continue to work. New code should import directly
 * from the domain modules (issue #40).
 *
 * Transport ownership:
 * - JSON: ``lib/api/transport/http.ts``
 * - SSE:  ``lib/api/transport/sse.ts``
 *
 * @deprecated Import from ``lib/api/domains/*`` instead.
 */

import { AGENT_EVENT_KINDS } from './agent-events'
import type {
  AgentTaskEvent,
  RunEvent,
  SessionSnapshot,
  SimExecutionSnapshot,
  QuizSubmissionSnapshot,
  AgentTaskListItem,
  AgentTaskSnapshot,
  NativeSkill,
  Pack,
  SessionListItem,
} from './types'

// Re-export types that callers may import from this module.
export type {
  WorkspaceFileItem,
  WorkspaceFolderItem,
  WorkspaceTableItem,
  KnowledgeBaseItem,
  KnowledgeDocumentItem,
} from './types'

// ---------------------------------------------------------------------------
// Transport re-exports (single owner is lib/api/transport)
// ---------------------------------------------------------------------------

export { API_BASE } from '@/lib/api/config'
export {
  ApiError,
  authorizedFetch,
  request,
  apiUrl,
  setAccessTokenProvider,
  setAuthenticationFailureHandler,
  setSessionRefreshHandler,
  setAccessTokenRefreshHandler,
} from '@/lib/api/transport/http'
export type { AccessTokenProvider } from '@/lib/api/transport/http'
export { subscribeSse } from '@/lib/api/transport/sse'
export type { SseOptions } from '@/lib/api/transport/sse'

// ---------------------------------------------------------------------------
// Domain re-exports (backwards-compatible ``api.xxx`` shape)
// ---------------------------------------------------------------------------

import {
  getHealth,
  getPacks,
  getSkills,
  createSkill as _createSkill,
  updateSkill as _updateSkill,
  deleteSkill as _deleteSkill,
} from '@/lib/api/domains/catalogue'

import * as workspaceClient from '@/lib/api/domains/workspace'
import * as knowledgeClient from '@/lib/api/domains/knowledge'
import * as agentTasksClient from '@/lib/api/domains/agent-tasks'
import * as userSettingsClient from '@/lib/api/domains/user-settings'
import * as sessionsClient from '@/lib/api/domains/sessions'
import { fetchArtifactBlob } from '@/lib/api/transport/http'

// ---------------------------------------------------------------------------
// Legacy LingxiAttachmentRef / LingxiTaskContextOptions
// ---------------------------------------------------------------------------

export type {
  LingxiAttachmentRef,
  LingxiTaskContextOptions,
} from '@/lib/api/domains/agent-tasks'

// ---------------------------------------------------------------------------
// God object (deprecated — use domain clients directly)
// ---------------------------------------------------------------------------

export const api = {
  // Catalogue
  health: getHealth,
  packs: getPacks,
  skills: getSkills,

  // Workspace
  workspace: workspaceClient.getWorkspace,
  updateWorkspace: workspaceClient.updateWorkspace,
  workspaceFolders: workspaceClient.getWorkspaceFolders,
  createWorkspaceFolder: workspaceClient.createWorkspaceFolder,
  updateWorkspaceFolder: workspaceClient.updateWorkspaceFolder,
  archiveWorkspaceFolder: workspaceClient.archiveWorkspaceFolder,
  restoreWorkspaceFolder: workspaceClient.restoreWorkspaceFolder,
  moveWorkspaceItems: workspaceClient.moveWorkspaceItems,
  workspaceFiles: workspaceClient.getWorkspaceFiles,
  createWorkspaceFile: workspaceClient.createWorkspaceFile,
  workspaceFile: workspaceClient.getWorkspaceFile,
  workspaceFileContent: workspaceClient.getWorkspaceFileContent,
  updateWorkspaceFileContent: workspaceClient.updateWorkspaceFileContent,
  archiveWorkspaceFile: workspaceClient.archiveWorkspaceFile,
  workspaceTables: workspaceClient.getWorkspaceTables,
  createWorkspaceTable: workspaceClient.createWorkspaceTable,
  workspaceTable: workspaceClient.getWorkspaceTable,
  workspaceTableRows: workspaceClient.getWorkspaceTableRows,
  createWorkspaceRows: workspaceClient.createWorkspaceRows,
  updateWorkspaceRow: workspaceClient.updateWorkspaceRow,
  deleteWorkspaceRow: workspaceClient.deleteWorkspaceRow,
  workspaceTableViews: workspaceClient.getWorkspaceTableViews,
  createWorkspaceTableView: workspaceClient.createWorkspaceTableView,

  // Knowledge
  workspaceKnowledge: knowledgeClient.getKnowledgeBases,
  createKnowledgeBase: knowledgeClient.createKnowledgeBase,
  knowledgeDocuments: knowledgeClient.getKnowledgeDocuments,
  createKnowledgeDocument: knowledgeClient.createKnowledgeDocument,
  updateKnowledgeDocument: knowledgeClient.updateKnowledgeDocument,

  // Agent Tasks
  createAgentTask: agentTasksClient.createAgentTask,
  agentTask: agentTasksClient.getAgentTask,
  agentTaskEvents: agentTasksClient.getAgentTaskEvents,
  runtimeGraph: agentTasksClient.getRuntimeGraph,
  agentTaskDecisions: agentTasksClient.getAgentTaskDecisions,
  agentMessage: agentTasksClient.sendAgentMessage,
  agentTasks: agentTasksClient.getAgentTasks,
  updateAgentTask: agentTasksClient.updateAgentTask,
  deleteAgentTask: agentTasksClient.deleteAgentTask,
  restoreAgentTask: agentTasksClient.restoreAgentTask,
  forkAgentTask: agentTasksClient.forkAgentTask,
  cancelAgentTask: agentTasksClient.cancelAgentTask,
  uploadAttachment: agentTasksClient.uploadAttachment,
  submitAgentQuiz: agentTasksClient.submitAgentQuiz,
  confirmAgentWork: agentTasksClient.confirmAgentWork,
  ackAgentDelivery: agentTasksClient.ackAgentDelivery,
  agentArtifactUrl: agentTasksClient.agentArtifactUrl,
  copilotToolPermission: agentTasksClient.copilotToolPermission,
  executionSnapshot: agentTasksClient.getExecutionSnapshot,
  logByExecution: agentTasksClient.getLogByExecution,
  recordLearningEvent: agentTasksClient.recordLearningEvent,

  // Skills
  createSkill: _createSkill,
  updateSkill: _updateSkill,
  deleteSkill: _deleteSkill,

  // Sessions
  createSession: sessionsClient.createSession,
  session: sessionsClient.getSession,
  answer: sessionsClient.submitAnswer,
  report: sessionsClient.getSessionReport,
  artifactUrl: sessionsClient.artifactUrl,
  fetchArtifact: fetchArtifactBlob,

  // User / Settings
  userProfile: userSettingsClient.getUserProfile,
  userSettings: userSettingsClient.getUserSettings,
  updateUserSettings: userSettingsClient.updateUserSettings,
  context: userSettingsClient.getContext,
  mastery: userSettingsClient.getMastery,
  preferences: userSettingsClient.getPreferences,
  updatePreferences: userSettingsClient.updatePreferences,
  billing: userSettingsClient.getBilling,
  billingInvoices: userSettingsClient.getBillingInvoices,
  billingPortal: userSettingsClient.getBillingPortal,
  purchaseCredits: userSettingsClient.purchaseCredits,
  switchBillingPlan: userSettingsClient.switchBillingPlan,
  billingUsageLimits: userSettingsClient.getBillingUsageLimits,
  v2BillingStatus: userSettingsClient.getV2BillingStatus,
  v2BillingLogs: userSettingsClient.getV2BillingLogs,
  usageLogs: userSettingsClient.getUsageLogs,

  // Logs
  logs: () =>
    import('@/lib/api/transport/http').then(({ request }) =>
      request<{ data: Array<Record<string, unknown>> }>('/logs?workspaceId=lingxi')
    ),
}

// ---------------------------------------------------------------------------
// SSE subscriptions (re-exported from domain clients)
// ---------------------------------------------------------------------------

export function subscribeEvents(
  sessionId: string,
  onEvent: (event: RunEvent) => void,
  options: import('@/lib/api/transport/sse').SseOptions = {}
): () => void {
  return sessionsClient.subscribeSessionEvents(sessionId, onEvent, options)
}

export function subscribeAgentEvents(
  taskId: string,
  onEvent: (event: AgentTaskEvent) => void,
  options: import('@/lib/api/transport/sse').SseOptions = {}
): () => void {
  return agentTasksClient.subscribeAgentEvents(taskId, onEvent, options)
}

/** Mothership Stream V1 history: durable envelopes only (issue #18). */
export function agentTaskV1Events(
  taskId: string,
  from = 0
): Promise<{ events: AgentTaskEvent[] }> {
  return agentTasksClient.getAgentTaskV1Events(taskId, from)
}

/** Subscribe to the V1 envelope stream for one long-lived thread. */
export function subscribeAgentV1Events(
  taskId: string,
  onEvent: (event: AgentTaskEvent) => void,
  options: import('@/lib/api/transport/sse').SseOptions = {}
): () => void {
  return agentTasksClient.subscribeAgentV1Events(taskId, onEvent, options)
}

/** Answer one blocking interaction through the structured API (issue #18 §10.4). */
export function answerAgentInteraction(
  taskId: string,
  interactionId: string,
  answers: Array<{
    questionId: string
    selectedOptionIds?: string[]
    text?: string | null
  }>,
  explicitIdempotencyKey?: string
): Promise<{ status: string; interactionId: string }> {
  return agentTasksClient.answerAgentInteraction(taskId, interactionId, answers, explicitIdempotencyKey)
}

export const KNOWN_EVENT_KINDS = [
  'run.started',
  'run.ended',
  'run.failed',
  'run.paused',
  'node.started',
  'node.completed',
  'node.held',
  'node.revising',
  'delivery.queued',
  'delivery.unlocked',
  'node.retrying',
  'interrupt.raised',
  'assistant.delta',
  'stage.changed',
  'tool.started',
  'tool.completed',
  'evidence.added',
  'coach.move',
  'hint.escalated',
  'answer.judged',
  'mastery.updated',
  'probe.graded',
  'verify.graded',
  'step.completed',
  'plan.ready',
  'report.ready',
]

export const KNOWN_AGENT_EVENT_KINDS = AGENT_EVENT_KINDS
