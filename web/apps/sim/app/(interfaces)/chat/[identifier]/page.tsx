import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ identifier: 'lingxi' }] }
export default function Page() { return <CapabilityPage title='公开对话 · 未接入' /> }
