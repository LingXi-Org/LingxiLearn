import { Suspense } from 'react'
import { AuthEntry } from '../components/auth-entry'

export default function LoginPage() {
  return <Suspense><AuthEntry kind='login' /></Suspense>
}
