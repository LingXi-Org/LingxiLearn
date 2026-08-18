/**
 * @vitest-environment node
 */
import { describe, expect, it, vi } from 'vitest'
import {
  createRefreshDedupeState,
  decideRefresh,
  invalidateRefreshFreshness,
  trackRefresh,
} from '@/lib/auth/session-refresh-dedupe'

const FRESHNESS_MS = 30 * 1000

/**
 * Simulates SessionProvider.refresh against the pure state machine: one
 * underlying fetcher (identityApi.me) plus the decide/track bookkeeping.
 */
function makeProviderSim(fetcher: () => Promise<string | null>) {
  const state = createRefreshDedupeState()
  let current: string | null = null
  const refresh = (options?: { force?: boolean; now?: number }) => {
    const now = options?.now ?? Date.now()
    const decision = decideRefresh(state, {
      force: options?.force,
      now,
      freshnessMs: FRESHNESS_MS,
      current,
    })
    if (decision.kind !== 'fetch') return Promise.resolve(decision.value as string | null)
    const request = fetcher().then((next) => {
      current = next
      return next
    })
    return trackRefresh(state, request, () => now)
  }
  const expire = () => {
    current = null
    invalidateRefreshFreshness(state)
  }
  return { refresh, expire }
}

describe('session refresh dedupe (SessionProvider contract)', () => {
  it('C: concurrent refresh() calls are single-flight — one fetch for many asks', async () => {
    let resolveFetch: (value: string | null) => void = () => {}
    const fetcher = vi.fn(
      () =>
        new Promise<string | null>((resolve) => {
          resolveFetch = resolve
        })
    )
    const { refresh } = makeProviderSim(fetcher)

    const pending = Promise.all([
      refresh({ force: true }),
      refresh({ force: true }),
      refresh({ force: true }),
      refresh({ force: true }),
      refresh({ force: true }),
    ])

    // Five simultaneous asks share the one in-flight request.
    expect(fetcher).toHaveBeenCalledTimes(1)

    resolveFetch('user-1')
    await expect(pending).resolves.toEqual([
      'user-1',
      'user-1',
      'user-1',
      'user-1',
      'user-1',
    ])
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('D: focus + visibility back to back cost one fetch inside the freshness window', async () => {
    const fetcher = vi.fn().mockResolvedValue('user-1')
    const { refresh } = makeProviderSim(fetcher)

    // Mount-time revalidation (the provider's mount effect always fetches:
    // lastRefreshAt starts at 0, and a real epoch is always outside the window).
    await refresh({ force: true, now: 100_000 })
    expect(fetcher).toHaveBeenCalledTimes(1)

    // Returning to the tab fires focus AND visibilitychange in quick
    // succession; both land inside the freshness window.
    await refresh({ now: 100_000 + FRESHNESS_MS / 2 })
    await refresh({ now: 100_000 + FRESHNESS_MS / 2 + 5 })
    expect(fetcher).toHaveBeenCalledTimes(1)

    // Once the window lapses a tab return revalidates again.
    await refresh({ now: 100_000 + FRESHNESS_MS + 1 })
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('E: forced refresh bypasses the window; expiry reopens it immediately', async () => {
    const fetcher = vi.fn().mockResolvedValue('user-1')
    const { refresh, expire } = makeProviderSim(fetcher)

    await refresh({ force: true, now: 100_000 })
    expect(fetcher).toHaveBeenCalledTimes(1)

    // Explicit refresh (login/logout/explicit refetch) ignores freshness.
    await refresh({ force: true, now: 100_500 })
    expect(fetcher).toHaveBeenCalledTimes(2)

    // A resource 401 clears the session; the very next non-forced ask must
    // revalidate instead of returning the stale window's answer.
    expire()
    await refresh({ now: 101_000 })
    expect(fetcher).toHaveBeenCalledTimes(3)
  })

  it('A/B: reads never fetch — one mount fetch serves every consumer', async () => {
    const fetcher = vi.fn().mockResolvedValue('user-1')
    const { refresh } = makeProviderSim(fetcher)

    // The provider mounts once and resolves the session once; every consumer
    // (useSession hook or snapshot read) is then a pure state read.
    const mounted = await refresh({ force: true, now: 100_000 })
    expect(mounted).toBe('user-1')
    expect(fetcher).toHaveBeenCalledTimes(1)

    // Many consumers asking for the current session within the window all
    // answer from state — the fetcher is never re-entered.
    for (let consumer = 0; consumer < 10; consumer += 1) {
      await expect(refresh({ now: 100_000 + consumer })).resolves.toBe('user-1')
    }
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('a failed attempt still stamps the window, so error storms stay bounded', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('network partition'))
    const { refresh } = makeProviderSim(fetcher)

    await expect(refresh({ force: true, now: 100_000 })).rejects.toThrow('network partition')
    await refresh({ now: 100_500 })

    expect(fetcher).toHaveBeenCalledTimes(1)
  })
})
