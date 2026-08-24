'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { isMockAuthEnabled } from '@/lib/core/config/env-flags'
import { setAuthenticationFailureHandler, setSessionRefreshHandler } from '@/lib/lingxi/api'
import { clearUserData } from '@/stores'
import { type IdentityMe, identityApi } from './identity-api'
import { MOCK_IDENTITY_ME } from './mock-session'
import {
  createRefreshDedupeState,
  decideRefresh,
  invalidateRefreshFreshness,
  trackRefresh,
} from './session-refresh-dedupe'
import {
  publishSessionSnapshot,
  registerCanonicalSessionRefresh,
  type SessionRefreshOptions,
} from './session-snapshot'

export interface SessionContextValue {
  data: IdentityMe | null
  ready: boolean
  authenticated: boolean
  error: string | null
  refresh: (options?: SessionRefreshOptions) => Promise<IdentityMe | null>
  logout: () => Promise<void>
}

export const SessionContext = createContext<SessionContextValue | null>(null)

/**
 * How long a completed session revalidation stays fresh. A tab return fires
 * `focus` AND `visibilitychange` back to back, and both ask for a refresh —
 * inside this window the second (and every later) ask is answered from the
 * current state instead of hitting `/api/v1/me` again. Deliberately a plain
 * timestamp comparison, not a cache framework.
 */
export const SESSION_REFRESH_FRESHNESS_MS = 30 * 1000

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<IdentityMe | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const dedupe = useRef(createRefreshDedupeState())
  const dataRef = useRef<IdentityMe | null>(null)
  dataRef.current = data

  const refresh = useCallback(async (options?: SessionRefreshOptions) => {
    // Single-flight + freshness, decided by the shared pure state machine:
    // concurrent asks join the one in-flight request, and a non-forced ask
    // inside the freshness window reuses the current state — so focus +
    // visibilitychange collapsing onto one tab return costs one request, not
    // two. Forced asks (login/logout/expiry/explicit refresh) always
    // revalidate.
    const decision = decideRefresh(dedupe.current, {
      force: options?.force,
      now: Date.now(),
      freshnessMs: SESSION_REFRESH_FRESHNESS_MS,
      current: dataRef.current,
    })
    if (decision.kind !== 'fetch') {
      return decision.value as Promise<IdentityMe | null> | IdentityMe | null
    }

    const request = (async () => {
      try {
        if (isMockAuthEnabled) {
          setData(MOCK_IDENTITY_ME)
          setError(null)
          setReady(true)
          return MOCK_IDENTITY_ME
        }
        const next = await identityApi.me()
        setData(next)
        setError(null)
        return next
      } catch (cause) {
        const status = (cause as { status?: number }).status
        const unauthenticated =
          status === 401 ||
          status === 403 ||
          (cause instanceof Error && /unauthorized|session_expired/i.test(cause.message))
        if (unauthenticated) {
          setData(null)
          setError(null)
        } else if (cause instanceof Error) {
          // Preserve a known session during a transient BFF/network failure.
          // The next focus/visibility event can recover it without flashing
          // the whole app back to a signed-out state.
          setError(cause.message)
        }
        return null
      } finally {
        setReady(true)
      }
    })()

    return trackRefresh(dedupe.current, request, Date.now)
  }, [])

  const logout = useCallback(async () => {
    if (!isMockAuthEnabled) await identityApi.logout()
    await clearUserData()
    setData(null)
    window.location.assign('/')
  }, [])

  useEffect(() => {
    void refresh()
    const onFocus = () => void refresh()
    const onVisibility = () => {
      if (document.visibilityState === 'visible') void refresh()
    }
    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVisibility)
    const releaseFailure = setAuthenticationFailureHandler(() => {
      setData(null)
      setError(null)
      // A 401 from a resource call means the session changed under us; the
      // freshness window must not block the revalidation that follows.
      invalidateRefreshFreshness(dedupe.current)
    })
    const releaseRefresh = setSessionRefreshHandler(async () => {
      await identityApi.refresh()
      await refresh({ force: true })
    })
    const releaseCanonical = registerCanonicalSessionRefresh(refresh)
    return () => {
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisibility)
      releaseFailure()
      releaseRefresh()
      releaseCanonical()
    }
  }, [refresh])

  // Publish the canonical state for imperative (non-React) consumers. The
  // provider is the only writer; the snapshot never fetches on its own.
  useEffect(() => {
    publishSessionSnapshot({ data, ready })
  }, [data, ready])

  const value = useMemo<SessionContextValue>(
    () => ({ data, ready, authenticated: Boolean(data), error, refresh, logout }),
    [data, error, logout, ready, refresh]
  )
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext)
  if (!value) throw new Error('useSession must be used inside SessionProvider')
  return value
}
