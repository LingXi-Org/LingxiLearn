import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ provider: 'lingxi', model: 'lingxi' }] }
export default function Page() { return <CapabilityPage title='模型详情 · 未接入' /> }
