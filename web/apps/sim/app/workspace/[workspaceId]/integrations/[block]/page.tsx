import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', block: 'not-integrated' }] }
export default function Page() { return <CapabilityPage title='集成详情 · 未接入' /> }
