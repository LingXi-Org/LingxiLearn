import type { AnyApiRouteContract, ContractJsonResponse } from '@/lib/api/contracts'
import { API_BASE } from '@/lib/lingxi/api'

type MaybeField<Key extends string, Value> = [Value] extends [undefined]
  ? { [K in Key]?: never }
  : { [K in Key]: Value }

/**
 * Shared resource contracts remain the source of runtime schemas. The client
 * accepts the superset of request shapes used by reused hooks (some contracts
 * encode an optional params/query slot).
 */
export type ApiClientRequest<_C extends AnyApiRouteContract> = Record<string, any> & {
  signal?: AbortSignal
}

export interface ApiRawRequestOptions {
  cache?: RequestCache
  headers?: Record<string, string>
}

function routePath(contract: AnyApiRouteContract, input: object): string {
  const params =
    'params' in input && input.params && typeof input.params === 'object'
      ? (input.params as Record<string, unknown>)
      : {}
  return contract.path.replace(/\[\[?(?:\.\.\.)?([^\][]+)\]\]?/g, (_match, key: string) =>
    encodeURIComponent(String(params[key] ?? key))
  )
}

/**
 * Reused browser components keep their strongly typed resource contracts.
 * Unsupported contract calls are disabled at the Lingxi hook boundary; this
 * client remains a single transport to the canonical FastAPI service.
 */
export async function requestJson<C extends AnyApiRouteContract>(
  contract: C,
  input: ApiClientRequest<C> = {}
): Promise<any> {
  const raw = await requestRaw(contract, input)
  const payload = (await raw.json()) as ContractJsonResponse<C>
  return payload
}

export async function requestRaw<C extends AnyApiRouteContract>(
  contract: C,
  input: ApiClientRequest<C> = {},
  options: ApiRawRequestOptions = {}
): Promise<Response> {
  const params =
    'params' in input && input.params && typeof input.params === 'object'
      ? (input.params as Record<string, unknown>)
      : {}
  const query =
    'query' in input && input.query && typeof input.query === 'object'
      ? (input.query as Record<string, unknown>)
      : {}
  const path = routePath(contract, input)
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, String(item))
    } else if (typeof value === 'object') {
      search.set(key, JSON.stringify(value))
    } else {
      search.set(key, String(value))
    }
  }
  const url = `${API_BASE}${path}${search.toString() ? `?${search.toString()}` : ''}`
  const headers = new Headers(options.headers)
  if ('headers' in input && input.headers && typeof input.headers === 'object') {
    for (const [key, value] of Object.entries(input.headers as Record<string, unknown>)) {
      if (value != null) headers.set(key, String(value))
    }
  }
  let body: BodyInit | undefined
  if ('body' in input && input.body !== undefined) {
    if (
      input.body instanceof FormData ||
      input.body instanceof Blob ||
      typeof input.body === 'string'
    ) {
      body = input.body as BodyInit
    } else {
      headers.set('Content-Type', 'application/json')
      body = JSON.stringify(input.body)
    }
  }
  const response = await fetch(url, {
    method: contract.method,
    headers,
    body,
    credentials: 'include',
    signal: input.signal,
    cache: options.cache,
  })
  if (!response.ok) {
    let detail = response.statusText || `Request failed (${response.status})`
    try {
      const data = (await response.clone().json()) as {
        error?: string
        detail?: unknown
        message?: string
      }
      detail =
        data.error || data.message || (typeof data.detail === 'string' ? data.detail : detail)
    } catch {
      // Preserve status text for non-JSON errors.
    }
    const error = new Error(detail) as Error & { status?: number; code?: string }
    error.status = response.status
    error.code = detail
    throw error
  }
  return response
}
