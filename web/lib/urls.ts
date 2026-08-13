/** URL helpers shared by the public LingxiLearn pages. */

const DEFAULT_SITE_URL = 'https://lingxilearn.cn'

export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.trim() ||
  (process.env.NODE_ENV === 'development' ? 'http://localhost:3000' : DEFAULT_SITE_URL)

export const CANONICAL_SITE_HOST = new URL(DEFAULT_SITE_URL).host

function normalizeBaseUrl(url: string): string {
  return /^https?:\/\//i.test(url)
    ? url.replace(/\/$/, '')
    : `${process.env.NODE_ENV === 'development' ? 'http' : 'https'}://${url}`
}

export function getBaseUrl(): string {
  return normalizeBaseUrl(process.env.NEXT_PUBLIC_APP_URL?.trim() || SITE_URL)
}

export function getInternalApiBaseUrl(): string {
  return normalizeBaseUrl(process.env.INTERNAL_API_BASE_URL?.trim() || getBaseUrl())
}

export function ensureAbsoluteUrl(pathOrUrl: string): string {
  if (!pathOrUrl) throw new Error('URL is required')
  return pathOrUrl.startsWith('/') ? `${getBaseUrl()}${pathOrUrl}` : pathOrUrl
}

export function getBaseDomain(): string {
  try {
    return new URL(getBaseUrl()).host
  } catch {
    return 'localhost:3000'
  }
}

export function isNonCanonicalSimHost(_host: string): boolean {
  return false
}

export function getEmailDomain(): string {
  return getBaseDomain().replace(/^www\./, '')
}

export function parseOriginList(
  raw: string | undefined | null,
  onInvalid?: (value: string) => void
): string[] {
  if (!raw) return []
  const origins = new Set<string>()
  for (const value of raw.split(',')) {
    const candidate = value.trim()
    if (!candidate) continue
    try {
      origins.add(new URL(candidate).origin)
    } catch {
      onInvalid?.(candidate)
    }
  }
  return [...origins]
}

export function isLocalhostUrl(url: string): boolean {
  try {
    return ['localhost', '127.0.0.1', '::1'].includes(new URL(url).hostname)
  } catch {
    return false
  }
}

export function getBrowserOrigin(): string | null {
  return typeof window === 'undefined' ? null : window.location.origin
}

export function isSafeHttpUrl(url: string): boolean {
  try {
    const parsed = new URL(url, getBrowserOrigin() ?? undefined)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}
