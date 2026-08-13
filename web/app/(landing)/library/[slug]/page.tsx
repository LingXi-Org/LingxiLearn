import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() {
  return [{ slug: 'lingxi' }]
}
export default function Page() {
  return <CapabilityPage title='资源详情 · 未接入' />
}
