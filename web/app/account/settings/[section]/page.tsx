import type { AccountSettingsSection } from '@/components/settings/navigation'
import { AccountSettingsRenderer } from '@/components/settings/account-settings-renderer'
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
  // Profile, billing and API keys use the complete native settings surfaces.
  // Identity-specific security/session flows remain on the LingxiIdentity
  // surface because they require its verification and session APIs.
  if (section === 'billing' || section === 'api-keys' || section === 'admin' || section === 'mothership') {
    const nativeSection = section === 'api-keys' ? 'api-keys' : section
    return <AccountSettingsRenderer section={nativeSection as AccountSettingsSection} />
  }
  if (
    section === 'profile' ||
    section === 'general' ||
    section === 'security' ||
    section === 'sessions'
  ) {
    return <AccountSettings initialSection={section === 'general' ? 'profile' : section} />
  }
  return <AccountSettingsRenderer section='general' />
}
