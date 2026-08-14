'use client'

import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '@/lib/lingxi/api'
import { LINGXI_WORKSPACE_ID } from '@/lib/lingxi/capabilities'
import type { AgentTaskListItem, AgentTaskSnapshot } from '@/lib/lingxi/types'
import type { ChatMessage, MothershipResource } from '@/app/workspace/[workspaceId]/home/types'

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

function taskName(task: Pick<AgentTaskListItem, 'prompt' | 'intent'>): string {
  return task.intent.topic || task.prompt || '新学习任务'
}

function mapTask(task: AgentTaskListItem): MothershipChatMetadata {
  const updatedAt = new Date(task.updated_at || task.created_at || 0)
  return {
    id: task.id,
    name: taskName(task),
    updatedAt,
    isActive: task.status === 'queued' || task.status === 'running',
    isUnread: false,
    isPinned: false,
    deletedAt: null,
  }
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
  if (workspaceId !== LINGXI_WORKSPACE_ID || scope === 'archived') return []
  signal?.throwIfAborted()
  const { tasks } = await api.agentTasks()
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
    title: task.intent.topic || task.prompt,
    messages: [
      {
        id: `lingxi-user-${task.id}`,
        role: 'user',
        content: task.prompt,
      },
    ],
    activeStreamId: active ? task.id : null,
    resources: [],
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
    queryFn: () => fetchMothershipChatHistory(chatId ?? ''),
    enabled: Boolean(chatId),
    staleTime: MOTHERSHIP_CHAT_HISTORY_STALE_TIME,
  })
}

function unsupportedMutation<TVariables = unknown, TResult = never>() {
  return useMutation<TResult, Error, TVariables>({
    mutationFn: async () => {
      throw new Error('该共享功能未接入 LingxiGraph')
    },
  })
}

/** Chat mutations remain visible to reused controls but never issue calls. */
export function useMarkMothershipChatRead(_workspaceId?: string) {
  return useMutation<void, Error, string>({ mutationFn: async () => undefined })
}

/** Compatibility mutations used by the copied workspace sidebar. */
export function useMarkMothershipChatUnread(_workspaceId?: string) {
  return useMutation<void, Error, string>({ mutationFn: async () => undefined })
}

export function useCreateMothershipChat(_workspaceId?: string) {
  return unsupportedMutation<{ title?: string }>()
}

export function useForkMothershipChat(_workspaceId?: string) {
  return unsupportedMutation<{ chatId: string }>()
}

export function useDeleteMothershipChat(_workspaceId?: string) {
  return unsupportedMutation<string>()
}

export function useDeleteMothershipChats(_workspaceId?: string) {
  return unsupportedMutation<string[]>()
}

export function useRestoreMothershipChat(_workspaceId?: string) {
  return unsupportedMutation<string>()
}

export function useUpdateMothershipChat(_workspaceId?: string) {
  return unsupportedMutation<{ chatId: string; title?: string; name?: string }>()
}

export function useRenameMothershipChat(_workspaceId?: string) {
  return useUpdateMothershipChat(_workspaceId)
}

export function useSetMothershipChatPinned(_workspaceId?: string) {
  return unsupportedMutation<{ chatId: string; pinned: boolean }>()
}

export function useAddMothershipChatResource(_workspaceId?: string) {
  return unsupportedMutation<{ chatId: string; resource: MothershipResource }>()
}

export function useRemoveMothershipChatResource(_workspaceId?: string) {
  return unsupportedMutation<{ chatId: string; resourceId: string }>()
}

export function useReorderMothershipChatResources(_workspaceId?: string) {
  return unsupportedMutation<{ chatId: string; resources: MothershipResource[] }>()
}

export function useAddChatResource(_workspaceId?: string) {
  return useAddMothershipChatResource(_workspaceId)
}

export function useRemoveChatResource(_workspaceId?: string) {
  return unsupportedMutation<{
    chatId: string
    resourceId?: string
    resourceType?: MothershipResource['type']
  }>()
}

export function useReorderChatResources(_workspaceId?: string) {
  return useReorderMothershipChatResources(_workspaceId)
}
