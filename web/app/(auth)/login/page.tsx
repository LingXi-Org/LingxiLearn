import { redirect } from 'next/navigation'
import type { SearchParams } from 'nuqs/server'
import { validateCallbackUrl } from '@/lib/core/security/input-validation'

export const dynamic = 'force-dynamic'

const DEFAULT_AUTH_CALLBACK = '/workspace/lingxi/home/'

function firstString(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const params = await searchParams
  const rawCallback =
    firstString(params.redirect) ??
    firstString(params.callbackUrl) ??
    firstString(params.callbackURL)

  const nextPath =
    rawCallback && validateCallbackUrl(rawCallback) ? rawCallback : DEFAULT_AUTH_CALLBACK

  redirect(`/auth/login?next_path=${encodeURIComponent(nextPath)}`)
}
