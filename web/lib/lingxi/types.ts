/** Small wire types for the LingxiGraph REST/SSE API. */

export type SceneKind = 'probe' | 'packet_lab' | 'attribution' | 'verify' | 'report'

export interface LingxiWorkspaceHostContext {
  workspace: {
    id: string
    name: string
    workspaceMode: 'personal'
    billedAccountUserId: string
  }
  hostOrganizationId: string | null
  ownerBilling: {
    plan: string
    status: string | null
    isPaid: boolean
    isPro: boolean
    isTeam: boolean
    isEnterprise: boolean
    isOrgScoped: boolean
    organizationId: string | null
    billingInterval: 'month' | 'year'
    billingBlocked: boolean
    billingBlockedReason: 'dispute' | 'payment_failed' | null
  }
  viewer: {
    permission: 'read' | 'write' | 'admin'
    isHostOrganizationMember: boolean
    isHostOrganizationAdmin: boolean
  }
}

export interface Choice {
  value: string
  label: string
}

export interface MissionSummary {
  id: string
  title: string
  subtitle: string
  summary: string
  why_not_chat: string
  concepts: string[]
  estimated_minutes: number
  steps: number
}

export interface Pack {
  id: string
  title: string
  version: string
  description: string
  concepts: Array<{ id: string; title: string; summary: string; requires: string[] }>
  missions: MissionSummary[]
}

export interface NativeSkill {
  id: string
  name?: string
  display_name: string
  description: string
  version: string
  license: string
  compatibility: string
  content: string
  source?: 'system' | 'personal' | string
  is_system?: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface AgentTaskEvent {
  sequence: number
  kind: string
  agent: string
  payload: Record<string, unknown>
  ts: string | null
  execution_id?: string | null
  run_id?: string | null
  step?: number | null
  node?: string | null
  task_id?: string | null
  namespace?: unknown
  checkpoint_id?: string | null
  span_id?: string | null
  executionSnapshot?: Record<string, unknown> | null
  runtime?: {
    execution_id?: string | null
    run_id?: string | null
    step?: number
    node?: string | null
    task_id?: string | null
    namespace?: unknown
    checkpoint_id?: string | null
    span_id?: string | null
    [key: string]: unknown
  }
}

export interface RunEvent {
  sequence: number
  kind: string
  node: string
  payload: Record<string, unknown>
  ts: string
}

export type AgentTaskStatus =
  | 'queued'
  | 'running'
  | 'awaiting_user'
  | 'handed_off'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'timed_out'
  | 'budget_exceeded'
  | 'cancelled'

export type AgentTurnStatus =
  | 'active'
  | 'awaiting_user'
  | 'delivered'
  | 'failed'
  | 'cancelled'
  | string

export type AgentGoalStatus = 'open' | 'active' | 'completed' | 'failed' | 'cancelled' | string

export interface AgentWorkItem {
  id: string
  candidateId: string
  capability: string
  dependsOn: string[]
  status: string
  planRevision: number
  provider: string
  payloadDigest?: string | null
}

export interface AgentTaskListItem {
  id: string
  prompt: string
  title?: string
  status: AgentTaskStatus
  intent: { topic?: string }
  created_at: string | null
  updated_at: string | null
  is_pinned?: boolean
  is_unread?: boolean
  deleted_at?: string | null
  resources?: unknown[]
}

export interface SessionListItem {
  id: string
  mission_id: string
  pack_id: string
  status: SessionSnapshot['status']
  created_at: string | null
}

export interface SessionSnapshot {
  id: string
  status: 'created' | 'running' | 'awaiting_learner' | 'done' | 'failed' | 'cancelled'
  error: string
  pack_id: string
  pack_version: string
  mission: {
    id: string
    title: string
    subtitle: string
    why_not_chat: string
    concepts: string[]
  }
  phase: string
  stage: { scene: SceneKind; props: Record<string, unknown>; focus: string[] }
  move: Record<string, unknown>
  plan: string[]
  step_index: number
  current_step: Record<string, unknown>
  hint_level: number
  attempts: number
  answer_unlocked: boolean
  mastery: Record<string, number>
  mastery_before: Record<string, number>
  mastery_changes: Array<Record<string, unknown>>
  misconceptions: string[]
  evidence: Array<Record<string, unknown>>
  transcript: Array<Record<string, unknown>>
  probe_score: number
  verify_score: number
  step_results: Array<Record<string, unknown>>
  report: Record<string, unknown>
  pending: Record<string, unknown> | null
  brain: string
}

export interface AgentAgentSnapshot {
  status: 'pending' | 'queued' | 'running' | 'completed' | 'failed'
  error?: string
}

export interface PublicQuizQuestion {
  id: string
  type: 'single_choice' | 'multi_choice' | 'short_text'
  prompt: string
  options: Array<{ id: string; label: string }>
  points: number
}

export interface PublicQuiz {
  schema_version: 'quiz-generation-result.v1'
  task_id: string
  title: string
  instructions: string
  questions: PublicQuizQuestion[]
  total_points: number
}

export interface QuizSubmissionSnapshot {
  submission_id: string
  submitted_at: string | null
  total_score: number
  total_points: number
  per_question: Array<{ id: string; correct: boolean; score: number; points: number }>
  handoff_reason: string
}

export interface AgentTaskSnapshot {
  id: string
  status: AgentTaskStatus
  title?: string
  is_pinned?: boolean
  is_unread?: boolean
  deleted_at?: string | null
  resources?: unknown[]
  turnStatus?: AgentTurnStatus
  goalStatus?: AgentGoalStatus
  phase?: string
  executionMode?: string
  currentTurnId?: string
  planRevision?: number
  workItems?: AgentWorkItem[]
  plan?: Record<string, unknown>
  budget?: Record<string, unknown>
  prompt: string
  graph_version: string
  intent: {
    topic?: string
    learning_objective?: string
    learner_level?: string
    course_context?: string
    language?: string
    target_duration_sec?: number
  }
  agents: Record<string, AgentAgentSnapshot>
  artifacts: {
    lesson_intro: ArtifactSnapshot
    lecture_deck: ArtifactSnapshot
    quiz: { available: boolean; data?: PublicQuiz | null }
    visual: ArtifactSnapshot
  }
  delivery: {
    order: string[]
    queue: Array<{
      artifact: string
      task_key: string
      title?: string
      sequence?: number
      state: 'queued' | 'unlocked' | 'consumed'
      closed_at?: string | null
    }>
    cursor: number
  }
  quiz_submission: QuizSubmissionSnapshot | null
  error: string
  created_at: string | null
  updated_at: string | null
  current_execution_id?: string | null
  latest_execution_id?: string | null
  runtime_graph?: {
    id: string
    type: 'runtime-graph'
    taskId: string
    latestExecutionId: string | null
    status: string
    updatedAt: string | null
  }
  executions?: Array<{
    id: string
    status: string
    trigger: string
    graph_version: string
    started_at: string | null
    ended_at: string | null
  }>
}

const TERMINAL_AGENT_TASK_STATUSES = new Set<AgentTaskStatus>([
  'handed_off',
  'completed',
  'partial',
  'failed',
  'timed_out',
  'budget_exceeded',
  'cancelled',
])

export function isAgentTaskTerminal(task: AgentTaskSnapshot | null | undefined): boolean {
  if (!task) return false
  return (
    TERMINAL_AGENT_TASK_STATUSES.has(task.status) ||
    task.turnStatus === 'delivered' ||
    task.turnStatus === 'failed' ||
    task.turnStatus === 'cancelled' ||
    task.goalStatus === 'completed' ||
    task.goalStatus === 'failed' ||
    task.goalStatus === 'cancelled'
  )
}

export function isAgentTaskActive(task: AgentTaskSnapshot | null | undefined): boolean {
  return Boolean(
    task &&
      !isAgentTaskTerminal(task) &&
      task.status !== 'awaiting_user' &&
      task.turnStatus !== 'awaiting_user'
  )
}

export interface ExecutionSnapshotResponse {
  executionId: string
  taskId?: string
  graphVersion?: string
  schemaVersion: 'lingxilearn.execution.v1'
  status?: string
  snapshot: Record<string, unknown>
  timeline: {
    schemaVersion: 'lingxilearn.timeline.v1'
    executionId: string
    spans: Array<Record<string, unknown>>
    totalTokens: number
    waitingForUserMs: number
  }
  executionMetadata: {
    trigger: string | null
    startedAt: string | null
    endedAt?: string | null
    totalDurationMs?: number | null
    cost: unknown | null
    totalTokens?: number | null
    scheduleId?: string | null
    scheduledFor?: string | null
  }
}

export interface ArtifactSnapshot {
  available: boolean
  url: string
  metadata?: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Workspace domain types (issue #40: extracted from api.ts)
// ---------------------------------------------------------------------------

export interface WorkspaceFileItem {
  id: string
  workspaceId?: string
  name: string
  key?: string
  path?: string
  url?: string
  size: number
  type?: string
  mimeType?: string
  width?: number | null
  height?: number | null
  folderId?: string | null
  folderPath?: string | null
  uploadedBy?: string
  uploadedAt?: string | null
  deletedAt?: string | null
  storageContext?: 'workspace' | 'mothership'
  archived?: boolean
  readOnly?: boolean
  metadata?: Record<string, unknown>
  createdAt?: string | null
  updatedAt?: string | null
}

export interface WorkspaceFolderItem {
  id: string
  name: string
  parentId?: string | null
  path?: string
  userId?: string
  sortOrder?: number
  createdAt?: string | null
  updatedAt?: string | null
  deletedAt?: string | null
  archived?: boolean
}

export interface WorkspaceTableItem {
  id: string
  name: string
  description?: string
  schema?: { columns: Array<Record<string, unknown>> }
  columns?: Array<Record<string, unknown>>
  rowCount?: number
  totalRows?: number
  archived?: boolean
  metadata?: Record<string, unknown>
}

export interface WorkspaceTableViewItem {
  id: string
  tableId: string
  name: string
  config: Record<string, unknown>
  isDefault?: boolean
}

// ---------------------------------------------------------------------------
// Knowledge domain types (issue #40: extracted from api.ts)
// ---------------------------------------------------------------------------

export interface KnowledgeBaseItem {
  id: string
  name: string
  description?: string
  documentCount?: number
  archived?: boolean
}

export interface KnowledgeDocumentItem {
  id: string
  knowledgeBaseId: string
  name: string
  mimeType?: string
  content?: string
  archived?: boolean
  readOnly?: boolean
  metadata?: Record<string, unknown>
}
