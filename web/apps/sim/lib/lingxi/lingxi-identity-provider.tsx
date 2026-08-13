'use client'

import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { setAuthenticationFailureHandler } from '@/lib/lingxi/api'
import {
  createLingxiIdentityClient,
  type LingxiIdentityClient,
} from '@/lib/lingxi/lingxi-identity'

interface LingxiIdentityContextValue {
  client: LingxiIdentityClient | null
  configured: boolean
  ready: boolean
  authenticated: boolean
  user: Awaited<ReturnType<LingxiIdentityClient['user']>>
  error: string | null
}

const LingxiIdentityContext = createContext<LingxiIdentityContextValue | null>(null)

export function LingxiIdentityProvider({ children }: { children: React.ReactNode }) {
  const [client, setClient] = useState<LingxiIdentityClient | null>(null)
  const [configured, setConfigured] = useState(true)
  const [ready, setReady] = useState(false)
  const [authenticated, setAuthenticated] = useState(false)
  const [user, setUser] = useState<Awaited<ReturnType<LingxiIdentityClient['user']>>>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    try {
      const identity = createLingxiIdentityClient()
      setClient(identity)
      // The API client is intentionally independent from the identity UI, so
      // the provider must explicitly bridge the current OIDC token into it.
      // Without this mount, every skills/task request is sent anonymously even
      // after a successful browser login.
      identity.mountTokenProvider()
      const onLogout = () => {
        void identity.logout()
      }
      window.addEventListener('lingxi:logout', onLogout)
      const releaseFailureHandler = setAuthenticationFailureHandler(() => {
        setAuthenticated(false)
        setUser(null)
      })
      const isCallback =
        window.location.pathname === '/auth/callback' ||
        window.location.pathname === '/auth/callback/'
      if (!isCallback) {
        setReady(true)
        void identity
          .user()
          .then((currentUser) => {
            setUser(currentUser)
            setAuthenticated(Boolean(currentUser))
          })
          .catch((cause) => setError(cause instanceof Error ? cause.message : String(cause)))
        return () => {
          window.removeEventListener('lingxi:logout', onLogout)
          releaseFailureHandler()
          identity.dispose()
        }
      }
      void identity
        .handleCallback()
        .then(async (handled) => {
          const currentUser = handled ? await identity.user() : null
          setUser(currentUser)
          setAuthenticated(Boolean(currentUser))
          if (handled) window.history.replaceState({}, document.title, window.location.pathname)
        })
        .catch((cause) => setError(cause instanceof Error ? cause.message : String(cause)))
        .finally(() => setReady(true))
      return () => {
        window.removeEventListener('lingxi:logout', onLogout)
        releaseFailureHandler()
        identity.dispose()
      }
    } catch {
      setConfigured(false)
      setReady(true)
    }
  }, [])

  const value = useMemo(
    () => ({ client, configured, ready, authenticated, user, error }),
    [authenticated, client, configured, error, ready, user]
  )
  return <LingxiIdentityContext.Provider value={value}>{children}</LingxiIdentityContext.Provider>
}

export function useLingxiIdentity() {
  const value = useContext(LingxiIdentityContext)
  if (!value) throw new Error('useLingxiIdentity must be used inside LingxiIdentityProvider')
  return value
}
