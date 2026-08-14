import { StandaloneSettingsShell } from '@/components/settings/standalone-settings-shell'

export default function AccountSettingsLayout({ children }: { children: React.ReactNode }) {
  return <StandaloneSettingsShell plane='account'>{children}</StandaloneSettingsShell>
}
