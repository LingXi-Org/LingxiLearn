import type { Metadata } from 'next'
import type { SearchParams } from 'nuqs/server'
import {
  isEmailSignupDisabled,
  isMockAuthEnabled,
  isProd,
  isRegistrationDisabled,
} from '@/lib/core/config/env-flags'
import { validateCallbackUrl } from '@/lib/core/security/input-validation'
import { resolveAuthRedirect } from '@/app/(auth)/auth-redirect'
import { getOAuthProviderStatus } from '@/app/(auth)/components/oauth-provider-checker'
import { RegistrationDisabled } from '@/app/(auth)/signup/registration-disabled'
import { signupSearchParamsCache } from '@/app/(auth)/signup/search-params'
import SignupForm from '@/app/(auth)/signup/signup-form'

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

  const { githubAvailable, googleAvailable, microsoftAvailable, isProduction } =
    await getOAuthProviderStatus()
  const emailVerificationEnabled = isMockAuthEnabled
    ? false
    : (await import('@/lib/messaging/email/verification')).isEmailVerificationEffectivelyEnabled()

  return (
    <SignupForm
      githubAvailable={githubAvailable}
      googleAvailable={googleAvailable}
      microsoftAvailable={microsoftAvailable}
      isProduction={isProduction}
      emailSignupEnabled={!isEmailSignupDisabled}
      emailVerificationEnabled={isProd ? emailVerificationEnabled : false}
    />
  )
}
