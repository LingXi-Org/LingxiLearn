import type { Metadata } from 'next'
import { LingxiChat } from '@/components/lingxi/lingxi-chat'

export const metadata: Metadata = {
  title: '学习对话',
}

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi', chatId: 'lingxi' }]
}

export default async function LingxiChatPage({
  params,
}: {
  params: Promise<{ workspaceId: string; chatId: string }>
}) {
  const { workspaceId, chatId } = await params
  return <LingxiChat workspaceId={workspaceId} taskId={chatId === 'lingxi' ? undefined : chatId} />
}
