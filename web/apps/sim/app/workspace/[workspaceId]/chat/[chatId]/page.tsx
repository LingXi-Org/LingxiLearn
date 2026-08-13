import { Suspense } from 'react'
import type { Metadata } from 'next'
import { Home } from '@/app/workspace/[workspaceId]/home/home'
import { HomeFallback } from '@/app/workspace/[workspaceId]/home/home-fallback'

export const metadata: Metadata = { title: '灵犀任务' }

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi', chatId: 'lingxi' }]
}

interface ChatPageProps {
  params: Promise<{ workspaceId: string; chatId: string }>
}

export default async function ChatPage({ params }: ChatPageProps) {
  const { chatId } = await params
  return (
    <Suspense fallback={<HomeFallback />}>
      <Home key={chatId} chatId={chatId} userName='同学' tableViewsEnabled={false} />
    </Suspense>
  )
}
