import { redirect } from 'next/navigation'

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi' }]
}

export default async function WorkspacePage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = await params
  redirect(`/workspace/${workspaceId}/home`)
}
