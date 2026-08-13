import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', tableId: 'not-integrated' }] }
export default function Page() { return <CapabilityPage title='表格详情 · 未接入' /> }
