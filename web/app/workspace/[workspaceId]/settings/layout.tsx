import { SettingsHeaderProvider, SettingsHeaderShell } from '@/components/settings/settings-header'

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <SettingsHeaderProvider>
      <SettingsHeaderShell>{children}</SettingsHeaderShell>
    </SettingsHeaderProvider>
  )
}
