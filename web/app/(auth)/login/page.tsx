import { Suspense } from 'react'
import type { Metadata } from 'next'
import { AuthEntry } from '@/app/(auth)/components/auth-entry'

export const metadata: Metadata = {
  title: 'Log In',
}

export const dynamic = 'force-dynamic'

export default function LoginPage() {
  return (
    <Suspense>
      <AuthEntry kind='login' />
    </Suspense>
  )
}
