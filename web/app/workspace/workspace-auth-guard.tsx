'use client'

import { useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { useSession } from '@/lib/auth/session-provider'

/** Enforces authentication for every workspace route, including after expiry. */
export function WorkspaceAuthGuard({ children }: { children: React.ReactNode }) {
  const { authenticated, ready } = useSession()
  const pathname = usePathname()
  const router = useRouter()

  useEffect(() => {
    if (!ready || authenticated) return
    const callbackUrl = `${pathname || '/workspace'}${window.location.search}`
    router.replace(`/login?callbackUrl=${encodeURIComponent(callbackUrl)}`)
  }, [authenticated, pathname, ready, router])

  if (!ready || !authenticated) return null
  return children
}
