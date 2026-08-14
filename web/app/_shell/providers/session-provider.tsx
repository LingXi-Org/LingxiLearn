'use client'

import { createContext, useEffect, useMemo, useState } from 'react'
import { useLingxiIdentity } from '@/lib/lingxi/lingxi-identity-provider'

type LingxiAppSession = {
  user: {
    id: string
    email: string
    emailVerified?: boolean
    name?: string | null
    image?: string | null
  } | null
  session?: {
    id?: string
    userId?: string
  }
} | null

export type SessionHookResult = {
  data: LingxiAppSession
  isPending: boolean
  error: Error | null
  refetch: () => Promise<void>
}

export const SessionContext = createContext<SessionHookResult | null>(null)

/**
 * LingxiGraph owns authentication and authorization. Sim's Better Auth session
 * provider is retained under sim-backend-unwired; the browser shell receives a
 * stable local viewer so it never calls a non-existent Better Auth endpoint.
 */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const identity = useLingxiIdentity()
  const [user, setUser] = useState(identity.user)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    setUser(identity.user)
    setError(identity.error ? new Error(identity.error) : null)
  }, [identity.error, identity.user])

  const value = useMemo<SessionHookResult>(
    () => ({
      data: user
        ? {
            user: {
              id: user.id,
              email: user.email ?? '',
              name: user.name ?? null,
              image: user.picture ?? null,
              emailVerified: user.emailVerified,
            },
            session: { id: 'lingxi-browser-session', userId: user.id },
          }
        : { user: null },
      isPending: !identity.ready,
      error,
      refetch: async () => {
        if (!identity.client) return
        const currentUser = await identity.client.user()
        setUser(currentUser)
      },
    }),
    [error, identity.client, identity.ready, user]
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
