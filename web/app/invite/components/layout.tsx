import { AuthShell } from '@/app/(auth)/components/auth-shell'
import { SupportFooter } from '@/app/(auth)/components/support-footer'

interface InviteLayoutProps {
  children: React.ReactNode
}

/**
 * Invite pages wear the same light auth shell as login/signup — the shared
 * {@link AuthShell} (logo-only header, centered column) plus the support footer —
 * so the invite-to-workspace flow is visually aligned with the rest of auth.
 */
export default function InviteLayout({ children }: InviteLayoutProps) {
  return <AuthShell footer={<SupportFooter position='static' />}>{children}</AuthShell>
}
