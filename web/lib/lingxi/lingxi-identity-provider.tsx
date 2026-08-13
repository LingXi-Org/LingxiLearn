'use client'

import { useMemo } from 'react'
import { identityApi } from '@/lib/auth/identity-api'
import { SessionProvider, useSession } from '@/lib/auth/session-provider'

export function LingxiIdentityProvider({ children }: { children: React.ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>
}

export function useLingxiIdentity() {
  const session = useSession()
  const client = useMemo(
    () => ({
      login: async () => window.location.assign(identityApi.authUrl('login')),
      register: async () => window.location.assign(identityApi.authUrl('register')),
      forgotPassword: async () => window.location.assign(identityApi.authUrl('forgot-password')),
      logout: session.logout,
    }),
    [session.logout]
  )
  const user = session.data?.user
    ? {
        id: session.data.user.id,
        email: session.data.user.email || undefined,
        name: session.data.user.name ?? undefined,
        picture: session.data.user.image ?? undefined,
        emailVerified: Boolean(session.data.user.emailVerified),
      }
    : null
  return {
    client,
    configured: true,
    ready: session.ready,
    authenticated: session.authenticated,
    user,
    error: session.error,
  }
}
