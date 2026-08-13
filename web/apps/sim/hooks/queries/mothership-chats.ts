'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/lingxi/api'
import { LINGXI_WORKSPACE_ID } from '@/lib/lingxi/capabilities'
import type { AgentTaskListItem, AgentTaskSnapshot } from '@/lib/lingxi/types'
import type { ChatMessage, MothershipResource } from '@/app/workspace/[workspaceId]/home/types'

/**
 * Sim's chat query namespace is kept as a compatibility seam for the copied
 * workspace chrome. Its implementation is deliberately Lingxi-only: there is
 * no fallback to /api/mothership, database contracts, or persisted Sim chat
 * records in the browser bundle.
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
  messages: ChatMessage[]
  activeStreamId: string | null
  resources: MothershipResource[]
  streamSnapshot: null
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

function taskName(task: Pick<AgentTaskListItem, 'prompt' | 'intent' | 'title'>): string {
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

/** Retained for copied Sim modules; it only maps the Lingxi list shape. */
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
  const { tasks } = await api.agentTasks(scope)
  return tasks.map(mapTask)
}

export function useMothershipChats(
  workspaceId?: string,
  options?: { scope?: MothershipChatScope; enabled?: boolean }
) {
  const scope = options?.scope ?? 'active'
  return useQuery({
    queryKey: mothershipChatKeys.list(workspaceId, scope),
    queryFn: workspaceId ? () => fetchMothershipChats(workspaceId, scope) : undefined,
    enabled: Boolean(workspaceId) && (options?.enabled ?? true),
    staleTime: MOTHERSHIP_CHAT_LIST_STALE_TIME,
  })
}

function snapshotToHistory(task: AgentTaskSnapshot): MothershipChatHistory {
  const active = task.status === 'queued' || task.status === 'running'
  return {
    id: task.id,
    title: task.intent.topic || task.prompt,
    messages: [
      {
        id: `lingxi-user-${task.id}`,
        role: 'user',
        content: task.prompt,
      },
    ],
    activeStreamId: active ? task.id : null,
    resources: (task.resources ?? []) as MothershipResource[],
    streamSnapshot: null,
  }
}

export async function fetchMothershipChatHistory(
  chatId: string,
  signal?: AbortSignal
): Promise<MothershipChatHistory> {
  signal?.throwIfAborted()
  if (!chatId) throw new Error('缺少 LingxiGraph 任务 ID')
  return snapshotToHistory(await api.agentTask(chatId))
}

export function useMothershipChatHistory(chatId: string | undefined) {
  return useQuery({
    queryKey: mothershipChatKeys.detail(chatId),
    queryFn: chatId ? () => fetchMothershipChatHistory(chatId) : undefined,
    enabled: Boolean(chatId),
    staleTime: MOTHERSHIP_CHAT_HISTORY_STALE_TIME,
  })
}

function invalidateChatLists(queryClient: ReturnType<typeof useQueryClient>, workspaceId?: string) {
  void queryClient.invalidateQueries({ queryKey: mothershipChatKeys.workspaceLists(workspaceId) })
  void queryClient.invalidateQueries({ queryKey: mothershipChatKeys.details() })
}

/** Chat mutations remain visible to copied Sim controls but never issue calls. */
export function useMarkMothershipChatRead(workspaceId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (chatId: string) => api.updateAgentTask(chatId, { is_unread: false }),
    onSuccess: () => invalidateChatLists(queryClient, workspaceId),
  })
}

/** Compatibility mutations used by the copied workspace sidebar. */
export function useMarkMothershipChatUnread(workspaceId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (chatId: string) => api.updateAgentTask(chatId, { is_unread: true }),
    onSuccess: () => invalidateChatLists(queryClient, workspaceId),
  })
}

export function useCreateMothershipChat(_workspaceId?: string) {
  return useMutation({ mutationFn: async ({ title }: { title?: string }) => api.createAgentTask(title || '新学习任务') })
}

export function useForkMothershipChat(workspaceId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ chatId }: { chatId: string }) => api.forkAgentTask(chatId),
    onSuccess: () => invalidateChatLists(queryClient, workspaceId),
  })
}

export function useDeleteMothershipChat(workspaceId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (chatId: string) => api.deleteAgentTask(chatId), onSuccess: () => invalidateChatLists(queryClient, workspaceId) })
}

export function useDeleteMothershipChats(workspaceId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (chatIds: string[]) => Promise.all(chatIds.map((id) => api.deleteAgentTask(id))), onSuccess: () => invalidateChatLists(queryClient, workspaceId) })
}

export function useRestoreMothershipChat(workspaceId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (chatId: string) => api.restoreAgentTask(chatId), onSuccess: () => invalidateChatLists(queryClient, workspaceId) })
}

export function useUpdateMothershipChat(workspaceId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ chatId, title, name }: { chatId: string; title?: string; name?: string }) => api.updateAgentTask(chatId, { title: title ?? name }),
    onSuccess: () => invalidateChatLists(queryClient, workspaceId),
  })
}

export function useRenameMothershipChat(_workspaceId?: string) {
  return useUpdateMothershipChat(_workspaceId)
}

export function useSetMothershipChatPinned(workspaceId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ chatId, pinned }: { chatId: string; pinned: boolean }) => api.updateAgentTask(chatId, { is_pinned: pinned }),
    onSuccess: () => invalidateChatLists(queryClient, workspaceId),
  })
}

export function useAddMothershipChatResource(workspaceId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ chatId, resource }: { chatId: string; resource: MothershipResource }) => {
      const current = queryClient.getQueryData<MothershipChatHistory>(mothershipChatKeys.detail(chatId))
      return api.updateAgentTask(chatId, { resources: [...(current?.resources ?? []), resource] as Array<Record<string, unknown>> })
    },
    onSuccess: () => invalidateChatLists(queryClient, workspaceId),
  })
}

export function useRemoveMothershipChatResource(workspaceId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ chatId, resourceId }: { chatId: string; resourceId: string }) => {
      const current = queryClient.getQueryData<MothershipChatHistory>(mothershipChatKeys.detail(chatId))
      return api.updateAgentTask(chatId, { resources: (current?.resources ?? []).filter((resource) => resource.id !== resourceId) as Array<Record<string, unknown>> })
    },
    onSuccess: () => invalidateChatLists(queryClient, workspaceId),
  })
}

export function useReorderMothershipChatResources(workspaceId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ chatId, resources }: { chatId: string; resources: MothershipResource[] }) => api.updateAgentTask(chatId, { resources: resources as Array<Record<string, unknown>> }),
    onSuccess: () => invalidateChatLists(queryClient, workspaceId),
  })
}

export function useAddChatResource(_workspaceId?: string) {
  return useAddMothershipChatResource(_workspaceId)
}

export function useRemoveChatResource(_workspaceId?: string) {
  return useRemoveMothershipChatResource(_workspaceId)
}

export function useReorderChatResources(_workspaceId?: string) {
  return useReorderMothershipChatResources(_workspaceId)
}
