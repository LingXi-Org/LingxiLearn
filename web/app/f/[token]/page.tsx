import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ token: 'lingxi' }] }
export default function Page() { return <CapabilityPage title='共享资源 · 未接入' /> }
