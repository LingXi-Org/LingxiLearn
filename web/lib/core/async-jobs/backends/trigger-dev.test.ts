/** @vitest-environment node */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockRetrieve, mockResolveTriggerRegion, mockTrigger } = vi.hoisted(() => ({
  mockRetrieve: vi.fn(),
  mockResolveTriggerRegion: vi.fn(),
  mockTrigger: vi.fn(),
}))

vi.mock('@/lib/logger', () => ({
  createLogger: () => ({ debug: vi.fn(), error: vi.fn(), info: vi.fn(), warn: vi.fn() }),
}))
vi.mock('@trigger.dev/core/v3', () => ({ taskContext: { isInsideTask: false } }))
vi.mock('@trigger.dev/sdk', () => ({
  runs: { cancel: vi.fn(), list: vi.fn(), retrieve: mockRetrieve },
  tasks: { batchTriggerAndWait: vi.fn(), trigger: mockTrigger },
}))
vi.mock('@/lib/core/async-jobs/region', () => ({
  resolveTriggerRegion: mockResolveTriggerRegion,
}))

import { TriggerDevJobQueue } from '@/lib/core/async-jobs/backends/trigger-dev'

describe('TriggerDevJobQueue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockResolveTriggerRegion.mockResolvedValue('us-east-1')
    mockTrigger.mockResolvedValue({ id: 'run-1' })
  })

  it('enqueues the retained webhook task with a stable idempotency key', async () => {
    const queue = new TriggerDevJobQueue()

    await expect(
      queue.enqueue('webhook-execution', { executionId: 'execution-1' }, { jobId: 'webhook:1' })
    ).resolves.toBe('run-1')
    expect(mockTrigger).toHaveBeenCalledWith(
      'webhook-execution',
      { executionId: 'execution-1' },
      expect.objectContaining({ idempotencyKey: 'webhook:1', region: 'us-east-1' })
    )
  })

  it('rejects a retired job type instead of dispatching an undeployed task', async () => {
    const queue = new TriggerDevJobQueue()

    await expect(queue.enqueue('workflow-execution' as never, {})).rejects.toThrow(
      'Unknown job type: workflow-execution'
    )
    expect(mockTrigger).not.toHaveBeenCalled()
  })

  it('maps active provider status to processing', async () => {
    mockRetrieve.mockResolvedValue({
      id: 'run-1',
      payload: {},
      status: 'EXECUTING',
      taskIdentifier: 'webhook-execution',
    })
    const queue = new TriggerDevJobQueue()

    await expect(queue.getJob('run-1')).resolves.toMatchObject({
      id: 'run-1',
      status: 'processing',
      type: 'webhook-execution',
    })
  })
})
