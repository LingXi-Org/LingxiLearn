import { NotIntegrated } from '@/ee/not-integrated'

export function generateStaticParams() { return [{ workspaceId: 'lingxi' }] }

export default function NewSkillPage() {
  return <NotIntegrated title='创建 Skill' />
}
