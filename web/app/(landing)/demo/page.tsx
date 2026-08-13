import type { Metadata } from 'next'
import { CapabilityPage } from '@/lib/lingxi/components/capability-page'

export const metadata: Metadata = { title: '预约演示 · 未接入' }

export default function Page() {
  return <CapabilityPage title='预约演示 · 未接入' />
}
