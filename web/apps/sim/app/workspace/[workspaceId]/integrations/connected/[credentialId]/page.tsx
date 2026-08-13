import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', credentialId: 'not-integrated' }] }
export default function Page() { return <CapabilityPage title='连接配置 · 未接入' /> }
