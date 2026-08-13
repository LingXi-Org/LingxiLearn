import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', workflowId: 'not-integrated' }] }
export default function Page() { return <CapabilityPage title='工作流编辑 · 未接入' /> }
