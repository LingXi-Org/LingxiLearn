import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', id: 'not-integrated' }] }
export default function Page() { return <CapabilityPage title='知识库详情 · 未接入' /> }
