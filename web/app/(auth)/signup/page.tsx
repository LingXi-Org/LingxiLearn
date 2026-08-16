import { redirect } from 'next/navigation'
import type { SearchParams } from 'nuqs/server'
import { isRegistrationDisabled } from '@/lib/core/config/env-flags'
import { validateCallbackUrl } from '@/lib/core/security/input-validation'
import { RegistrationDisabled } from '@/app/(auth)/signup/registration-disabled'

export const dynamic = 'force-dynamic'

const DEFAULT_AUTH_CALLBACK = '/workspace/lingxi/home/'

function firstString(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default async function SignupPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const params = await searchParams
  const rawCallback =
    firstString(params.redirect) ??
    firstString(params.callbackUrl) ??
    firstString(params.callbackURL)
  const validCallback = rawCallback && validateCallbackUrl(rawCallback) ? rawCallback : null
  const isInviteFlow =
    firstString(params.invite_flow) === 'true' || Boolean(validCallback?.startsWith('/invite/'))

  if (isRegistrationDisabled) {
    return <RegistrationDisabled callbackUrl={validCallback} isInviteFlow={isInviteFlow} />
  }

  const nextPath = validCallback ?? DEFAULT_AUTH_CALLBACK
  redirect(`/auth/register?next_path=${encodeURIComponent(nextPath)}`)
}
