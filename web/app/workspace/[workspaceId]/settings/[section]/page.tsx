import { SettingsPage } from './settings'

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi', section: 'general' }]
}
export default async function Page({
  params,
}: {
  params: Promise<{ workspaceId: string; section: string }>
}) {
  const { section } = await params
  const aliases: Record<string, string> = {
    profile: 'general',
    preferences: 'general',
  }
  return <SettingsPage section={aliases[section] ?? section} />
}
