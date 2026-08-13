import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ id: 'lingxi' }] }
export default function Page() { return <CapabilityPage title='作者页面 · 未接入' /> }
