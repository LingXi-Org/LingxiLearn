import { AccountSettings } from '../account-settings'

export function generateStaticParams() {
  return [{ section: 'profile' }, { section: 'security' }, { section: 'sessions' }]
}

export default async function Page({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params
  // Every account identity flow stays on LingxiIdentity. The api-keys/admin/
  // mothership surfaces had no Lingxi backend owner and were removed with their
  // Sim closures (issue #54) — unsupported sections fall back to the identity
  // profile instead of a fake closure.
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
