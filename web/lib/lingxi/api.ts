import type {
  AgentTaskEvent,
  AgentTaskListItem,
  AgentTaskSnapshot,
  NativeSkill,
  Pack,
  QuizSubmissionSnapshot,
  RunEvent,
  SessionListItem,
  SessionSnapshot,
  SimExecutionSnapshot,
} from './types'
import { AGENT_EVENT_KINDS } from './agent-events'

/**
 * When the app is served by FastAPI (the single-process deployment) the API is
 * same-origin and this is empty. Point NEXT_PUBLIC_API_BASE at the backend when
 * running `next dev` against a separately hosted server.
 */
// Local development uses Next's same-origin rewrite to FastAPI. A non-empty
// value is still supported for an explicitly separate API origin.
const configuredApiBase = process.env.NEXT_PUBLIC_API_BASE?.trim()
export const API_BASE = configuredApiBase || ''

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string
  ) {
    super(detail || `HTTP ${status}`)
  }
}

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
}

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
  schema?: { columns: Array<Record<string, any>> }
  columns?: Array<Record<string, any>>
  rowCount?: number
  totalRows?: number
  archived?: boolean
}

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

let authenticationFailureHandler: (() => void) | null = null
let sessionRefreshHandler: (() => void | Promise<void>) | null = null
export type AccessTokenProvider = () =>
  | string
  | null
  | undefined
  | Promise<string | null | undefined>
let accessTokenProvider: AccessTokenProvider | null = null

export function setAccessTokenProvider(provider: AccessTokenProvider | null): () => void {
  const previous = accessTokenProvider
  accessTokenProvider = provider
  return () => {
    accessTokenProvider = previous
  }
}

export function setAccessTokenRefreshHandler(
  handler: (() => void | Promise<void>) | null
): () => void {
  return setSessionRefreshHandler(handler)
}

export function setAuthenticationFailureHandler(handler: (() => void) | null): () => void {
  const previous = authenticationFailureHandler
  authenticationFailureHandler = handler
  return () => {
    authenticationFailureHandler = previous
  }
}

export function setSessionRefreshHandler(handler: (() => void | Promise<void>) | null): () => void {
  const previous = sessionRefreshHandler
  sessionRefreshHandler = handler
  return () => {
    sessionRefreshHandler = previous
  }
}

function apiUrl(path: string): string {
  return `${API_BASE}/api${path}`
}

function normalizeWorkspaceFile(file: WorkspaceFileItem): WorkspaceFileItem {
  if (!file.url || !file.url.startsWith('/api/')) return file
  return { ...file, url: `${API_BASE}${file.url}` }
}

async function authorizedFetch(url: string, init?: RequestInit): Promise<Response> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const headers = new Headers(init?.headers)
    if (accessTokenProvider && !headers.has('Authorization')) {
      const token = await accessTokenProvider()
      if (token) headers.set('Authorization', `Bearer ${token}`)
    }
    let response: Response
    try {
      response = await fetch(url, { ...init, headers, credentials: 'include' })
    } catch (error) {
      throw error
    }
    if (response.status !== 401 || attempt > 0 || !sessionRefreshHandler) return response
    try {
      await sessionRefreshHandler()
    } catch {
      authenticationFailureHandler?.()
      return response
    }
  }
  throw new Error('unreachable')
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  const response = await authorizedFetch(apiUrl(path), { ...init, headers })
  if (!response.ok) {
    if (response.status === 401) authenticationFailureHandler?.()
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep the status text */
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export const api = {
  health: () =>
    request<{
      status: string
      brain: string
      agent: { configured: boolean; model: string }
      packs: string[]
      tools: number
    }>('/health'),

  packs: () => request<{ packs: Pack[] }>('/packs'),

  skills: () => request<{ skills: NativeSkill[] }>('/skills'),

  workspace: () =>
    request<{ workspace: Record<string, any>; data: Record<string, any> }>('/workspaces/lingxi'),

  updateWorkspace: (patch: { name?: string; appearance?: Record<string, any> }) =>
    request<{ workspace: Record<string, any>; data: Record<string, any> }>('/workspaces/lingxi', {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),

  workspaceFolders: (scope: 'active' | 'archived' = 'active') =>
    request<{ folders: WorkspaceFolderItem[] }>(`/workspaces/lingxi/files/folders?scope=${scope}`),

  createWorkspaceFolder: (name: string, parentId?: string | null) =>
    request<{ folder: WorkspaceFolderItem }>('/workspaces/lingxi/files/folders', {
      method: 'POST',
      body: JSON.stringify({ name, parentId: parentId ?? null }),
    }),

  updateWorkspaceFolder: (folderId: string, body: { name?: string; parentId?: string | null }) =>
    request<{ folder: WorkspaceFolderItem }>(
      `/workspaces/lingxi/files/folders/${encodeURIComponent(folderId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify(body),
      }
    ),

  archiveWorkspaceFolder: (folderId: string) =>
    request<{ success: boolean }>(
      `/workspaces/lingxi/files/folders/${encodeURIComponent(folderId)}`,
      { method: 'DELETE' }
    ),

  restoreWorkspaceFolder: (folderId: string) =>
    request<{ folder: WorkspaceFolderItem }>(
      `/workspaces/lingxi/files/folders/${encodeURIComponent(folderId)}/restore`,
      { method: 'POST' }
    ),

  moveWorkspaceItems: (fileIds: string[], folderIds: string[], targetFolderId?: string | null) =>
    request<{ movedItems: { files: number; folders: number } }>('/workspaces/lingxi/files/move', {
      method: 'POST',
      body: JSON.stringify({ fileIds, folderIds, targetFolderId: targetFolderId ?? null }),
    }),

  workspaceFiles: async (scope: 'active' | 'archived' = 'active', folderId?: string | null) => {
    const result = await request<{ files: WorkspaceFileItem[] }>(
      `/workspaces/lingxi/files?scope=${scope}${folderId ? `&folderId=${encodeURIComponent(folderId)}` : ''}`
    )
    return { ...result, files: result.files.map(normalizeWorkspaceFile) }
  },

  createWorkspaceFile: async (
    name: string,
    content: string,
    type?: string,
    encoding?: 'utf-8' | 'base64',
    folderId?: string | null
  ) => {
    const result = await request<{ file: WorkspaceFileItem }>('/workspaces/lingxi/files', {
      method: 'POST',
      body: JSON.stringify({
        name,
        content,
        type: type || 'text/plain',
        contentType: type || 'text/plain',
        encoding: encoding || 'utf-8',
        folderId: folderId ?? null,
      }),
    })
    return { ...result, file: normalizeWorkspaceFile(result.file) }
  },

  workspaceFile: async (fileId: string) => {
    const result = await request<{ file: WorkspaceFileItem }>(
      `/workspaces/lingxi/files/${encodeURIComponent(fileId)}`
    )
    return { ...result, file: normalizeWorkspaceFile(result.file) }
  },

  workspaceFileContent: async (fileId: string) => {
    const result = await request<{ content: string; encoding: string; file: WorkspaceFileItem }>(
      `/workspaces/lingxi/files/${encodeURIComponent(fileId)}/content`
    )
    return { ...result, file: normalizeWorkspaceFile(result.file) }
  },

  updateWorkspaceFileContent: (fileId: string, content: string) =>
    request<{ file: WorkspaceFileItem }>(
      `/workspaces/lingxi/files/${encodeURIComponent(fileId)}/content`,
      { method: 'PUT', body: JSON.stringify({ content }) }
    ),

  archiveWorkspaceFile: (fileId: string) =>
    request<{ success: boolean }>(`/workspaces/lingxi/files/${encodeURIComponent(fileId)}`, {
      method: 'DELETE',
    }),

  workspaceTables: () =>
    request<{ tables: WorkspaceTableItem[]; data: any }>('/table?workspaceId=lingxi'),

  createWorkspaceTable: (name: string, columns = [{ name: '内容', type: 'string' }]) =>
    request<{ data: { table: WorkspaceTableItem } }>('/table', {
      method: 'POST',
      body: JSON.stringify({ workspaceId: 'lingxi', name, schema: { columns } }),
    }),

  workspaceTable: (tableId: string) =>
    request<{ data: { table: WorkspaceTableItem } }>(
      `/table/${encodeURIComponent(tableId)}?workspaceId=lingxi`
    ),

  workspaceTableRows: (tableId: string) =>
    request<{ data: { rows: Array<Record<string, any>>; totalCount: number } }>(
      `/table/${encodeURIComponent(tableId)}/rows`
    ),

  createWorkspaceRows: (tableId: string, rows: Array<Record<string, any>>) =>
    request<{ data: { rows: Array<Record<string, any>> } }>(
      `/table/${encodeURIComponent(tableId)}/rows`,
      {
        method: 'POST',
        body: JSON.stringify({ rows }),
      }
    ),

  updateWorkspaceRow: (tableId: string, rowId: string, data: Record<string, any>) =>
    request<{ data: { row: Record<string, any> } }>(
      `/table/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}`,
      { method: 'PATCH', body: JSON.stringify({ data }) }
    ),

  workspaceKnowledge: async () => {
    const result = await request<{
      knowledgeBases?: KnowledgeBaseItem[]
      data?: KnowledgeBaseItem[]
    }>('/knowledge')
    const knowledgeBases = result.knowledgeBases ?? result.data ?? []
    return { knowledgeBases, data: knowledgeBases }
  },

  createKnowledgeBase: (name: string, description = '') =>
    request<{ data: KnowledgeBaseItem; knowledgeBase: KnowledgeBaseItem }>('/knowledge', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    }),

  knowledgeDocuments: async (baseId: string) => {
    const result = await request<{
      documents?: KnowledgeDocumentItem[]
      data?: KnowledgeDocumentItem[] | { documents?: KnowledgeDocumentItem[] }
    }>(`/knowledge/${encodeURIComponent(baseId)}/documents`)
    const documents =
      result.documents ?? (Array.isArray(result.data) ? result.data : result.data?.documents) ?? []
    return { documents, data: documents }
  },

  createKnowledgeDocument: (
    baseId: string,
    name: string,
    content: string,
    mimeType = 'text/plain'
  ) =>
    request<{ data: KnowledgeDocumentItem; document: KnowledgeDocumentItem }>(
      `/knowledge/${encodeURIComponent(baseId)}/documents`,
      { method: 'POST', body: JSON.stringify({ name, content, mimeType }) }
    ),

  updateKnowledgeDocument: (baseId: string, documentId: string, content: string) =>
    request<{ data: KnowledgeDocumentItem; document: KnowledgeDocumentItem }>(
      `/knowledge/${encodeURIComponent(baseId)}/documents/${encodeURIComponent(documentId)}`,
      { method: 'PATCH', body: JSON.stringify({ content }) }
    ),

  logs: () => request<{ data: Array<Record<string, any>> }>('/logs?workspaceId=lingxi'),

  recordLearningEvent: (taskId: string, event: AgentTaskEvent) =>
    request<{ success: boolean; data: Record<string, unknown> }>('/lingxi/learning-records', {
      method: 'POST',
      body: JSON.stringify({ taskId, event }),
    }),

  billing: () =>
    request<{ success: boolean; context: string; data: Record<string, any> }>(
      '/billing?context=user&includeOrg=false'
    ),

  billingInvoices: (context: 'user' | 'organization' = 'user') =>
    request<{
      success: boolean
      invoices: Array<Record<string, any>>
      hasMore: boolean
    }>(`/billing/invoices?context=${context}`),

  billingPortal: (returnUrl = '/workspace/lingxi/settings/billing') =>
    request<{ url: string }>('/billing/portal', {
      method: 'POST',
      body: JSON.stringify({ context: 'user', returnUrl }),
    }),

  purchaseCredits: (amount: number) =>
    request<{ success: boolean; message?: string }>('/billing/credits', {
      method: 'POST',
      body: JSON.stringify({ amount, requestId: crypto.randomUUID() }),
    }),

  switchBillingPlan: (targetPlanName: string, interval: 'month' | 'year' = 'month') =>
    request<{ success: boolean; plan?: string; interval?: string; message?: string }>(
      '/billing/switch-plan',
      { method: 'POST', body: JSON.stringify({ targetPlanName, interval }) }
    ),

  billingUsageLimits: () =>
    request<{
      success: boolean
      rateLimit: Record<string, any>
      usage: Record<string, any>
      storage: Record<string, any>
    }>('/users/me/usage-limits'),

  v2BillingStatus: (workspaceId = 'lingxi') =>
    request<{ data: Record<string, any> }>(
      `/v2/billing/status?workspaceId=${encodeURIComponent(workspaceId)}`
    ),

  v2BillingLogs: (
    params: {
      period?: '1d' | '7d' | '30d' | 'all' | 'custom'
      startDate?: string
      endDate?: string
      source?: string
      cursor?: string
      limit?: number
    } = {}
  ) => {
    const query = new URLSearchParams()
    for (const [key, value] of Object.entries({ workspaceId: 'lingxi', ...params })) {
      if (value !== undefined && value !== '') query.set(key, String(value))
    }
    return request<{ data: Array<Record<string, any>>; nextCursor: string | null }>(
      `/v2/billing/logs?${query.toString()}`
    )
  },

  usageLogs: (period = '30d') =>
    request<{
      success: boolean
      logs: Array<Record<string, any>>
      summary: { totalCredits: number; bySourceCredits: Record<string, number> }
      pagination: { nextCursor?: string | null; hasMore: boolean }
    }>(`/users/me/usage-logs?period=${encodeURIComponent(period)}`),

  userProfile: () => request<{ user: Record<string, any> }>('/users/me/profile'),

  userSettings: () => request<{ data: Record<string, any> }>('/users/me/settings'),

  updateUserSettings: (patch: Record<string, unknown>) =>
    request<{ success: boolean; data?: Record<string, any> }>('/users/me/settings', {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),

  createSkill: (body: { name: string; description?: string; content?: string; version?: string }) =>
    request<{ skill: NativeSkill }>('/skills', { method: 'POST', body: JSON.stringify(body) }),

  updateSkill: (skillId: string, body: Record<string, string>) =>
    request<{ skill: NativeSkill }>(`/skills/${encodeURIComponent(skillId)}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteSkill: (skillId: string) =>
    request<{ success: boolean }>(`/skills/${encodeURIComponent(skillId)}`, { method: 'DELETE' }),

  createSession: (missionId: string, packId = '') =>
    request<{ id: string; mission_id: string; pack_id: string; status: string }>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ mission_id: missionId, pack_id: packId }),
    }),

  session: (id: string) => request<SessionSnapshot>(`/sessions/${id}`),

  answer: (id: string, answer: unknown) =>
    request<{ status: string }>(`/sessions/${id}/answer`, {
      method: 'POST',
      body: JSON.stringify({ answer }),
    }),

  report: (id: string) => request<Record<string, any>>(`/sessions/${id}/report`),

  createAgentTask: (
    prompt: string,
    attachments: LingxiAttachmentRef[] = [],
    context: LingxiTaskContextOptions = {}
  ) =>
    request<{ id: string; status: string }>('/agent-tasks', {
      method: 'POST',
      body: JSON.stringify({
        prompt,
        attachments,
        resource_refs: context.resourceRefs ?? [],
        skill_ids: context.skillIds ?? [],
      }),
    }),

  agentTask: (id: string) => request<AgentTaskSnapshot>(`/agent-tasks/${id}`),
  agentTaskEvents: (id: string) =>
    request<{ events: AgentTaskEvent[] }>(`/agent-tasks/${id}/events?format=json`),
  runtimeGraph: (taskId: string) =>
    request<{
      id: string
      type: 'runtime-graph'
      taskId: string
      latestExecutionId: string | null
      status: string
      updatedAt: string | null
      workflowState: Record<string, unknown>
    }>(`/agent-tasks/${taskId}/runtime-graph`),
  agentTaskDecisions: (taskId: string) =>
    request<{ decisions: Array<Record<string, unknown>> }>(
      `/agent-tasks/${taskId}/decisions`
    ),

  executionSnapshot: (executionId: string) =>
    request<SimExecutionSnapshot>(`/logs/execution/${encodeURIComponent(executionId)}`),

  logByExecution: (executionId: string) =>
    request<Record<string, unknown>>(`/logs/by-execution/${encodeURIComponent(executionId)}`),

  copilotToolPermission: (
    decisions: Array<{
      toolCallId: string
      decision: 'allow' | 'allow_chat' | 'always_allow' | 'skip'
    }>
  ) =>
    request<{ success: boolean; results: Array<Record<string, unknown>> }>(
      '/copilot/tool-permission',
      {
        method: 'POST',
        body: JSON.stringify({ decisions }),
      }
    ),


  agentMessage: (
    taskId: string,
    message: string,
    attachments: LingxiAttachmentRef[] = [],
    context: LingxiTaskContextOptions = {}
  ) =>
    request<{ status: string }>(`/agent-tasks/${taskId}/messages`, {
      method: 'POST',
      body: JSON.stringify({
        message,
        attachments,
        resource_refs: context.resourceRefs ?? [],
        skill_ids: context.skillIds ?? [],
      }),
    }),

  agentTasks: (scope: 'active' | 'archived' = 'active') =>
    request<{ tasks: AgentTaskListItem[] }>(`/agent-tasks?scope=${scope}`),

  updateAgentTask: (
    taskId: string,
    patch: {
      title?: string
      is_pinned?: boolean
      is_unread?: boolean
      resources?: Array<Record<string, unknown>>
    }
  ) =>
    request<{
      id: string
      title: string
      is_pinned: boolean
      is_unread: boolean
      resources: Array<Record<string, unknown>>
    }>(`/agent-tasks/${taskId}`, { method: 'PATCH', body: JSON.stringify(patch) }),

  deleteAgentTask: (taskId: string) =>
    request<{ id: string; deleted_at: string | null }>(`/agent-tasks/${taskId}`, {
      method: 'DELETE',
    }),

  restoreAgentTask: (taskId: string) =>
    request<{ id: string; deleted_at: null }>(`/agent-tasks/${taskId}/restore`, { method: 'POST' }),

  forkAgentTask: (taskId: string) =>
    request<{ id: string; status: string }>(`/agent-tasks/${taskId}/fork`, { method: 'POST' }),

  cancelAgentTask: (taskId: string) =>
    request<{ id: string; status: string }>(`/agent-tasks/${taskId}/cancel`, { method: 'POST' }),

  uploadAttachment: async (file: File) => {
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
  },

  submitAgentQuiz: (taskId: string, submissionId: string, answers: Record<string, unknown>) =>
    request<{ status: string; submission: QuizSubmissionSnapshot }>(
      `/agent-tasks/${taskId}/quiz-submissions`,
      {
        method: 'POST',
        body: JSON.stringify({ submission_id: submissionId, answers }),
      }
    ),
  ackAgentDelivery: (taskId: string, artifact: string) =>
    request<{ artifact: string; cursor: number; delivery: AgentTaskSnapshot['delivery']['queue'] }>(
      `/agent-tasks/${taskId}/delivery/${artifact}/ack`, { method: 'POST' }
    ),

  agentArtifactUrl: (taskId: string, kind: 'lesson-intro' | 'lecture-deck' | 'visual') =>
    `${API_BASE}/api/agent-tasks/${taskId}/artifacts/${kind}`,

  context: () =>
    request<{
      profile: Record<string, unknown>
      mastery: Record<string, number>
      misconceptions: Record<string, unknown>[]
      preferences: Record<string, unknown>
    }>('/me/context'),

  mastery: () =>
    request<{ mastery: Record<string, number>; sessions: SessionListItem[] }>('/me/mastery'),

  preferences: () => request<{ preferences: Record<string, unknown> }>('/me/preferences'),

  updatePreferences: (patch: Record<string, unknown>) =>
    request<{ preferences: Record<string, unknown> }>('/me/preferences', {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),

  artifactUrl: (sessionId: string, artifactId: string) =>
    `${API_BASE}/api/sessions/${sessionId}/artifact/${artifactId}`,

  fetchArtifact: async (url: string): Promise<Blob> => {
    // Artifact URL builders already include the `/api` prefix. Passing an
    // origin-relative URL through apiUrl() again produced `/api/api/...` in
    // the same-origin Compose deployment.
    const response = await authorizedFetch(url)
    if (!response.ok) {
      throw new ApiError(response.status, response.statusText)
    }
    return response.blob()
  },
}

/**
 * Subscribe to a session's event stream.
 *
 * The server replays from a durable log, so reconnecting with the last sequence
 * we saw resumes exactly where we left off — no gap, no duplicates. That is why
 * this tracks `lastSequence` rather than trusting the socket to stay up.
 */
type SseOptions = { from?: number; onEnd?: (status: string) => void }

/**
 * Fetch-based SSE keeps the existing durable-log replay contract while sending
 * the same HttpOnly session cookie as normal API calls.
 */
function subscribeSse<T extends { sequence?: number }>(
  path: string,
  onEvent: (event: T) => void,
  options: SseOptions = {}
): () => void {
  let closed = false
  let finished = false
  let controller: AbortController | null = null
  let retry: ReturnType<typeof setTimeout> | null = null
  let lastSequence = options.from ?? 0

  const scheduleReconnect = () => {
    if (!closed && !finished && !retry) {
      retry = setTimeout(() => {
        retry = null
        void connect()
      }, 1200)
    }
  }

  const dispatch = (eventName: string, data: string) => {
    if (!data) return
    if (eventName === 'stream.end') {
      try {
        const payload = JSON.parse(data) as { status?: string }
        options.onEnd?.(payload.status ?? 'unknown')
      } catch {
        options.onEnd?.('unknown')
      }
      finished = true
      return
    }
    try {
      const event = JSON.parse(data) as T
      if (typeof event.sequence === 'number') lastSequence = event.sequence
      onEvent(event)
    } catch {
      /* Ignore malformed frames rather than losing the stream. */
    }
  }

  const connect = async () => {
    if (closed || finished) return
    controller = new AbortController()
    try {
      const separator = path.includes('?') ? '&' : '?'
      const response = await authorizedFetch(
        apiUrl(`${path}${separator}last_event_id=${lastSequence}`),
        {
          signal: controller.signal,
          headers: {
            Accept: 'text/event-stream',
            'Last-Event-ID': String(lastSequence),
          },
        }
      )
      if (!response.ok || !response.body) {
        if (response.status === 401 || response.status === 403 || response.status === 404) {
          finished = true
          return
        }
        scheduleReconnect()
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let eventName = 'message'
      let dataLines: string[] = []

      const consumeLine = (line: string) => {
        if (line === '') {
          dispatch(eventName, dataLines.join('\n'))
          eventName = 'message'
          dataLines = []
          return
        }
        if (line.startsWith(':')) return
        if (line.startsWith('event:')) eventName = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
      }

      while (!closed && !finished) {
        const chunk = await reader.read()
        if (chunk.done) {
          buffer += decoder.decode()
          if (buffer) consumeLine(buffer)
          break
        }
        buffer += decoder.decode(chunk.value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) consumeLine(line.replace(/\r$/, ''))
      }
      reader.releaseLock()
      if (!closed && !finished) scheduleReconnect()
    } catch (cause) {
      if (!closed && !(cause instanceof DOMException && cause.name === 'AbortError')) {
        scheduleReconnect()
      }
    } finally {
      controller = null
    }
  }

  void connect()
  return () => {
    closed = true
    if (retry) clearTimeout(retry)
    retry = null
    controller?.abort()
  }
}

export function subscribeEvents(
  sessionId: string,
  onEvent: (event: RunEvent) => void,
  options: SseOptions = {}
): () => void {
  return subscribeSse(`/sessions/${sessionId}/events`, onEvent, options)
}

export function subscribeAgentEvents(
  taskId: string,
  onEvent: (event: AgentTaskEvent) => void,
  options: SseOptions = {}
): () => void {
  return subscribeSse(`/agent-tasks/${taskId}/events`, onEvent, options)
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
