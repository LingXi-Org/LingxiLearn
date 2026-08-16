import { Suspense } from 'react'
import type { Metadata } from 'next'
import { isRegistrationDisabled } from '@/lib/core/config/env-flags'
import LoginLoading from '@/app/(auth)/login/loading'
import { AuthEntry } from '@/app/(auth)/components/auth-entry'

export const metadata: Metadata = {
  title: 'Log In',
}

export const dynamic = 'force-dynamic'

export default async function LoginPage() {
  return (
    <Suspense fallback={<LoginLoading />}>
      <AuthEntry kind='login' registrationDisabled={isRegistrationDisabled} />
    </Suspense>
  )
}
