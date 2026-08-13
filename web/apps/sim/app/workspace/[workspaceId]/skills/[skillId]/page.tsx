import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', skillId: 'lingxi' }] }
export default function Page() { return <CapabilityPage title='Skill 详情 · 只读' /> }
