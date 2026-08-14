import { SettingsPage } from './[section]/settings'

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi' }]
}

export default function Page() {
  return <SettingsPage section='general' />
}
