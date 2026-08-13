import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() {
  return [{ provider: 'lingxi' }]
}
export default function Page() {
  return <CapabilityPage title='模型提供商 · 未接入' />
}
