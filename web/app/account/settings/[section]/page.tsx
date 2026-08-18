import type { AccountSettingsSection } from '@/components/settings/navigation'
import { AccountSettingsRenderer } from '@/components/settings/account-settings-renderer'
import { AccountSettings } from '../account-settings'

export function generateStaticParams() {
  return [{ section: 'profile' }, { section: 'security' }, { section: 'sessions' }]
}

export default async function Page({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params
  // API keys and platform admin sections keep their native surfaces; every
  // account identity flow stays on LingxiIdentity. Billing had no backend
  // owner and was removed with its routes (issue #54), so billing-shaped
  // sections fall back to the identity profile instead of a fake closure.
  if (section === 'api-keys' || section === 'admin' || section === 'mothership') {
    return <AccountSettingsRenderer section={section as AccountSettingsSection} />
  }
  if (
    section === 'profile' ||
    section === 'general' ||
    section === 'security' ||
    section === 'sessions'
  ) {
    return <AccountSettings initialSection={section === 'general' ? 'profile' : section} />
  }
  return <AccountSettings initialSection='profile' />
}
