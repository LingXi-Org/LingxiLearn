import { Suspense } from 'react'
import type { Metadata } from 'next'
import { redirect } from 'next/navigation'
import { isChatEnabled } from '@/lib/core/config/env-flags'
import { Home } from './home'
import { HomeFallback } from './home-fallback'

export const metadata: Metadata = {
  title: '学习工作台',
}

export default async function HomePage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = await params

  if (!isChatEnabled) redirect(`/workspace/${workspaceId}`)

  // Lingxi is a private singleton workspace. Its task/resource data comes from
  // the Lingxi adapter in the browser, so the native Sim prefetch layer (which
  // expects a Sim session header) must not run for this route.
  if (workspaceId === 'lingxi') {
    return (
      <Suspense fallback={<HomeFallback />}>
        <Home tableViewsEnabled={false} />
      </Suspense>
    )
  }

  return (
    <Suspense fallback={<HomeFallback />}>
      <Home tableViewsEnabled={false} />
    </Suspense>
  )
}
