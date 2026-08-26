'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createAgentTask,
  deleteAgentTask,
  forkAgentTask,
  getAgentTask,
  getAgentTasks,
  restoreAgentTask,
  updateAgentTask,
} from '@/lib/api/domains/agent-tasks'
import { suspendBrowserScope } from '@/lib/browser-agent/transport'
import { type MothershipResource, MothershipResourceType } from '@/lib/copilot/resources/types'
import { LINGXI_WORKSPACE_ID } from '@/lib/lingxi/capabilities'
import type { AgentTaskListItem, AgentTaskSnapshot } from '@/lib/lingxi/types'
import { suspendTerminalScope } from '@/lib/terminal/transport'

/**
 * The shared chat query namespace is kept as a compatibility seam for the
 * reused workspace chrome. Its implementation is deliberately Lingxi-only:
 * there is no fallback to /api/mothership, database contracts, or a second
 * persisted chat store in the browser bundle.
 */
export type MothershipChatScope = 'active' | 'archived'

export interface MothershipChatMetadata {
  id: string
  name: string
  updatedAt: Date
  isActive: boolean
  isUnread: boolean
  isPinned: boolean
  deletedAt: Date | null
}

export interface MothershipChatHistory {
  id: string
  title: string | null
  /** The shared chat surface keeps a persisted wire shape; Lingxi adapts it at
   * render time and may resume with either representation. */
  messages: any[]
  activeStreamId: string | null
  resources: any[]
  streamSnapshot?: any
}

export const mothershipChatKeys = {
  all: ['lingxi-agent-tasks'] as const,
  lists: () => [...mothershipChatKeys.all, 'list'] as const,
  workspaceLists: (workspaceId: string | undefined) =>
    [...mothershipChatKeys.lists(), workspaceId ?? ''] as const,
  list: (workspaceId: string | undefined, scope: MothershipChatScope = 'active') =>
    [...mothershipChatKeys.workspaceLists(workspaceId), scope] as const,
  details: () => [...mothershipChatKeys.all, 'detail'] as const,
  detail: (chatId: string | undefined) => [...mothershipChatKeys.details(), chatId ?? ''] as const,
}

export const MOTHERSHIP_CHAT_LIST_STALE_TIME = 60 * 1000
export const MOTHERSHIP_CHAT_HISTORY_STALE_TIME = 30 * 1000

function taskName(task: Pick<AgentTaskListItem, 'prompt' | 'title' | 'intent'>): string {
  return task.title || task.intent.topic || task.prompt || '新学习任务'
}

function mapTask(task: AgentTaskListItem): MothershipChatMetadata {
  const updatedAt = new Date(task.updated_at || task.created_at || 0)
  return {
    id: task.id,
    name: taskName(task),
    updatedAt,
    isActive: task.status === 'queued' || task.status === 'running',
    isUnread: Boolean(task.is_unread),
    isPinned: Boolean(task.is_pinned),
    deletedAt: task.deleted_at ? new Date(task.deleted_at) : null,
  }
}

const mothershipResourceTypes = new Set<string>(Object.values(MothershipResourceType))

function isMothershipResource(value: unknown): value is MothershipResource {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Partial<MothershipResource>
  return (
    typeof candidate.type === 'string' &&
    mothershipResourceTypes.has(candidate.type) &&
    typeof candidate.id === 'string' &&
    typeof candidate.title === 'string' &&
    (candidate.path === undefined || typeof candidate.path === 'string')
  )
}

function taskResources(task: Pick<AgentTaskSnapshot, 'resources'>): MothershipResource[] {
  return (task.resources ?? []).filter(isMothershipResource)
}

/** Retained for reused workspace modules; it only maps the Lingxi list shape. */
export function mapChat(task: AgentTaskListItem): MothershipChatMetadata {
  return mapTask(task)
}

export async function fetchMothershipChats(
  workspaceId: string,
  scope: MothershipChatScope = 'active',
  signal?: AbortSignal
): Promise<MothershipChatMetadata[]> {
  if (workspaceId !== LINGXI_WORKSPACE_ID) return []
  signal?.throwIfAborted()
  const { tasks } = await getAgentTasks(scope)
  return tasks.map(mapTask)
}

export function useMothershipChats(
  workspaceId?: string,
  options?: { scope?: MothershipChatScope; enabled?: boolean }
) {
  const scope = options?.scope ?? 'active'
  return useQuery({
    queryKey: mothershipChatKeys.list(workspaceId, scope),
    queryFn: () => fetchMothershipChats(workspaceId ?? '', scope),
    enabled: Boolean(workspaceId) && (options?.enabled ?? true),
    staleTime: MOTHERSHIP_CHAT_LIST_STALE_TIME,
  })
}

function snapshotToHistory(task: AgentTaskSnapshot): MothershipChatHistory {
  const active = task.status === 'queued' || task.status === 'running'
  return {
    id: task.id,
    title: task.title || task.intent.topic || task.prompt,
    messages: [
      {
        id: `lingxi-user-${task.id}`,
        role: 'user',
        content: task.prompt,
      },
    ],
    activeStreamId: active ? task.id : null,
    resources: taskResources(task),
    streamSnapshot: null,
  }
}

export async function fetchMothershipChatHistory(
  chatId: string,
  signal?: AbortSignal
): Promise<MothershipChatHistory> {
  signal?.throwIfAborted()
  if (!chatId) throw new Error('缺少 LingxiGraph 任务 ID')
  return snapshotToHistory(await getAgentTask(chatId))
}

export function useMothershipChatHistory(chatId: string | undefined) {
  return useQuery({
    queryKey: mothershipChatKeys.detail(chatId),
    queryFn: () => fetchMothershipChatHistory(chatId ?? ''),
    enabled: Boolean(chatId),
    staleTime: MOTHERSHIP_CHAT_HISTORY_STALE_TIME,
  })
}

function useAgentTaskMutation<TVariables, TResult>(
  mutationFn: (variables: TVariables) => Promise<TResult>
) {
  const queryClient = useQueryClient()
  return useMutation<TResult, Error, TVariables>({
    mutationFn,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: mothershipChatKeys.all })
    },
  })
}

async function suspendNativeTaskResources(taskId: string): Promise<void> {
  await Promise.allSettled([suspendBrowserScope(taskId), suspendTerminalScope(taskId)])
}

export function useMarkMothershipChatUnread(_workspaceId?: string) {
  return useAgentTaskMutation((taskId: string) => updateAgentTask(taskId, { is_unread: true }))
}

export function useMarkMothershipChatRead(_workspaceId?: string) {
  return useAgentTaskMutation((taskId: string) => updateAgentTask(taskId, { is_unread: false }))
}

export function useCreateMothershipChat(_workspaceId?: string) {
  return useAgentTaskMutation(({ title }: { title?: string }) =>
    createAgentTask(title?.trim() || '新学习任务')
  )
}

export function useForkMothershipChat(_workspaceId?: string) {
  return useAgentTaskMutation(({ chatId }: { chatId: string }) => forkAgentTask(chatId))
}

export function useDeleteMothershipChat(_workspaceId?: string) {
  return useAgentTaskMutation(async (chatId: string) => {
    const result = await deleteAgentTask(chatId)
    await suspendNativeTaskResources(chatId)
    return result
  })
}

export function useDeleteMothershipChats(_workspaceId?: string) {
  return useAgentTaskMutation(async (chatIds: string[]) => {
    await Promise.all(
      chatIds.map(async (chatId) => {
        await deleteAgentTask(chatId)
        await suspendNativeTaskResources(chatId)
      })
    )
  })
}

export function useRestoreMothershipChat(_workspaceId?: string) {
  return useAgentTaskMutation((chatId: string) => restoreAgentTask(chatId))
}

export function useUpdateMothershipChat(_workspaceId?: string) {
  return useAgentTaskMutation(
    ({ chatId, title, name }: { chatId: string; title?: string; name?: string }) =>
      updateAgentTask(chatId, { title: title ?? name })
  )
}

export function useRenameMothershipChat(_workspaceId?: string) {
  return useUpdateMothershipChat(_workspaceId)
}

export function useSetMothershipChatPinned(_workspaceId?: string) {
  return useAgentTaskMutation(({ chatId, pinned }: { chatId: string; pinned: boolean }) =>
    updateAgentTask(chatId, { is_pinned: pinned })
  )
}

export function useAddMothershipChatResource(_workspaceId?: string) {
  return useAgentTaskMutation(
    async ({ chatId, resource }: { chatId: string; resource: MothershipResource }) => {
      const task = await getAgentTask(chatId)
      const resources = taskResources(task)
      const next = resources.filter(
        (candidate) => candidate.type !== resource.type || candidate.id !== resource.id
      )
      next.push(resource)
      return updateAgentTask(chatId, { resources: next })
    }
  )
}

export function useRemoveMothershipChatResource(_workspaceId?: string) {
  return useAgentTaskMutation(
    async ({ chatId, resourceId }: { chatId: string; resourceId: string }) => {
      const task = await getAgentTask(chatId)
      const resources = taskResources(task)
      return updateAgentTask(chatId, {
        resources: resources.filter((resource) => resource.id !== resourceId),
      })
    }
  )
}

export function useReorderMothershipChatResources(_workspaceId?: string) {
  return useAgentTaskMutation(
    ({ chatId, resources }: { chatId: string; resources: MothershipResource[] }) =>
      updateAgentTask(chatId, { resources })
  )
}

export function useAddChatResource(_workspaceId?: string) {
  return useAddMothershipChatResource(_workspaceId)
}

export function useRemoveChatResource(_workspaceId?: string) {
  return useAgentTaskMutation(
    async ({
      chatId,
      resourceId,
    }: {
      chatId: string
      resourceId?: string
      resourceType?: MothershipResource['type']
    }) => {
      if (!resourceId) throw new Error('缺少资源 ID')
      const task = await getAgentTask(chatId)
      const resources = taskResources(task)
      return updateAgentTask(chatId, {
        resources: resources.filter((resource) => resource.id !== resourceId),
      })
    }
  )
}

export function useReorderChatResources(_workspaceId?: string) {
  return useReorderMothershipChatResources(_workspaceId)
}
