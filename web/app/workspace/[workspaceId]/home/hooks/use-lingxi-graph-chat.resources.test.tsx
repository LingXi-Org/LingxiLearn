/**
 * @vitest-environment jsdom
 */

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { MothershipResource } from '@/lib/copilot/resources/types'
import type { LingxiTaskTransport } from '@/lib/lingxi/lingxi-task-transport'
import type { AgentTaskSnapshot } from '@/lib/lingxi/types'

const api = vi.hoisted(() => ({
  answerAgentInteraction: vi.fn(),
  createAgentTask: vi.fn(),
  deleteAgentTask: vi.fn(),
  forkAgentTask: vi.fn(),
  getAgentTask: vi.fn(),
  getAgentTasks: vi.fn(),
  getAgentTaskV1Events: vi.fn(),
  getExecutionSnapshot: vi.fn(),
  getRuntimeGraph: vi.fn(),
  recordLearningEvent: vi.fn(),
  restoreAgentTask: vi.fn(),
  subscribeAgentV1Events: vi.fn(),
  updateAgentTask: vi.fn(),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))
vi.mock('@/lib/api/domains/agent-tasks', () => api)
vi.mock('@/lib/browser-agent/transport', () => ({ suspendBrowserScope: vi.fn() }))
vi.mock('@/lib/terminal/transport', () => ({ suspendTerminalScope: vi.fn() }))

import { useWorkspaceChatController } from './use-lingxi-graph-chat'

function taskWithResources(resources: MothershipResource[]): AgentTaskSnapshot {
  return {
    id: 'task-1',
    status: 'completed',
    prompt: 'Review resources',
    graph_version: 'v1',
    intent: { topic: 'Resources' },
    agents: {},
    resources,
    artifacts: {
      lesson_intro: { available: false },
      lecture_deck: { available: false },
      quiz: { available: false },
      visual: { available: false },
    },
    delivery: { order: [], queue: [], cursor: 0 },
    quiz_submission: null,
    error: '',
    created_at: '2026-08-26T00:00:00Z',
    updated_at: '2026-08-26T00:00:00Z',
  }
}

function cloneTask(task: AgentTaskSnapshot): AgentTaskSnapshot {
  return structuredClone(task)
}

let serverTask: AgentTaskSnapshot
const mounted: Array<{ root: Root; queryClient: QueryClient; container: HTMLDivElement }> = []

function renderController() {
  ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  const container = document.createElement('div')
  const root = createRoot(container)
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const adapter: LingxiTaskTransport = {
    createTask: vi.fn(),
    loadTask: vi.fn(async () => cloneTask(serverTask)),
    loadEvents: vi.fn(async () => []),
    sendMessage: vi.fn(),
    cancelTask: vi.fn(),
    updateTaskMetadata: vi.fn(),
    subscribe: vi.fn(() => () => {}),
  }
  let current: ReturnType<typeof useWorkspaceChatController> | null = null

  function Probe() {
    current = useWorkspaceChatController('lingxi', 'task-1', { adapter })
    return null
  }

  act(() => {
    root.render(
      <QueryClientProvider client={queryClient}>
        <Probe />
      </QueryClientProvider>
    )
  })
  mounted.push({ root, queryClient, container })

  return {
    value: () => {
      if (!current) throw new Error('controller has not rendered')
      return current
    },
  }
}

async function waitFor(assertion: () => void): Promise<void> {
  let lastError: unknown
  for (let attempt = 0; attempt < 40; attempt += 1) {
    await act(async () => {
      await new Promise((resolve) => globalThis.setTimeout(resolve, 0))
    })
    try {
      assertion()
      return
    } catch (cause) {
      lastError = cause
    }
  }
  throw lastError
}

describe('workspace controller native resource mutations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    serverTask = taskWithResources([])
    api.getAgentTask.mockImplementation(async () => cloneTask(serverTask))
    api.updateAgentTask.mockImplementation(
      async (_taskId: string, patch: { resources?: MothershipResource[] }) => {
        if (patch.resources) serverTask = { ...serverTask, resources: cloneTaskResources(patch.resources) }
        return {
          id: serverTask.id,
          title: serverTask.title ?? '',
          is_pinned: false,
          is_unread: false,
          resources: serverTask.resources ?? [],
        }
      }
    )
    api.getAgentTaskV1Events.mockResolvedValue({ protocol: 'v1', events: [] })
    api.getRuntimeGraph.mockResolvedValue({ workflowState: {} })
    api.getExecutionSnapshot.mockResolvedValue({ workflowState: {} })
    api.subscribeAgentV1Events.mockReturnValue(() => {})
    api.recordLearningEvent.mockResolvedValue(undefined)
  })

  afterEach(() => {
    for (const handle of mounted.splice(0)) {
      act(() => handle.root.unmount())
      handle.queryClient.clear()
      handle.container.remove()
    }
  })

  it('shows an added resource immediately and restores it after reopening the task', async () => {
    const file: MothershipResource = { type: 'file', id: 'file-1', title: 'Spec.md' }
    const first = renderController()
    await waitFor(() => expect(first.value().lingxiRuntime?.task?.id).toBe('task-1'))

    let accepted = false
    act(() => {
      accepted = first.value().addResource(file)
    })
    expect(accepted).toBe(true)
    expect(first.value().resources).toContainEqual(file)
    await waitFor(() => expect(serverTask.resources).toEqual([file]))

    const reopened = renderController()
    await waitFor(() => expect(reopened.value().resources).toContainEqual(file))
  })

  it('removes only the matching type-and-id resource from the task snapshot', async () => {
    serverTask = taskWithResources([
      { type: 'file', id: 'shared-id', title: 'Spec.md' },
      { type: 'table', id: 'shared-id', title: 'Scores' },
    ])
    const controller = renderController()
    await waitFor(() => expect(controller.value().resources).toHaveLength(3))

    act(() => controller.value().removeResource('file', 'shared-id'))
    expect(controller.value().resources.filter((resource) => resource.id === 'shared-id')).toEqual([
      { type: 'table', id: 'shared-id', title: 'Scores' },
    ])
    await waitFor(() =>
      expect(serverTask.resources).toEqual([
        { type: 'table', id: 'shared-id', title: 'Scores' },
      ])
    )
  })

  it('persists resource ordering and keeps it after the confirmation refresh', async () => {
    const file: MothershipResource = { type: 'file', id: 'file-1', title: 'Spec.md' }
    const table: MothershipResource = { type: 'table', id: 'table-1', title: 'Scores' }
    serverTask = taskWithResources([file, table])
    const controller = renderController()
    await waitFor(() => expect(controller.value().resources).toHaveLength(3))

    act(() => controller.value().reorderResources([table, file]))
    expect(controller.value().resources.filter((resource) => resource.type !== 'generic')).toEqual([
      table,
      file,
    ])
    await waitFor(() => expect(serverTask.resources).toEqual([table, file]))
    await waitFor(() =>
      expect(controller.value().resources.filter((resource) => resource.type !== 'generic')).toEqual([
        table,
        file,
      ])
    )
  })
})

function cloneTaskResources(resources: MothershipResource[]): MothershipResource[] {
  return structuredClone(resources)
}
