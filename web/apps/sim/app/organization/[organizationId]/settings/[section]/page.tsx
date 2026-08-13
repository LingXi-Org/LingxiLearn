import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ organizationId: 'lingxi', section: 'general' }] }
export default function Page() { return <CapabilityPage title='组织设置 · 未接入' /> }
