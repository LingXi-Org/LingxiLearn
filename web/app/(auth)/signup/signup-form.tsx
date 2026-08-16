'use client'

import { AuthEntry } from '@/app/(auth)/components/auth-entry'

/**
 * Compatibility wrapper for the historical route component. Registration is
 * completed by LingxiIdentity's Logto Experience, so this page must not ask
 * for a name, password, captcha, or maintain a second validation policy.
 */
export default function SignupPage({}: {
  githubAvailable: boolean
  googleAvailable: boolean
  microsoftAvailable: boolean
  isProduction: boolean
  emailSignupEnabled: boolean
  emailVerificationEnabled: boolean
}) {
  return <AuthEntry kind='register' />
}
