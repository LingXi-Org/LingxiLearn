import { Suspense } from 'react'
import type { Metadata } from 'next'
import { redirect } from 'next/navigation'
import { isRegistrationDisabled, isSsoEnabled } from '@/lib/core/config/env-flags'
import SSOLoading from '@/app/(auth)/sso/loading'
import { SSOForm } from '@/app/(auth)/sso/sso-form'

export const metadata: Metadata = { title: '单点登录' }
export const dynamic = 'force-dynamic'

export default function SSOPage() {
  if (!isSsoEnabled) redirect('/login')
  return (
    <Suspense fallback={<SSOLoading />}>
      <SSOForm registrationDisabled={isRegistrationDisabled} />
    </Suspense>
  )
}
