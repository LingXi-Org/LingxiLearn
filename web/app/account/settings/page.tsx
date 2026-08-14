import type { Metadata } from 'next'
import { AccountSettingsRenderer } from '@/components/settings/account-settings-renderer'

export const metadata: Metadata = { title: '账户设置' }

export default function AccountSettingsPage() {
  return <AccountSettingsRenderer section='general' />
}
