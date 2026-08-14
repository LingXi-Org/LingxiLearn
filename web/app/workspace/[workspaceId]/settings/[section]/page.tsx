import { SettingsPage } from './settings'

export function generateStaticParams() { return [{ workspaceId: 'lingxi', section: 'general' }] }
export default async function Page({ params }: { params: Promise<{ workspaceId: string; section: string }> }) {
  const { section } = await params
  const aliases: Record<string, string> = {
    subscription: 'billing',
    profile: 'general',
    preferences: 'general',
    users: 'teammates',
    members: 'teammates',
  }
  return <SettingsPage section={(aliases[section] ?? section) as never} />
}
