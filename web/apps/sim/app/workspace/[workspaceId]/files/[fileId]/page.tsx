import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', fileId: 'not-integrated' }] }
export default function Page() { return <CapabilityPage title='文件详情 · 未接入' /> }
