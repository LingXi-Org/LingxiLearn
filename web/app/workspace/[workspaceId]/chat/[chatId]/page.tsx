import { Suspense } from 'react'
import type { Metadata } from 'next'
import { Home } from '../../home/home'
import { HomeFallback } from '../../home/home-fallback'

export const metadata: Metadata = {
  title: '学习对话',
}

export default async function ChatPage({
  params,
}: {
  params: Promise<{ workspaceId: string; chatId: string }>
}) {
  const { workspaceId, chatId } = await params
  return (
    <Suspense fallback={<HomeFallback />}>
      <Home chatId={chatId === 'lingxi' ? undefined : chatId} tableViewsEnabled={false} />
    </Suspense>
  )
}
