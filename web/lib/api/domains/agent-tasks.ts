/**
 * Agent Tasks domain client.
 *
 * Owns all agent task CRUD, messaging, events, interactions, artifacts,
 * quiz submissions, confirmations, and delivery acknowledgements.
 * Issue #40: extracted from the God API object in ``lib/lingxi/api.ts``.
 */

import { API_BASE } from '@/lib/api/config'
import { AGENT_EVENT_KINDS } from '@/lib/lingxi/agent-events'
import type {
  AgentTaskEvent,
  AgentTaskListItem,
  AgentTaskSnapshot,
  QuizSubmissionSnapshot,
  SimExecutionSnapshot,
} from '@/lib/lingxi/types'
import { request } from '../transport'
import type { SseOptions } from '../transport/sse'
import { subscribeSse } from '../transport/sse'

// ---------------------------------------------------------------------------
// Types shared across agent task operations
// ---------------------------------------------------------------------------

export interface LingxiAttachmentRef {
  key: string
  path?: string
  filename: string
  media_type: string
  size: number
}

export interface LingxiTaskContextOptions {
  resourceRefs?: Array<Record<string, unknown>>
  skillIds?: string[]
  idempotencyKey?: string
}

function idempotencyKey(prefix: string): string {
  return `${prefix}:${crypto.randomUUID()}`
}

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export function createAgentTask(
  prompt: string,
  attachments: LingxiAttachmentRef[] = [],
  context: LingxiTaskContextOptions = {}
) {
  return request<{ id: string; status: string }>('/agent-tasks', {
    method: 'POST',
    body: JSON.stringify({
      prompt,
      attachments,
      resource_refs: context.resourceRefs ?? [],
      skill_ids: context.skillIds ?? [],
      idempotency_key: context.idempotencyKey ?? idempotencyKey('agent-task:create'),
    }),
  })
}

export function getAgentTask(id: string) {
  return request<AgentTaskSnapshot>(`/agent-tasks/${id}`)
}

export function getAgentTasks(scope: 'active' | 'archived' = 'active') {
  return request<{ tasks: AgentTaskListItem[] }>(`/agent-tasks?scope=${scope}`)
}

export function updateAgentTask(
  taskId: string,
  patch: {
    title?: string
    is_pinned?: boolean
    is_unread?: boolean
    resources?: unknown[]
  }
) {
  return request<{
    id: string
    title: string
    is_pinned: boolean
    is_unread: boolean
    resources: Array<Record<string, unknown>>
  }>(`/agent-tasks/${taskId}`, { method: 'PATCH', body: JSON.stringify(patch) })
}

export function deleteAgentTask(taskId: string) {
  return request<{ id: string; deleted_at: string | null }>(`/agent-tasks/${taskId}`, {
    method: 'DELETE',
  })
}

export function restoreAgentTask(taskId: string) {
  return request<{ id: string; deleted_at: null }>(`/agent-tasks/${taskId}/restore`, {
    method: 'POST',
  })
}

export function forkAgentTask(taskId: string) {
  return request<{ id: string; status: string }>(`/agent-tasks/${taskId}/fork`, { method: 'POST' })
}

export function cancelAgentTask(taskId: string) {
  return request<{ id: string; status: string }>(`/agent-tasks/${taskId}/cancel`, {
    method: 'POST',
  })
}

// ---------------------------------------------------------------------------
// Messages
// ---------------------------------------------------------------------------

export function sendAgentMessage(
  taskId: string,
  message: string,
  attachments: LingxiAttachmentRef[] = [],
  context: LingxiTaskContextOptions = {}
) {
  return request<{ status: string }>(`/agent-tasks/${taskId}/messages`, {
    method: 'POST',
    body: JSON.stringify({
      message,
      attachments,
      resource_refs: context.resourceRefs ?? [],
      skill_ids: context.skillIds ?? [],
      idempotency_key: context.idempotencyKey ?? idempotencyKey('agent-message'),
    }),
  })
}

// ---------------------------------------------------------------------------
// Events & runtime graph
// ---------------------------------------------------------------------------

export function getAgentTaskEvents(id: string) {
  return request<{ events: AgentTaskEvent[]; protocol: 'v1' | 'legacy-v0' }>(
    `/agent-tasks/${id}/events?format=json`
  )
}

export function getRuntimeGraph(taskId: string) {
  return request<{
    id: string
    type: 'runtime-graph'
    taskId: string
    latestExecutionId: string | null
    status: string
    updatedAt: string | null
    workflowState: Record<string, unknown>
  }>(`/agent-tasks/${taskId}/runtime-graph`)
}

export function getAgentTaskDecisions(taskId: string) {
  return request<{ decisions: Array<Record<string, unknown>> }>(`/agent-tasks/${taskId}/decisions`)
}

export function subscribeAgentEvents(
  taskId: string,
  onEvent: (event: AgentTaskEvent) => void,
  options: SseOptions = {}
): () => void {
  return subscribeSse(`/agent-tasks/${taskId}/events`, onEvent, options)
}

/** Mothership Stream V1 history: durable envelopes only (issue #18). */
export function getAgentTaskV1Events(taskId: string, from = 0) {
  return request<{ events: AgentTaskEvent[]; protocol: 'v1' | 'legacy-v0' }>(
    `/agent-tasks/${taskId}/events?format=json&protocol=v1&last_event_id=${Math.max(0, from)}`
  )
}

/** Subscribe to the V1 envelope stream for one long-lived thread. */
export function subscribeAgentV1Events(
  taskId: string,
  onEvent: (event: AgentTaskEvent) => void,
  options: SseOptions = {}
): () => void {
  return subscribeSse(`/agent-tasks/${taskId}/events?protocol=v1`, onEvent, options)
}

// ---------------------------------------------------------------------------
// Interactions & quizzes
// ---------------------------------------------------------------------------

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
) {
  return request<{ status: string; interactionId: string }>(
    `/agent-tasks/${taskId}/interactions/${encodeURIComponent(interactionId)}/answers`,
    {
      method: 'POST',
      body: JSON.stringify({
        answers,
        idempotency_key:
          explicitIdempotencyKey ?? idempotencyKey(`interaction-answer:${interactionId}`),
      }),
    }
  )
}

export function submitAgentQuiz(
  taskId: string,
  submissionId: string,
  answers: Record<string, unknown>,
  requestKey = idempotencyKey(`quiz:${taskId}:${submissionId}`)
) {
  return request<{ status: string; submission: QuizSubmissionSnapshot }>(
    `/agent-tasks/${taskId}/quiz-submissions`,
    {
      method: 'POST',
      body: JSON.stringify({
        submission_id: submissionId,
        answers,
        idempotency_key: requestKey,
      }),
    }
  )
}

export function confirmAgentWork(
  taskId: string,
  input: { workItemId: string; approve: boolean; payloadDigest: string; idempotencyKey?: string }
) {
  return request<{ status: string; workItemId: string }>(`/agent-tasks/${taskId}/confirmations`, {
    method: 'POST',
    body: JSON.stringify({
      work_item_id: input.workItemId,
      approve: input.approve,
      payload_digest: input.payloadDigest,
      idempotency_key:
        input.idempotencyKey ?? idempotencyKey(`confirmation:${taskId}:${input.workItemId}`),
    }),
  })
}

export function ackAgentDelivery(
  taskId: string,
  artifact: string,
  requestKey = idempotencyKey(`delivery:${taskId}:${artifact}`)
) {
  return request<{
    artifact: string
    cursor: number
    delivery: AgentTaskSnapshot['delivery']['queue']
  }>(`/agent-tasks/${taskId}/delivery/${artifact}/ack`, {
    method: 'POST',
    headers: { 'Idempotency-Key': requestKey },
  })
}

// ---------------------------------------------------------------------------
// Artifacts
// ---------------------------------------------------------------------------

export function agentArtifactUrl(
  taskId: string,
  kind: 'lesson-intro' | 'lecture-deck' | 'visual'
): string {
  return `${API_BASE}/api/agent-tasks/${taskId}/artifacts/${kind}`
}

// ---------------------------------------------------------------------------
// Attachments
// ---------------------------------------------------------------------------

export async function uploadAttachment(file: File) {
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ''
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000))
  }
  return request<{
    key: string
    path: string
    filename: string
    media_type: string
    size: number
  }>('/attachments', {
    method: 'POST',
    body: JSON.stringify({
      filename: file.name,
      media_type: file.type || 'application/octet-stream',
      size: file.size,
      data: btoa(binary),
    }),
  })
}

// ---------------------------------------------------------------------------
// Execution logs
// ---------------------------------------------------------------------------

export function getExecutionSnapshot(executionId: string) {
  return request<SimExecutionSnapshot>(`/logs/execution/${encodeURIComponent(executionId)}`)
}

export function getLogByExecution(executionId: string) {
  return request<Record<string, unknown>>(`/logs/by-execution/${encodeURIComponent(executionId)}`)
}

// ---------------------------------------------------------------------------
// Learning records
// ---------------------------------------------------------------------------

export function recordLearningEvent(taskId: string, event: AgentTaskEvent) {
  return request<{ success: boolean; data: Record<string, unknown> }>('/lingxi/learning-records', {
    method: 'POST',
    body: JSON.stringify({ taskId, event }),
  })
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const KNOWN_AGENT_EVENT_KINDS = AGENT_EVENT_KINDS
