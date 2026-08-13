'use client'

export interface IdentityPrincipal {
  subject: string
  tenant_id?: string | null
  roles: string[]
  permissions: string[]
  issuer?: string | null
  audience: string[]
}

export interface IdentityUser {
  id: string
  username?: string | null
  primaryEmail?: string | null
  primaryPhone?: string | null
  name?: string | null
  avatar?: string | null
  /** Compatibility aliases consumed by the shared account/identity UI. */
  email?: string | null
  image?: string | null
  emailVerified?: boolean | null
  isSuspended?: boolean
  hasPassword?: boolean | null
  customData?: Record<string, unknown>
  profile?: Record<string, unknown>
  createdAt?: string | null
  updatedAt?: string | null
}

export interface IdentitySession {
  id: string
  userId?: string | null
  applicationId?: string | null
  applicationName?: string | null
  createdAt?: string | null
  lastUsedAt?: string | null
  isCurrent: boolean
}

export interface IdentityMe {
  principal: IdentityPrincipal
  user: IdentityUser
}

export interface VerificationRecord {
  verificationRecordId: string
  expiresAt?: string | null
}

export class IdentityApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string
  ) {
    super(message)
  }
}

let csrfToken: string | null = null
let csrfPromise: Promise<string> | null = null
let refreshPromise: Promise<{ ok: boolean; expiresAt?: string | null }> | null = null

const configuredBase = process.env.NEXT_PUBLIC_API_BASE?.trim().replace(/\/$/, '')
const defaultBase = process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : ''

function identityUrl(path: string): string {
  const base = configuredBase || defaultBase
  return base ? `${base}${path}` : path
}

function safeNextPath(value: string): string {
  if (!value.startsWith('/') || value.startsWith('//') || value.includes('\\')) return '/'
  return value
}

async function parseError(response: Response): Promise<IdentityApiError> {
  let code = `identity.http_${response.status}`
  let message = response.statusText || '身份服务请求失败'
  try {
    const body = (await response.json()) as {
      code?: string
      detail?: string | { code?: string }
      message?: string
    }
    if (typeof body.code === 'string') code = body.code
    if (typeof body.detail === 'string') message = body.detail
    if (body.detail && typeof body.detail === 'object' && typeof body.detail.code === 'string') {
      code = body.detail.code
      message = body.detail.code
    }
    if (typeof body.message === 'string') message = body.message
  } catch {
    // Keep the HTTP status text when the upstream did not return JSON.
  }
  return new IdentityApiError(response.status, code, message)
}

function normalizeIdentityMe(value: IdentityMe): IdentityMe {
  const user = value.user
  return {
    ...value,
    user: {
      ...user,
      // The BFF deliberately preserves Logto's Account API field names. Keep
      // the Sim-facing aliases in one place so every native surface sees the
      // same user shape.
      email: user.email ?? user.primaryEmail ?? null,
      image: user.image ?? user.avatar ?? null,
      emailVerified: user.emailVerified ?? null,
    },
  }
}

async function getCsrfToken(force = false): Promise<string> {
  if (csrfToken && !force) return csrfToken
  if (!csrfPromise || force) {
    csrfPromise = fetch(identityUrl('/auth/csrf'), {
      credentials: 'include',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    })
      .then(async (response) => {
        if (!response.ok) throw await parseError(response)
        const body = (await response.json()) as { csrfToken: string }
        csrfToken = body.csrfToken
        return body.csrfToken
      })
      .finally(() => {
        csrfPromise = null
      })
  }
  return csrfPromise
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || 'GET').toUpperCase()
  const mutating = !['GET', 'HEAD', 'OPTIONS'].includes(method)
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (mutating) headers.set('X-CSRF-Token', await getCsrfToken())

  const url = identityUrl(path)
  let response = await fetch(url, { ...init, method, headers, credentials: 'include' })
  if (response.status === 403 && mutating) {
    const error = await parseError(response.clone())
    if (error.code === 'identity.csrf_failed') {
      headers.set('X-CSRF-Token', await getCsrfToken(true))
      response = await fetch(url, { ...init, method, headers, credentials: 'include' })
    }
  }
  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const identityApi = {
  authUrl(kind: 'login' | 'register' | 'forgot-password', nextPath = '/workspace/lingxi/home/') {
    const params = new URLSearchParams({ next_path: safeNextPath(nextPath) })
    return `${identityUrl(`/auth/${kind}`)}?${params}`
  },

  me: async () => normalizeIdentityMe(await request<IdentityMe>('/api/v1/me')),

  refresh: () => {
    if (!refreshPromise) {
      refreshPromise = request<{ ok: boolean; expiresAt?: string | null }>('/auth/refresh', {
        method: 'POST',
      }).finally(() => {
        refreshPromise = null
      })
    }
    return refreshPromise
  },

  async logout(): Promise<void> {
    try {
      await request<void>('/auth/logout', { method: 'POST' })
    } catch (cause) {
      if (!(cause instanceof IdentityApiError) || ![401, 403, 404].includes(cause.status)) {
        throw cause
      }
    } finally {
      csrfToken = null
    }
  },

  updateProfile: (changes: {
    name?: string
    username?: string
    avatar?: string
    customData?: Record<string, unknown>
    profile?: Record<string, unknown>
    verificationId?: string
  }) =>
    request<IdentityUser>('/api/v1/me/profile', { method: 'PATCH', body: JSON.stringify(changes) }),

  verifyPassword: (password: string) =>
    request<VerificationRecord>('/api/v1/me/verifications/password', {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),

  sendEmailVerification: (email: string) =>
    request<VerificationRecord>('/api/v1/me/verifications/email', {
      method: 'POST',
      body: JSON.stringify({ identifier: email, identifierType: 'email' }),
    }),

  verifyEmailCode: (email: string, verificationId: string, code: string) =>
    request<VerificationRecord>('/api/v1/me/verifications/email/verify', {
      method: 'POST',
      body: JSON.stringify({
        identifier: email,
        identifierType: 'email',
        verificationId,
        code,
      }),
    }),

  updateEmail: (email: string, verificationId: string, newIdentifierVerificationId: string) =>
    request<IdentityUser>('/api/v1/me/email', {
      method: 'PATCH',
      body: JSON.stringify({ email, verificationId, newIdentifierVerificationId }),
    }),

  updatePassword: (password: string, verificationId: string) =>
    request<void>('/api/v1/me/password', {
      method: 'POST',
      body: JSON.stringify({ password, verificationId }),
    }),

  sessions: (verificationId?: string) =>
    request<IdentitySession[]>('/api/v1/me/sessions', {
      headers: verificationId ? { 'X-Logto-Verification-Id': verificationId } : undefined,
    }),

  revokeSession: (sessionId: string) =>
    request<void>(`/api/v1/me/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' }),

  async deactivate(): Promise<void> {
    await request<void>('/api/v1/me/deactivate', { method: 'POST' })
    csrfToken = null
  },
}
