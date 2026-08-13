import { Suspense } from 'react'
import type { Metadata } from 'next'
import { Skills } from './skills'

export const metadata: Metadata = {
  title: '技能 · 灵犀智学',
}

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi' }]
}

export default function SkillsPage() {
  return (
    <Suspense fallback={<div className='h-full bg-[var(--bg)]' />}>
      <Skills />
    </Suspense>
  )
}
