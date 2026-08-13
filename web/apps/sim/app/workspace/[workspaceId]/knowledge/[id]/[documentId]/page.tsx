import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', id: 'not-integrated', documentId: 'not-integrated' }] }
export default function Page() { return <CapabilityPage title='知识库文档 · 未接入' /> }
