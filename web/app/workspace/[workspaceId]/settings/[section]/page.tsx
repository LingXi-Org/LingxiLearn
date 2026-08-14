import {
  LingxiBillingPage,
  LingxiUnavailableSettingsPage,
  LingxiUserManagementPage,
} from '@/app/workspace/[workspaceId]/components/lingxi-settings-pages'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', section: 'general' }] }
export default async function Page({ params }: { params: Promise<{ workspaceId: string; section: string }> }) {
  const { section } = await params
  if (section === 'billing' || section === 'subscription') return <LingxiBillingPage />
  if (section === 'users' || section === 'members' || section === 'teammates' || section === 'admin') return <LingxiUserManagementPage />
  if (section === 'general' || section === 'profile' || section === 'preferences') {
    const { LingxiResourcePage } = await import('@/app/workspace/[workspaceId]/components/lingxi-resource-page')
    return <LingxiResourcePage kind='settings' />
  }
  return <LingxiUnavailableSettingsPage title={section} />
}
