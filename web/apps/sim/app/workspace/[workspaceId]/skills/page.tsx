import type { Metadata } from 'next'
import { LingxiSkills } from './lingxi-skills'

export const metadata: Metadata = {
  title: 'Skills · 灵犀智学',
}

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi' }]
}

export default function SkillsPage() {
  return <LingxiSkills />
}
