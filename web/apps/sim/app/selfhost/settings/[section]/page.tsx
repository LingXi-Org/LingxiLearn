import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ section: 'general' }] }
export default function Page() { return <CapabilityPage title='自托管设置 · 未接入' /> }
