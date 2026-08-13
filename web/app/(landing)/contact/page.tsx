import type { Metadata } from 'next'
import { CapabilityPage } from '@/lib/lingxi/components/capability-page'

export const metadata: Metadata = { title: '联系灵犀 · 未接入' }

export default function Page() {
  return <CapabilityPage title='联系团队 · 未接入' />
}
