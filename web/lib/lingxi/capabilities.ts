export const LINGXI_WORKSPACE_ID = 'lingxi' as const

export type LingxiCapabilityStatus = 'integrated' | 'not_integrated'

export interface LingxiCapability {
  status: LingxiCapabilityStatus
  label: string
  backend: string | null
  /**
   * Workspace route segment this capability owns (e.g. `skills` for
   * `/workspace/lingxi/skills`). Only integrated capabilities may carry one:
   * a segment here is what the route allowlist below is built from.
   */
  routeSegment?: string
}

export const LingxiCapabilityManifest = {
  chat: { status: 'integrated', label: 'Agent 对话', backend: '/api/agent-tasks' },
  taskStream: {
    status: 'integrated',
    label: 'Agent 事件流',
    backend: '/api/agent-tasks/{id}/events',
  },
  artifacts: {
    status: 'integrated',
    label: '学习产物',
    backend: '/api/agent-tasks/{id}/artifacts/{kind}',
  },
  quiz: {
    status: 'integrated',
    label: '知识点检测',
    backend: '/api/agent-tasks/{id}/quiz-submissions',
  },
  skills: {
    status: 'integrated',
    label: 'Skills',
    backend: '/api/skills',
    routeSegment: 'skills',
  },
  preferences: { status: 'integrated', label: '偏好设置', backend: '/api/me/preferences' },
  files: {
    status: 'integrated',
    label: '文件',
    backend: '/api/workspaces/{workspaceId}/files',
    routeSegment: 'files',
  },
  tables: { status: 'integrated', label: '表格', backend: '/api/table', routeSegment: 'tables' },
  knowledge: {
    status: 'integrated',
    label: '知识库',
    backend: '/api/knowledge',
    routeSegment: 'knowledge',
  },
  integrations: { status: 'not_integrated', label: '集成', backend: null },
  logs: { status: 'integrated', label: '日志', backend: '/api/logs', routeSegment: 'logs' },
  schedules: { status: 'not_integrated', label: '计划任务', backend: null },
  workflows: { status: 'not_integrated', label: '可编辑工作流', backend: null },
  organizations: { status: 'not_integrated', label: '组织', backend: null },
  billing: { status: 'not_integrated', label: '计费', backend: null },
  desktop: { status: 'not_integrated', label: '桌面端', backend: null },
  cli: { status: 'not_integrated', label: 'CLI', backend: null },
  ingest: { status: 'not_integrated', label: '分析采集', backend: null },
  enterprise: { status: 'not_integrated', label: '企业功能', backend: null },
} as const satisfies Record<string, LingxiCapability>

export type LingxiCapabilityKey = keyof typeof LingxiCapabilityManifest

/**
 * Single gate both navigation visibility and route availability consult
 * (issue #48): a capability surfaces in the product exactly when it is
 * integrated. Unsupported capabilities are expressed by code not existing —
 * never by a permanent 404/placeholder route.
 */
export function isLingxiCapabilityIntegrated(capability: LingxiCapabilityKey): boolean {
  return LingxiCapabilityManifest[capability].status === 'integrated'
}

/**
 * Workspace route allowlist, derived from the manifest so navigation and
 * route availability can never drift: a workspace route segment exists in the
 * product if and only if an integrated capability declares it.
 */
export const LINGXI_WORKSPACE_ROUTE_ALLOWLIST: readonly string[] = Object.values(
  LingxiCapabilityManifest
)
  .filter(
    (capability): capability is LingxiCapability & { routeSegment: string } =>
      capability.status === 'integrated' && typeof capability.routeSegment === 'string'
  )
  .map((capability) => capability.routeSegment)

export function lingxiNotIntegratedError(method: string, path: string): Error {
  return new Error(`未接入：${method} ${path} 不属于当前 LingxiGraph 后端能力`)
}
