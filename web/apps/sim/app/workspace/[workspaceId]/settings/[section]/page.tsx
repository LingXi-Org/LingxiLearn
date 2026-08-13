import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', section: 'general' }] }
export default function Page() { return <CapabilityPage title='该设置项 · 未接入' /> }
