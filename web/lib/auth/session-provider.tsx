'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { setAuthenticationFailureHandler, setSessionRefreshHandler } from '@/lib/lingxi/api'
import { identityApi, type IdentityMe } from './identity-api'

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

  const refresh = useCallback(async () => {
    try {
      const next = await identityApi.me()
      setData(next)
      setError(null)
      return next
    } catch (cause) {
      setData(null)
      if (
        cause instanceof Error &&
        !(
          cause.message.includes('unauthorized') ||
          (cause as { status?: number }).status === 401 ||
          (cause as { status?: number }).status === 403
        )
      ) {
        setError(cause.message)
      } else {
        setError(null)
      }
      return null
    } finally {
      setReady(true)
    }
  }, [])

  const logout = useCallback(async () => {
    await identityApi.logout()
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
    const releaseFailure = setAuthenticationFailureHandler(() => setData(null))
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
