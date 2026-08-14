/**
 * @vitest-environment node
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockHeaders } = vi.hoisted(() => ({
  mockHeaders: vi.fn(),
}))

vi.mock('next/headers', () => ({ headers: mockHeaders }))
vi.mock('@/lib/core/utils/urls', () => ({
  getInternalApiBaseUrl: () => 'https://lingxilearn.cn',
}))

import { getSession } from './session-server'

describe('getSession', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockHeaders.mockResolvedValue({ get: () => 'lingxi_session=session-1' })
  })

  it('treats the BFF 401 as an anonymous session', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getSession()).resolves.toBeNull()
    expect(fetchMock).toHaveBeenCalledWith(
      'https://lingxilearn.cn/api/v1/me',
      expect.objectContaining({
        credentials: 'include',
        cache: 'no-store',
        headers: {
          cookie: 'lingxi_session=session-1',
          Accept: 'application/json',
        },
      })
    )
  })

  it('returns the BFF session for an authenticated visitor', async () => {
    const session = {
      principal: { subject: 'user-1', roles: [], permissions: [], audience: [] },
      user: { id: 'user-1', primaryEmail: 'user@example.com' },
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(session)))

    await expect(getSession()).resolves.toEqual(session)
  })

  it('throws for unexpected BFF failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 503 })))

    await expect(getSession()).rejects.toThrow('Failed to load session (503)')
  })
})
