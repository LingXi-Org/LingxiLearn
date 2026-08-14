export const LINGXI_WORKSPACE_ID = 'lingxi' as const

export type LingxiCapabilityStatus = 'integrated' | 'not_integrated'

export interface LingxiCapability {
  status: LingxiCapabilityStatus
  label: string
  backend: string | null
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
  skills: { status: 'integrated', label: 'Skills', backend: '/api/skills' },
  preferences: { status: 'integrated', label: '偏好设置', backend: '/api/me/preferences' },
  files: {
    status: 'integrated',
    label: '文件',
    backend: '/api/workspaces/{workspaceId}/files',
  },
  tables: { status: 'integrated', label: '表格', backend: '/api/table' },
  knowledge: { status: 'integrated', label: '知识库', backend: '/api/knowledge' },
  integrations: { status: 'not_integrated', label: '集成', backend: null },
  logs: { status: 'integrated', label: '日志', backend: '/api/logs' },
  schedules: { status: 'not_integrated', label: '计划任务', backend: null },
  workflows: { status: 'not_integrated', label: '可编辑工作流', backend: null },
  organizations: { status: 'not_integrated', label: '组织', backend: null },
  billing: { status: 'not_integrated', label: '计费', backend: null },
  enterprise: { status: 'not_integrated', label: '企业功能', backend: null },
} as const satisfies Record<string, LingxiCapability>

export function lingxiNotIntegratedError(method: string, path: string): Error {
  return new Error(`未接入：${method} ${path} 不属于当前 LingxiGraph 后端能力`)
}
