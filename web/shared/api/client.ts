import type { components } from '@/shared/api/generated/schema'

type Schemas = components['schemas']

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !(init.body instanceof FormData)) {
    headers.set('content-type', 'application/json')
  }
  const response = await fetch(path, {
    ...init,
    headers,
    credentials: 'include',
    cache: 'no-store',
  })
  if (!response.ok) {
    const problem = (await response.json().catch(() => null)) as {
      detail?: string
      message?: string
    } | null
    throw new ApiError(
      response.status,
      problem?.detail ?? problem?.message ?? `Request failed (${response.status})`,
    )
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export interface Identity {
  id: string
  name?: string | null
  email?: string | null
}

export const identityApi = {
  me: () => apiRequest<Identity>('/api/v1/me'),
}

export const workspaceApi = {
  list: () => apiRequest<Schemas['WorkspaceListResponse']>('/api/workspaces'),
  get: (workspaceId: string) =>
    apiRequest<Schemas['WorkspaceResponse']>(`/api/workspaces/${workspaceId}`),
  update: (workspaceId: string, name: string) =>
    apiRequest<Schemas['WorkspaceResponse']>(`/api/workspaces/${workspaceId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),
}

export const agentTaskApi = {
  list: () => apiRequest<Schemas['AgentTaskListResponse']>('/api/agent-tasks'),
  get: (taskId: string) =>
    apiRequest<Schemas['AgentTaskSnapshotResponse']>(`/api/agent-tasks/${taskId}`),
  create: (prompt: string) =>
    apiRequest<Schemas['AgentTaskCreateResponse']>('/api/agent-tasks', {
      method: 'POST',
      body: JSON.stringify({ prompt, resources: [] } satisfies Schemas['CreateAgentTask']),
    }),
  sendMessage: (taskId: string, message: string) =>
    apiRequest<Record<string, unknown>>(`/api/agent-tasks/${taskId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
  cancel: (taskId: string) =>
    apiRequest<Schemas['AgentTaskCancelResponse']>(`/api/agent-tasks/${taskId}/cancel`, {
      method: 'POST',
    }),
}

export const artifactApi = {
  list: (workspaceId: string) =>
    apiRequest<Schemas['ArtifactListResponse']>(`/api/workspaces/${workspaceId}/artifacts`),
  upload: (workspaceId: string, file: File) => {
    const form = new FormData()
    form.set('file', file)
    return apiRequest<Schemas['ArtifactResponse']>(`/api/workspaces/${workspaceId}/artifacts`, {
      method: 'POST',
      body: form,
    })
  },
  rename: (workspaceId: string, artifactId: string, name: string) =>
    apiRequest<Schemas['ArtifactResponse']>(
      `/api/workspaces/${workspaceId}/artifacts/${artifactId}`,
      { method: 'PATCH', body: JSON.stringify({ name }) },
    ),
  remove: (workspaceId: string, artifactId: string) =>
    apiRequest<void>(`/api/workspaces/${workspaceId}/artifacts/${artifactId}`, {
      method: 'DELETE',
    }),
  contentUrl: (workspaceId: string, artifactId: string) =>
    `/api/workspaces/${workspaceId}/artifacts/${artifactId}/content`,
}

export const skillApi = {
  list: () => apiRequest<Schemas['SkillsResponse']>('/api/skills'),
  create: (payload: { name: string; description: string; content: string }) =>
    apiRequest<Schemas['SkillCreateResponse']>('/api/skills', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  remove: (skillId: string) =>
    apiRequest<Schemas['SuccessResponse']>(`/api/skills/${skillId}`, { method: 'DELETE' }),
}
