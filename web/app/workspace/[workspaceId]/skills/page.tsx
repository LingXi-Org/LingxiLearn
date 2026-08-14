import type { Metadata } from 'next'
import { Skills } from './skills'

export const metadata: Metadata = {
  title: 'Skills · 灵犀智学',
}

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi' }]
}

export default function SkillsPage() {
  return <Skills />
}
