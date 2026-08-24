import { useContext } from 'react'
import { isMockAuthEnabled } from '@/lib/core/config/env-flags'
import { clearUserData } from '@/stores'
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
      // An explicit refetch is a "the session may have changed" signal, so it
      // bypasses the provider's freshness window.
      await context.refresh({ force: true })
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
export async function startLogin(options: AuthRedirectOptions = {}): Promise<AuthRedirectResult> {
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
export async function startSocialLogin(options: SocialAuthOptions): Promise<AuthRedirectResult> {
  const nextPath = callbackPath(options)
  if (isMockAuthEnabled) {
    window.location.assign(nextPath)
    return { data: toSimSession(MOCK_IDENTITY_ME), error: null, redirectStarted: true }
  }
  window.location.assign(identityApi.authUrl('login', nextPath, options.provider))
  return { data: null, error: null, redirectStarted: true }
}

export const client = {
  // Verb-first navigation methods only: the LingxiIdentity BFF owns
  // credentials, tokens and session state. There is intentionally no
  // `signIn.email`/`signUp.email`, no organization/subscription namespace,
  // and no `getSession`: the SessionProvider is the single canonical owner of
  // the browser session — React code reads `useSession`, imperative code
  // reads `getSessionSnapshot` from `./session-snapshot`. Neither path may
  // issue its own `/api/v1/me` request.
  startLogin,
  startRegistration,
  startSocialLogin,
}

export async function signOut(): Promise<void> {
  if (!isMockAuthEnabled) await identityApi.logout()
  await clearUserData()
  window.location.assign('/')
}
