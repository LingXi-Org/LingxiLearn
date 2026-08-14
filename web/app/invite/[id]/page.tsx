import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ id: 'lingxi' }] }
export default function Page() { return <CapabilityPage title='邀请 · 未接入' /> }
