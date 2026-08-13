import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi' }] }
export default function Page() { return <CapabilityPage title='用量与计费 · 未接入' /> }
