'use client'

import { redirect } from 'next/navigation'
import { LingxiResourcePage } from '@/app/workspace/[workspaceId]/components/lingxi-resource-page'

export function SettingsPage({ section }: { section: string }) {
  if (section === 'general') return <LingxiResourcePage kind='settings' />
  redirect('/workspace/lingxi/settings')
}
