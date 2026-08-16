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

export type AuthRedirectOptions = { callbackURL?: unknown; callbackUrl?: unknown }
export type SocialAuthOptions = AuthRedirectOptions & {
  provider: 'github' | 'google' | 'microsoft'
}

/**
 * The identity BFF starts authentication with a browser navigation rather
 * than returning a session from JavaScript. Callers must not treat that
 * navigation as an already completed login and start a second navigation.
 */
export type AuthRedirectResult = {
  data: SimSession | null
  error: null
  redirectStarted: true
}

const DEFAULT_AUTH_CALLBACK = '/workspace/lingxi/home/'

function isSafeCallbackPath(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.startsWith('/') &&
    !value.startsWith('//') &&
    !value.includes('\\')
  )
}

function callbackPath(...sources: Array<AuthRedirectOptions | undefined>): string {
  for (const source of sources) {
    const value = source?.callbackURL ?? source?.callbackUrl
    if (isSafeCallbackPath(value)) return value
  }
  return DEFAULT_AUTH_CALLBACK
}

/**
 * Start the browser-owned LingxiIdentity Experience login flow.
 *
 * Authentication is deliberately a top-level navigation. LingxiLearn never
 * posts credentials or receives an access/refresh token in JavaScript; the
 * BFF owns OIDC state, PKCE, the callback exchange, and the HttpOnly session.
 */
export async function startLogin(
  options: AuthRedirectOptions = {}
): Promise<AuthRedirectResult> {
  const nextPath = callbackPath(options)
  if (isMockAuthEnabled) {
    window.location.assign(nextPath)
    return { data: toSimSession(MOCK_IDENTITY_ME), error: null, redirectStarted: true }
  }
  window.location.assign(identityApi.authUrl('login', nextPath))
  return { data: null, error: null, redirectStarted: true }
}

/** Start the browser-owned LingxiIdentity Experience registration flow. */
export async function startRegistration(
  options: AuthRedirectOptions = {}
): Promise<AuthRedirectResult> {
  const nextPath = callbackPath(options)
  if (isMockAuthEnabled) {
    window.location.assign(nextPath)
    return { data: toSimSession(MOCK_IDENTITY_ME), error: null, redirectStarted: true }
  }
  window.location.assign(identityApi.authUrl('register', nextPath))
  return { data: null, error: null, redirectStarted: true }
}

/** Start a social provider through the same BFF + Logto Experience flow. */
export async function startSocialLogin(
  options: SocialAuthOptions
): Promise<AuthRedirectResult> {
  const nextPath = callbackPath(options)
  if (isMockAuthEnabled) {
    window.location.assign(nextPath)
    return { data: toSimSession(MOCK_IDENTITY_ME), error: null, redirectStarted: true }
  }
  window.location.assign(identityApi.authUrl('login', nextPath, options.provider))
  return { data: null, error: null, redirectStarted: true }
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
  // Keep the compatibility client object for the many non-auth query modules,
  // but expose only verb-first navigation methods. There is intentionally no
  // `signIn.email`/`signUp.email`: LingxiLearn does not own credentials.
  startLogin,
  startRegistration,
  startSocialLogin,
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
