import { Suspense } from 'react'
import { AuthEntry } from '../components/auth-entry'

export default function ResetPasswordPage() {
  return <Suspense><AuthEntry kind='forgot-password' /></Suspense>
}
