import { useContext } from 'react'
import { isMockAuthEnabled } from '@/lib/core/config/env-flags'
import { identityApi } from './identity-api'
import { MOCK_IDENTITY_ME } from './mock-session'
import { SessionContext, type SessionContextValue } from './session-provider'

type SimUser = {
  id: string
  email: string
  emailVerified?: boolean
  name?: string | null
  image?: string | null
}

type SimSession = {
  user: SimUser
  session: { id: string; userId: string }
} | null

export type SessionHookResult = {
  data: SimSession
  isPending: boolean
  error: Error | null
  refetch: () => Promise<void>
}

function toSimSession(value: SessionContextValue['data']): SimSession {
  if (!value) return null
  return {
    user: {
      id: value.user.id,
      email: value.user.email ?? value.user.primaryEmail ?? '',
      emailVerified: Boolean(value.user.emailVerified),
      name: value.user.name ?? value.user.username ?? null,
      image: value.user.image ?? value.user.avatar ?? null,
    },
    session: {
      id: value.principal.subject,
      userId: value.user.id,
    },
  }
}

export function useSession(): SessionHookResult {
  const context = useContext(SessionContext)
  if (!context) throw new Error('SessionProvider is not mounted.')
  return {
    data: toSimSession(context.data),
    isPending: !context.ready,
    error: context.error ? new Error(context.error) : null,
    refetch: async () => {
      await context.refresh()
    },
  }
}

type AuthRedirectOptions = { callbackURL?: string; callbackUrl?: string }
type SocialSignInOptions = AuthRedirectOptions & {
  provider: 'github' | 'google' | 'microsoft'
}

/**
 * The identity BFF starts authentication with a browser navigation rather
 * than returning a session from JavaScript. Callers must not treat that
 * navigation as an already completed login and start a second navigation.
 */
type AuthRedirectResult = {
  data: SimSession | null
  error: null
  redirectStarted: true
}

function callbackPath(options?: AuthRedirectOptions): string {
  return options?.callbackURL ?? options?.callbackUrl ?? '/workspace/lingxi/home/'
}

export const client = {
  getSession: async (_options?: unknown) => {
    if (isMockAuthEnabled) return { data: toSimSession(MOCK_IDENTITY_ME), error: null }
    try {
      const value = await identityApi.me()
      return { data: toSimSession(value), error: null }
    } catch {
      return { data: null, error: null }
    }
  },
  signIn: {
    email: async (_credentials: Record<string, unknown>, options?: AuthRedirectOptions) => {
      if (isMockAuthEnabled) {
        window.location.assign(callbackPath(options))
        return { data: toSimSession(MOCK_IDENTITY_ME), error: null, redirectStarted: true }
      }
      window.location.assign(identityApi.authUrl('login', callbackPath(options)))
      return { data: null, error: null, redirectStarted: true } satisfies AuthRedirectResult
    },
    social: async (options: SocialSignInOptions) => {
      if (isMockAuthEnabled) {
        window.location.assign(callbackPath(options))
        return { data: toSimSession(MOCK_IDENTITY_ME), error: null, redirectStarted: true }
      }
      window.location.assign(identityApi.authUrl('login', callbackPath(options), options.provider))
      return { data: null, error: null, redirectStarted: true } satisfies AuthRedirectResult
    },
  },
  signUp: {
    email: async (_credentials: Record<string, unknown>, options?: AuthRedirectOptions) => {
      if (isMockAuthEnabled) {
        window.location.assign(callbackPath(options))
        return { data: toSimSession(MOCK_IDENTITY_ME), error: null, redirectStarted: true }
      }
      window.location.assign(identityApi.authUrl('register', callbackPath(options)))
      return { data: null, error: null, redirectStarted: true } satisfies AuthRedirectResult
    },
  },
  // These namespaces keep the direct Sim query modules type-compatible while
  // their organization/admin capabilities are migrated to Lingxi APIs.
  organization: {
    list: async (..._args: unknown[]) => ({ data: [], error: null }),
    getFullOrganization: async (..._args: unknown[]) => ({ data: null, error: null }),
    setActive: async (..._args: unknown[]) => ({ data: null, error: null }),
  },
  admin: {
    createUser: async (..._args: unknown[]) => ({
      data: null,
      error: { message: '管理员账户 API 尚未接入' },
    }),
    getUser: async (..._args: unknown[]) => ({
      data: null,
      error: { message: '管理员账户 API 尚未接入' },
    }),
    listUsers: async (..._args: unknown[]) => ({ data: { users: [], total: 0 }, error: null }),
    setRole: async (..._args: unknown[]) => ({
      data: null,
      error: { message: '管理员账户 API 尚未接入' },
    }),
    banUser: async (..._args: unknown[]) => ({
      data: null,
      error: { message: '管理员账户 API 尚未接入' },
    }),
    unbanUser: async (..._args: unknown[]) => ({
      data: null,
      error: { message: '管理员账户 API 尚未接入' },
    }),
    impersonateUser: async (..._args: unknown[]) => ({
      data: null,
      error: { message: '管理员账户 API 尚未接入' },
    }),
    stopImpersonating: async (..._args: unknown[]) => ({
      data: null,
      error: { message: '管理员账户 API 尚未接入' },
    }),
  },
  subscription: {
    list: async (..._args: unknown[]) => ({ data: [], error: null }),
  },
  useActiveOrganization: () => ({ data: null, isPending: false, error: null }),
} as any

export const useActiveOrganization = client.useActiveOrganization

export const useSubscription = () => ({
  list: undefined,
  upgrade: undefined,
  cancel: undefined,
  restore: undefined,
})

export async function signOut(): Promise<void> {
  if (!isMockAuthEnabled) await identityApi.logout()
  window.location.assign('/')
}
