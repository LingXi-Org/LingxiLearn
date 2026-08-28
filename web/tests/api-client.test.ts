import { afterEach, describe, expect, it, vi } from 'vitest'
import { type ApiError, agentTaskApi, artifactApi } from '@/shared/api/client'

afterEach(() => vi.unstubAllGlobals())

describe('V1 API client', () => {
  it('uses the canonical artifact content route', () => {
    expect(artifactApi.contentUrl('workspace-a', 'artifact-b')).toBe(
      '/api/workspaces/workspace-a/artifacts/artifact-b/content',
    )
  })

  it('sends a canonical agent task payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 'task-a', status: 'queued' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await agentTaskApi.create('Explain causal inference')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/agent-tasks',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ prompt: 'Explain causal inference', resources: [] }),
        credentials: 'include',
      }),
    )
  })

  it('surfaces an HTTP failure as ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'identity required' }), {
          status: 401,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    )

    await expect(agentTaskApi.list()).rejects.toEqual(
      expect.objectContaining<ApiError>({
        name: 'ApiError',
        status: 401,
        message: 'identity required',
      }),
    )
  })
})
