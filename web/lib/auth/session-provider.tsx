'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { isMockAuthEnabled } from '@/lib/core/config/env-flags'
import { setAuthenticationFailureHandler, setSessionRefreshHandler } from '@/lib/lingxi/api'
import { type IdentityMe, identityApi } from './identity-api'
import { MOCK_IDENTITY_ME } from './mock-session'

export interface SessionContextValue {
  data: IdentityMe | null
  ready: boolean
  authenticated: boolean
  error: string | null
  refresh: () => Promise<IdentityMe | null>
  logout: () => Promise<void>
}

export const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<IdentityMe | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const refreshInFlight = useRef<Promise<IdentityMe | null> | null>(null)

  const refresh = useCallback(async () => {
    if (refreshInFlight.current) return refreshInFlight.current

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

    refreshInFlight.current = request
    void request.finally(() => {
      if (refreshInFlight.current === request) refreshInFlight.current = null
    })
    return request
  }, [])

  const logout = useCallback(async () => {
    if (!isMockAuthEnabled) await identityApi.logout()
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
    })
    const releaseRefresh = setSessionRefreshHandler(async () => {
      await identityApi.refresh()
      await refresh()
    })
    return () => {
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisibility)
      releaseFailure()
      releaseRefresh()
    }
  }, [refresh])

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
