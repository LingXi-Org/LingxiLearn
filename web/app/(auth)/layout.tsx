import { AuthShell } from './components/auth-shell'
import { AuthRouteGuard } from './components/auth-route-guard'

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthRouteGuard>
      <AuthShell>{children}</AuthShell>
    </AuthRouteGuard>
  )
}
