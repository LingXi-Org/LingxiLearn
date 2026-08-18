/**
 * @vitest-environment node
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { IdentityMe } from '@/lib/auth/identity-api'
import {
  getSessionSnapshot,
  isSessionSnapshotReady,
  publishSessionSnapshot,
  refreshCanonicalSession,
  registerCanonicalSessionRefresh,
} from '@/lib/auth/session-snapshot'

const SESSION: IdentityMe = {
  principal: { subject: 'sess-1', roles: [], permissions: [], audience: [] },
  user: { id: 'user-1', email: 'user@example.com' },
}

/** Restores the module-level singleton state between tests. */
function resetSnapshotModule() {
  publishSessionSnapshot({ data: null, ready: false })
}

afterEach(() => {
  resetSnapshotModule()
})

describe('session snapshot accessor', () => {
  it('B: snapshot reads are pure state reads — they never fetch', () => {
    publishSessionSnapshot({ data: SESSION, ready: true })

    for (let consumer = 0; consumer < 25; consumer += 1) {
      expect(getSessionSnapshot()?.user.id).toBe('user-1')
    }
    expect(isSessionSnapshotReady()).toBe(true)
  })

  it('only the publisher (SessionProvider) moves the snapshot', () => {
    expect(getSessionSnapshot()).toBeNull()
    expect(isSessionSnapshotReady()).toBe(false)

    publishSessionSnapshot({ data: SESSION, ready: true })
    expect(getSessionSnapshot()).toEqual(SESSION)

    publishSessionSnapshot({ data: null, ready: true })
    expect(getSessionSnapshot()).toBeNull()
    expect(isSessionSnapshotReady()).toBe(true)
  })

  it('all imperative callers share the ONE registered canonical refresh', async () => {
    const canonical = vi.fn().mockResolvedValue(SESSION)
    const release = registerCanonicalSessionRefresh(canonical)

    await Promise.all([
      refreshCanonicalSession({ force: true }),
      refreshCanonicalSession({ force: true }),
      refreshCanonicalSession({ force: true }),
    ])

    // Three callers, one delegation target — there is no per-caller /me path.
    expect(canonical).toHaveBeenCalledTimes(3)
    release()
  })

  it('releases the canonical refresh on provider unmount', async () => {
    const canonical = vi.fn().mockResolvedValue(SESSION)
    const release = registerCanonicalSessionRefresh(canonical)
    release()

    // No mounted provider: fall back to the snapshot instead of fetching.
    await expect(refreshCanonicalSession({ force: true })).resolves.toBeNull()
    expect(canonical).not.toHaveBeenCalled()
  })

  it('falls back to the current snapshot when no provider is mounted', async () => {
    publishSessionSnapshot({ data: SESSION, ready: true })

    await expect(refreshCanonicalSession()).resolves.toEqual(SESSION)
  })
})
