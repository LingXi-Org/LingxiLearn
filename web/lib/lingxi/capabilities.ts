export const LINGXI_WORKSPACE_ID = 'lingxi' as const

export type LingxiCapabilityStatus = 'integrated' | 'not_integrated'

export interface LingxiCapability {
  status: LingxiCapabilityStatus
  label: string
  backend: string | null
  /**
   * Workspace route segment this capability owns (e.g. `skills` for
   * `/workspace/lingxi/skills`). Only integrated capabilities may carry one:
   * a segment here is what the route allowlist below is built from (issue #48).
   */
  routeSegment?: string
  /**
   * Where durable state lives for integrated capabilities (issue #54). `null`
   * means the capability has no persistence owner and must not surface product
   * UI.
   */
  persistenceOwner?: string | null
}

/**
 * Capability matrix for the LingxiLearn product closure (issue #54).
 *
 * Only capabilities with a real backend owner may surface in navigation,
 * settings, or the API client. Everything listed as `not_integrated` below was
 * audited and removed from the reachable product surface rather than kept as a
 * placeholder:
 *
 * capability      | UI entry          | frontend client     | backend endpoint        | persistence owner | status
 * --------------- | ----------------- | ------------------- | ----------------------- | ----------------- | --------------
 * chat            | workspace home    | api.createAgentTask | /api/agent-tasks        | AgentTask         | integrated
 * taskStream      | workspace home    | subscribeAgent*     | /api/agent-tasks/events | AgentTaskEvent    | integrated
 * artifacts       | task detail       | api.agentArtifactUrl| /api/agent-tasks/artifacts | AgentTaskArtifact | integrated
 * quiz            | task detail       | api.submitAgentQuiz | /api/agent-tasks/quiz-submissions | QuizSubmission | integrated
 * skills          | sidebar + pages   | api.skills CRUD     | /api/skills             | skills/ catalog   | integrated
 * preferences     | settings general  | api.updatePreferences | /api/me/preferences   | LearnerPreference | integrated
 * userSettings    | settings general  | api.updateUserSettings | /api/users/me/settings | LearnerPreference | integrated
 * files           | sidebar + pages   | api.workspaceFiles  | /api/workspaces/lingxi/files | WorkspaceFile | integrated
 * tables          | sidebar + pages   | api.workspaceTables | /api/table              | WorkspaceTable    | integrated
 * knowledge       | sidebar + pages   | api.workspaceKnowledge | /api/knowledge       | KnowledgeBase     | integrated
 * logs            | sidebar + pages   | api.logs            | /api/logs               | AgentTaskEvent    | integrated
 * usageAudit      | logs (CSV export) | —                   | /api/users/me/usage-logs | AgentTask        | integrated
 * billing         | removed           | removed             | stubs only              | none              | not_integrated
 * organizations   | removed           | removed             | stubs only              | none              | not_integrated
 * invitations     | removed           | removed             | none                    | none              | not_integrated
 * integrations    | removed (#48)     | removed             | none                    | none              | not_integrated
 * oauth           | auth callbacks    | auth plumbing       | none                    | none              | not_integrated
 * credentials     | removed (#54)     | removed             | none                    | none              | not_integrated
 * secrets         | removed           | removed             | none                    | none              | not_integrated
 * auditLogs       | removed           | removed             | none                    | none              | not_integrated
 * admin           | removed (#54)     | removed             | none                    | none              | not_integrated
 * schedules       | removed           | removed             | none                    | none              | not_integrated
 * workflows       | removed           | removed             | none                    | none              | not_integrated
 * desktop         | removed (#48)     | removed             | none                    | none              | not_integrated
 * cli             | removed (#48)     | removed             | none                    | none              | not_integrated
 * ingest          | removed (#48)     | removed             | none                    | none              | not_integrated
 * enterprise      | removed (#54)     | removed             | none                    | none              | not_integrated
 *
 * The #54 audit also removed the Sim account-settings closures that had no
 * Lingxi backend owner: /account/settings/api-keys (credentials),
 * /account/settings/admin (Better Auth admin stubs), and
 * /account/settings/mothership (enterprise license/BYOK proxy endpoints that
 * no LingxiLearn deployment serves). Unsupported capabilities are expressed
 * by code not existing — never by a reachable route backed by a fake client.
 */
export const LingxiCapabilityManifest = {
  chat: {
    status: 'integrated',
    label: 'Agent 对话',
    backend: '/api/agent-tasks',
    persistenceOwner: 'AgentTask',
  },
  taskStream: {
    status: 'integrated',
    label: 'Agent 事件流',
    backend: '/api/agent-tasks/{id}/events',
    persistenceOwner: 'AgentTaskEvent',
  },
  artifacts: {
    status: 'integrated',
    label: '学习产物',
    backend: '/api/agent-tasks/{id}/artifacts/{kind}',
    persistenceOwner: 'AgentTaskArtifact',
  },
  quiz: {
    status: 'integrated',
    label: '知识点检测',
    backend: '/api/agent-tasks/{id}/quiz-submissions',
    persistenceOwner: 'QuizSubmission',
  },
  skills: {
    status: 'integrated',
    label: 'Skills',
    backend: '/api/skills',
    routeSegment: 'skills',
    persistenceOwner: 'skills/ catalog',
  },
  preferences: {
    status: 'integrated',
    label: '偏好设置',
    backend: '/api/me/preferences',
    persistenceOwner: 'LearnerPreference',
  },
  userSettings: {
    status: 'integrated',
    label: '用户设置',
    backend: '/api/users/me/settings',
    persistenceOwner: 'LearnerPreference',
  },
  files: {
    status: 'integrated',
    label: '文件',
    backend: '/api/workspaces/{workspaceId}/files',
    routeSegment: 'files',
    persistenceOwner: 'WorkspaceFile',
  },
  tables: {
    status: 'integrated',
    label: '表格',
    backend: '/api/table',
    routeSegment: 'tables',
    persistenceOwner: 'WorkspaceTable',
  },
  knowledge: {
    status: 'integrated',
    label: '知识库',
    backend: '/api/knowledge',
    routeSegment: 'knowledge',
    persistenceOwner: 'KnowledgeBase',
  },
  integrations: { status: 'not_integrated', label: '集成', backend: null, persistenceOwner: null },
  logs: {
    status: 'integrated',
    label: '日志',
    backend: '/api/logs',
    routeSegment: 'logs',
    persistenceOwner: 'AgentTaskEvent',
  },
  usageAudit: {
    status: 'integrated',
    label: '用量审计',
    backend: '/api/users/me/usage-logs',
    persistenceOwner: 'AgentTask',
  },
  schedules: { status: 'not_integrated', label: '计划任务', backend: null, persistenceOwner: null },
  workflows: {
    status: 'not_integrated',
    label: '可编辑工作流',
    backend: null,
    persistenceOwner: null,
  },
  organizations: { status: 'not_integrated', label: '组织', backend: null, persistenceOwner: null },
  invitations: { status: 'not_integrated', label: '邀请', backend: null, persistenceOwner: null },
  oauth: { status: 'not_integrated', label: 'OAuth 连接', backend: null, persistenceOwner: null },
  credentials: { status: 'not_integrated', label: '凭据', backend: null, persistenceOwner: null },
  secrets: { status: 'not_integrated', label: '密钥', backend: null, persistenceOwner: null },
  auditLogs: { status: 'not_integrated', label: '审计日志', backend: null, persistenceOwner: null },
  admin: { status: 'not_integrated', label: '管理员控制台', backend: null, persistenceOwner: null },
  billing: { status: 'not_integrated', label: '计费', backend: null, persistenceOwner: null },
  desktop: { status: 'not_integrated', label: '桌面端', backend: null, persistenceOwner: null },
  cli: { status: 'not_integrated', label: 'CLI', backend: null, persistenceOwner: null },
  ingest: { status: 'not_integrated', label: '分析采集', backend: null, persistenceOwner: null },
  enterprise: {
    status: 'not_integrated',
    label: '企业功能',
    backend: null,
    persistenceOwner: null,
  },
} as const satisfies Record<string, LingxiCapability>

export type LingxiCapabilityKey = keyof typeof LingxiCapabilityManifest

/**
 * Single gate both navigation visibility and route availability consult
 * (issues #48, #54): a capability surfaces in the product exactly when it is
 * integrated — i.e. its backend and persistence owners exist. Unsupported
 * capabilities are expressed by code not existing — never by a permanent
 * 404/placeholder route.
 */
export function isLingxiCapabilityIntegrated(capability: LingxiCapabilityKey): boolean {
  return LingxiCapabilityManifest[capability].status === 'integrated'
}

/**
 * Workspace route allowlist, derived from the manifest so navigation and
 * route availability can never drift: a workspace route segment exists in the
 * product if and only if an integrated capability declares it.
 */
export const LINGXI_WORKSPACE_ROUTE_ALLOWLIST: readonly string[] = (
  Object.values(LingxiCapabilityManifest) as LingxiCapability[]
).flatMap((capability) =>
  capability.status === 'integrated' && typeof capability.routeSegment === 'string'
    ? [capability.routeSegment]
    : []
)

export function lingxiNotIntegratedError(method: string, path: string): Error {
  return new Error(`未接入：${method} ${path} 不属于当前 LingxiGraph 后端能力`)
}
