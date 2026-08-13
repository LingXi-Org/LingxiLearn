import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() {
  return [{ id: 'lingxi' }]
}
export default function Page() {
  return <CapabilityPage title='资源作者 · 未接入' />
}
