import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Lingxi API task creation', () => {
  it('creates the first agent task without requiring a server-assigned task id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 't-first', status: 'queued' }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const created = await api.createAgentTask('Explain TCP retransmission')

    expect(created).toEqual({ id: 't-first', status: 'queued' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/agent-tasks')
    const body = JSON.parse(String(init.body)) as Record<string, unknown>
    expect(body.prompt).toBe('Explain TCP retransmission')
    expect(body.idempotency_key).toMatch(/^agent-task:create:/)
  })
})
