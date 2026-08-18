import type { Metadata } from 'next'
import { AccountSettings } from './account-settings'

export const metadata: Metadata = { title: '账户设置' }

export default function AccountSettingsPage() {
  return <AccountSettings initialSection='profile' />
}
