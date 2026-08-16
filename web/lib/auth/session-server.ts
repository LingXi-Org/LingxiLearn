import { headers } from 'next/headers'
import { getInternalApiBaseUrl } from '@/lib/core/utils/urls'
import type { IdentityMe } from './identity-api'

function sessionUrl(): string {
  // NEXT_PUBLIC_API_BASE must remain empty in production. Server-side loaders
  // use the private/internal origin while browser requests always use the
  // same-origin rewrite in identity-api.ts.
  return `${getInternalApiBaseUrl()}/api/v1/me`
}

/**
 * Reads the LingxiIdentity BFF session for a Server Component or server-side
 * data loader. An anonymous visitor is a valid state: the BFF's 401 means
 * there is no session and must not make a public page fail to render.
 */
export async function getSession(): Promise<IdentityMe | null> {
  const requestHeaders = await headers()
  const cookie = requestHeaders.get('cookie')
  const response = await fetch(sessionUrl(), {
    headers: cookie ? { cookie, Accept: 'application/json' } : { Accept: 'application/json' },
    credentials: 'include',
    cache: 'no-store',
  })

  if (response.status === 401) return null

  if (!response.ok) {
    throw new Error(`Failed to load session (${response.status})`)
  }

  return (await response.json()) as IdentityMe
}
