import { afterEach, describe, expect, it, vi } from 'vitest'
import { createAgentTask, sendAgentMessage } from './agent-tasks'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Agent task API', () => {
  it('creates the first agent task without requiring a server-assigned task id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 't-first', status: 'queued' }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const created = await createAgentTask('Explain TCP retransmission')

    expect(created).toEqual({ id: 't-first', status: 'queued' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/agent-tasks')
    const body = JSON.parse(String(init.body)) as Record<string, unknown>
    expect(body.prompt).toBe('Explain TCP retransmission')
    expect(body.idempotency_key).toMatch(/^agent-task:create:/)
  })

  it('sends the caller-provided idempotency key for a follow-up message', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'accepted' }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await sendAgentMessage('task-1', 'Continue with the next step', [], {
      idempotencyKey: 'lingxi-message:queued-1',
    })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const body = JSON.parse(String(init.body)) as Record<string, unknown>
    expect(body.idempotency_key).toBe('lingxi-message:queued-1')
  })
})
