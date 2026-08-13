import type { Metadata } from 'next'
import { CapabilityPage } from '@/lib/lingxi/components/capability-page'

export const metadata: Metadata = {
  title: 'Unsubscribe',
  robots: { index: false },
}

export default function UnsubscribePage() {
  return <CapabilityPage title='取消订阅 · 未接入' />
}
