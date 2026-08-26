/**
 * @vitest-environment node
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AgentTaskListItem, AgentTaskSnapshot } from '@/lib/lingxi/types'

const {
  createAgentTask,
  deleteAgentTask,
  forkAgentTask,
  getAgentTask,
  getAgentTasks,
  queryClient,
  restoreAgentTask,
  suspendBrowserScope,
  suspendTerminalScope,
  updateAgentTask,
} = vi.hoisted(() => ({
  createAgentTask: vi.fn(),
  deleteAgentTask: vi.fn(),
  forkAgentTask: vi.fn(),
  getAgentTask: vi.fn(),
  getAgentTasks: vi.fn(),
  queryClient: { invalidateQueries: vi.fn().mockResolvedValue(undefined) },
  restoreAgentTask: vi.fn(),
  suspendBrowserScope: vi.fn().mockResolvedValue(true),
  suspendTerminalScope: vi.fn().mockResolvedValue(true),
  updateAgentTask: vi.fn(),
}))

vi.mock('@/lib/api/domains/agent-tasks', () => ({
  createAgentTask,
  deleteAgentTask,
  forkAgentTask,
  getAgentTask,
  getAgentTasks,
  restoreAgentTask,
  updateAgentTask,
}))

vi.mock('@/lib/browser-agent/transport', () => ({ suspendBrowserScope }))
vi.mock('@/lib/terminal/transport', () => ({ suspendTerminalScope }))

vi.mock('@tanstack/react-query', () => ({
  useMutation: vi.fn((options) => options),
  useQuery: vi.fn((options) => options),
  useQueryClient: vi.fn(() => queryClient),
}))

import {
  fetchMothershipChatHistory,
  fetchMothershipChats,
  useAddChatResource,
  useDeleteMothershipChat,
  useDeleteMothershipChats,
  useMarkMothershipChatRead,
  useRemoveChatResource,
  useReorderChatResources,
} from '@/hooks/queries/mothership-chats'

const listTask: AgentTaskListItem = {
  id: 'task-1',
  prompt: 'Original prompt',
  title: 'Native title',
  status: 'running',
  intent: { topic: 'Intent topic' },
  created_at: '2026-04-11T09:00:00.000Z',
  updated_at: '2026-04-11T10:00:00.000Z',
  is_pinned: true,
  is_unread: true,
  deleted_at: null,
  resources: [],
}

const snapshot = {
  id: 'task-1',
  prompt: 'Original prompt',
  title: 'Native title',
  status: 'running',
  intent: { topic: 'Intent topic' },
  resources: [{ type: 'file', id: 'file-1', title: 'Spec.md' }],
  created_at: '2026-04-11T09:00:00.000Z',
  updated_at: '2026-04-11T10:00:00.000Z',
} as AgentTaskSnapshot

describe('native agent-task chat compatibility', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getAgentTasks.mockResolvedValue({ tasks: [listTask] })
    getAgentTask.mockResolvedValue(snapshot)
    updateAgentTask.mockResolvedValue({ id: 'task-1', resources: snapshot.resources })
    deleteAgentTask.mockResolvedValue({ id: 'task-1', deleted_at: '2026-04-11T11:00:00Z' })
  })

  it('maps native task metadata without inventing chat state', async () => {
    const tasks = await fetchMothershipChats('lingxi')

    expect(getAgentTasks).toHaveBeenCalledWith('active')
    expect(tasks).toEqual([
      {
        id: 'task-1',
        name: 'Native title',
        updatedAt: new Date('2026-04-11T10:00:00.000Z'),
        isActive: true,
        isUnread: true,
        isPinned: true,
        deletedAt: null,
      },
    ])
  })

  it('passes archived scope to the native task API and rejects foreign workspaces locally', async () => {
    await fetchMothershipChats('lingxi', 'archived')
    expect(getAgentTasks).toHaveBeenCalledWith('archived')

    vi.clearAllMocks()
    await expect(fetchMothershipChats('foreign-workspace')).resolves.toEqual([])
    expect(getAgentTasks).not.toHaveBeenCalled()
  })

  it('projects native snapshot metadata and persisted resources into history', async () => {
    await expect(fetchMothershipChatHistory('task-1')).resolves.toEqual({
      id: 'task-1',
      title: 'Native title',
      messages: [{ id: 'lingxi-user-task-1', role: 'user', content: 'Original prompt' }],
      activeStreamId: 'task-1',
      resources: snapshot.resources,
      streamSnapshot: null,
    })
  })

  it('marks a task read through the native metadata endpoint', async () => {
    const mutation = useMarkMothershipChatRead('lingxi') as unknown as {
      mutationFn: (taskId: string) => Promise<unknown>
      onSuccess: () => Promise<void>
    }

    await mutation.mutationFn('task-1')
    expect(updateAgentTask).toHaveBeenCalledWith('task-1', { is_unread: false })
    await mutation.onSuccess()
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['lingxi-agent-tasks'],
    })
  })

  it('suspends native browser and terminal scopes only after a successful delete', async () => {
    const mutation = useDeleteMothershipChat('lingxi') as unknown as {
      mutationFn: (taskId: string) => Promise<unknown>
    }

    await mutation.mutationFn('task-1')
    expect(suspendBrowserScope).toHaveBeenCalledWith('task-1')
    expect(suspendTerminalScope).toHaveBeenCalledWith('task-1')

    vi.clearAllMocks()
    deleteAgentTask.mockRejectedValueOnce(new Error('delete failed'))
    await expect(mutation.mutationFn('task-2')).rejects.toThrow('delete failed')
    expect(suspendBrowserScope).not.toHaveBeenCalled()
    expect(suspendTerminalScope).not.toHaveBeenCalled()
  })

  it('cleans up every successfully deleted task when a bulk sibling fails', async () => {
    deleteAgentTask.mockImplementation(async (taskId: string) => {
      if (taskId === 'task-b') throw new Error('delete failed')
      return { id: taskId, deleted_at: '2026-04-11T11:00:00Z' }
    })
    const mutation = useDeleteMothershipChats('lingxi') as unknown as {
      mutationFn: (taskIds: string[]) => Promise<void>
    }

    await expect(mutation.mutationFn(['task-a', 'task-b'])).rejects.toThrow('delete failed')
    expect(suspendBrowserScope).toHaveBeenCalledWith('task-a')
    expect(suspendTerminalScope).toHaveBeenCalledWith('task-a')
    expect(suspendBrowserScope).not.toHaveBeenCalledWith('task-b')
  })

  it('persists add, remove, and reorder operations through native task resources', async () => {
    const add = useAddChatResource('task-1') as unknown as {
      mutationFn: (input: { chatId: string; resource: Record<string, unknown> }) => Promise<unknown>
    }
    const remove = useRemoveChatResource('task-1') as unknown as {
      mutationFn: (input: { chatId: string; resourceId: string }) => Promise<unknown>
    }
    const reorder = useReorderChatResources('task-1') as unknown as {
      mutationFn: (input: {
        chatId: string
        resources: Array<Record<string, unknown>>
      }) => Promise<unknown>
    }

    const table = { type: 'table', id: 'table-1', title: 'Scores' }
    await add.mutationFn({ chatId: 'task-1', resource: table })
    expect(updateAgentTask).toHaveBeenLastCalledWith('task-1', {
      resources: [...(snapshot.resources ?? []), table],
    })

    await remove.mutationFn({ chatId: 'task-1', resourceId: 'file-1' })
    expect(updateAgentTask).toHaveBeenLastCalledWith('task-1', { resources: [] })

    await reorder.mutationFn({ chatId: 'task-1', resources: [table] })
    expect(updateAgentTask).toHaveBeenLastCalledWith('task-1', { resources: [table] })
  })
})
