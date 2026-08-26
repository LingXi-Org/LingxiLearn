import { notFound } from 'next/navigation'
import { AccountSettings } from '../account-settings'

export function generateStaticParams() {
  return [{ section: 'profile' }, { section: 'security' }, { section: 'sessions' }]
}

export default async function Page({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params
  // Every account identity flow stays on LingxiIdentity. The api-keys/admin/
  // mothership surfaces had no Lingxi backend owner and were removed with their
  // Sim closures (issue #54). Unknown and legacy aliases are real 404s so an
  // unsupported capability cannot masquerade as the profile page.
  if (section === 'profile' || section === 'security' || section === 'sessions') {
    return <AccountSettings initialSection={section} />
  }
  notFound()
}
