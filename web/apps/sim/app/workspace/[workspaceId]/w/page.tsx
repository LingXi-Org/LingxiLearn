import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi' }] }
export default function Page() { return <CapabilityPage title='可编辑工作流 · 未接入' /> }
