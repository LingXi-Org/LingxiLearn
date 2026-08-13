import { LingxiChat } from '@/components/lingxi/lingxi-chat'

export function generateStaticParams() {
  return [{ identifier: 'lingxi' }]
}

export default async function Page({ params }: { params: Promise<{ identifier: string }> }) {
  const { identifier } = await params
  return (
    <LingxiChat workspaceId='lingxi' taskId={identifier === 'lingxi' ? undefined : identifier} />
  )
}
