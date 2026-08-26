/**
 * Unified HTTP transport for the Lingxi frontend.
 *
 * Single owner of:
 * - API_BASE resolution
 * - session cookie / 401 / refresh / identity-failure handling
 * - credentials, error normalisation
 *
 * Issue #40: merge the duplicate transport responsibilities that were split
 * between ``lib/lingxi/api.ts`` and ``lib/api/client/request.ts``.
 */

import { API_BASE } from '@/lib/api/config'

// ---------------------------------------------------------------------------
// Auth / session failure handlers
// ---------------------------------------------------------------------------

export type AccessTokenProvider = () =>
  | string
  | null
  | undefined
  | Promise<string | null | undefined>

let authenticationFailureHandler: (() => void) | null = null
let sessionRefreshHandler: (() => void | Promise<void>) | null = null
let accessTokenProvider: AccessTokenProvider | null = null

export function setAccessTokenProvider(provider: AccessTokenProvider | null): () => void {
  const previous = accessTokenProvider
  accessTokenProvider = provider
  return () => {
    accessTokenProvider = previous
  }
}

export function setAuthenticationFailureHandler(handler: (() => void) | null): () => void {
  const previous = authenticationFailureHandler
  authenticationFailureHandler = handler
  return () => {
    authenticationFailureHandler = previous
  }
}

export function setSessionRefreshHandler(handler: (() => void | Promise<void>) | null): () => void {
  const previous = sessionRefreshHandler
  sessionRefreshHandler = handler
  return () => {
    sessionRefreshHandler = previous
  }
}

/** @deprecated Use setSessionRefreshHandler instead. */
export function setAccessTokenRefreshHandler(
  handler: (() => void | Promise<void>) | null
): () => void {
  return setSessionRefreshHandler(handler)
}

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string
  ) {
    super(detail || `HTTP ${status}`)
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function apiUrl(path: string): string {
  return `${API_BASE}/api${path}`
}

// ---------------------------------------------------------------------------
// Authorized fetch (handles 401 retry + token injection)
// ---------------------------------------------------------------------------

export async function authorizedFetch(url: string, init?: RequestInit): Promise<Response> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const headers = new Headers(init?.headers)
    if (accessTokenProvider && !headers.has('Authorization')) {
      const token = await accessTokenProvider()
      if (token) headers.set('Authorization', `Bearer ${token}`)
    }
    const response = await fetch(url, { ...init, headers, credentials: 'include' })
    if (response.status !== 401 || attempt > 0 || !sessionRefreshHandler) return response
    try {
      await sessionRefreshHandler()
    } catch {
      authenticationFailureHandler?.()
      return response
    }
  }
  throw new Error('unreachable')
}

// ---------------------------------------------------------------------------
// Typed JSON request (legacy path-based — domain clients call this)
// ---------------------------------------------------------------------------

/**
 * Generic JSON request with auth retry. Domain clients wrap this with
 * their own typed signatures. Error handling is unified here: one owner
 * for 401 → auth failure, error detail extraction, and ApiError throw.
 */
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  const response = await authorizedFetch(apiUrl(path), { ...init, headers })
  if (!response.ok) {
    if (response.status === 401) authenticationFailureHandler?.()
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep the status text */
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

/**
 * Fetch a binary resource (blob) through the authorized transport.
 * Artifact URL builders already include the ``/api`` prefix.
 */
export async function fetchArtifactBlob(url: string): Promise<Blob> {
  const response = await authorizedFetch(url)
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText)
  }
  return response.blob()
}
