import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ section: 'profile' }] }
export default function Page() { return <CapabilityPage title='账户设置 · 未接入' /> }
