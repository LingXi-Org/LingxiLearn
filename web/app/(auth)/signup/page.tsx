import { Suspense } from 'react'
import { AuthEntry } from '../components/auth-entry'

export default function SignupPage() {
  return <Suspense><AuthEntry kind='register' /></Suspense>
}
