'use client'

import { AuthEntry } from '@/app/(auth)/components/auth-entry'

/**
 * Compatibility wrapper for routes/imports that still call this component.
 * Login is an Identity Experience handoff; LingxiLearn intentionally renders
 * no credential fields, password policy, or local submit/error state here.
 */
export default function LoginPage({
  registrationDisabled,
}: {
  githubAvailable: boolean
  googleAvailable: boolean
  microsoftAvailable: boolean
  isProduction: boolean
  registrationDisabled: boolean
}) {
  return <AuthEntry kind='login' registrationDisabled={registrationDisabled} />
}
