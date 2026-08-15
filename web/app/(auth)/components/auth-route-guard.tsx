'use client'

import { useEffect } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { useSession } from '@/lib/auth/session-provider'

function safeDestination(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) {
    return '/workspace/lingxi/home/'
  }
  const pathname = value.split('?')[0]
  const isAuthEntry = ['/login', '/signup', '/sso', '/verify', '/reset-password'].some(
    (entry) => pathname === entry || pathname.startsWith(`${entry}/`)
  )
  if (isAuthEntry) return '/workspace/lingxi/home/'
  return value
}

/** Auth pages remain public, but an active session must never be asked to log in again. */
export function AuthRouteGuard({ children }: { children: React.ReactNode }) {
  const { authenticated, ready } = useSession()
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  useEffect(() => {
    if (!ready || !authenticated) return
    router.replace(safeDestination(searchParams.get('callbackUrl') ?? searchParams.get('callbackURL')))
  }, [authenticated, pathname, ready, router, searchParams])

  if (ready && authenticated) return null
  return children
}
