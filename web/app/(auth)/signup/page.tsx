import { Suspense } from 'react'
import type { Metadata } from 'next'
import type { SearchParams } from 'nuqs/server'
import { isRegistrationDisabled } from '@/lib/core/config/env-flags'
import { validateCallbackUrl } from '@/lib/core/security/input-validation'
import { resolveAuthRedirect } from '@/app/(auth)/auth-redirect'
import SignupLoading from '@/app/(auth)/signup/loading'
import { RegistrationDisabled } from '@/app/(auth)/signup/registration-disabled'
import { signupSearchParamsCache } from '@/app/(auth)/signup/search-params'
import { AuthEntry } from '@/app/(auth)/components/auth-entry'

export const metadata: Metadata = { title: '注册' }
export const dynamic = 'force-dynamic'

export default async function SignupPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  if (isRegistrationDisabled) {
    const { redirect, callbackUrl, inviteFlow } = await signupSearchParamsCache.parse(searchParams)
    const { rawCallbackUrl, isInviteFlow } = resolveAuthRedirect({
      redirect,
      callbackUrl,
      inviteFlow,
    })
    return (
      <RegistrationDisabled
        callbackUrl={validateCallbackUrl(rawCallbackUrl) ? rawCallbackUrl : null}
        isInviteFlow={isInviteFlow}
      />
    )
  }

  return (
    <Suspense fallback={<SignupLoading />}>
      <AuthEntry kind='register' />
    </Suspense>
  )
}
