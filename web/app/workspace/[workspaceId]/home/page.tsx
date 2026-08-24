import { Suspense } from 'react'
import type { Metadata } from 'next'
import { redirect } from 'next/navigation'
import { isChatEnabled } from '@/lib/core/config/env-flags'
import { WorkspaceHomeShell } from './home'
import { HomeFallback } from './home-fallback'

export const metadata: Metadata = {
  title: '学习工作台',
}

export default async function HomePage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = await params

  if (!isChatEnabled) redirect(`/workspace/${workspaceId}`)

  return (
    <Suspense fallback={<HomeFallback />}>
      <WorkspaceHomeShell tableViewsEnabled={false} />
    </Suspense>
  )
}
