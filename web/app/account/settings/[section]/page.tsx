import { LingxiUnavailableSettingsPage } from '@/app/workspace/[workspaceId]/components/lingxi-settings-pages'
import { AccountSettings } from '../account-settings'

export function generateStaticParams() {
  return [
    { section: 'profile' },
    { section: 'security' },
    { section: 'sessions' },
    { section: 'billing' },
    { section: 'users' },
  ]
}

export default async function Page({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params
  // The account component keeps the identity verification flows together. The
  // section URL is accepted for native Sim links while the visible tab remains
  // a single LingxiIdentity-backed account center.
  if (
    section === 'profile' ||
    section === 'general' ||
    section === 'security' ||
    section === 'sessions'
  ) {
    return <AccountSettings initialSection={section === 'general' ? 'profile' : section} />
  }
  return <LingxiUnavailableSettingsPage title={section} />
}
