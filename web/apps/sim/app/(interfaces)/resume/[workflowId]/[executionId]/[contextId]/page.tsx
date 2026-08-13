import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ workflowId: 'lingxi', executionId: 'lingxi', contextId: 'lingxi' }] }
export default function Page() { return <CapabilityPage title='继续执行 · 未接入' /> }
