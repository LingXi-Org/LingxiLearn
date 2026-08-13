import type { Metadata } from 'next'
import { LingxiChat } from '@/components/lingxi/lingxi-chat'

export const metadata: Metadata = {
  title: '学习工作台',
}

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi' }]
}

export default async function LingxiHomePage({
  params,
}: {
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = await params
  return <LingxiChat workspaceId={workspaceId} />
}
