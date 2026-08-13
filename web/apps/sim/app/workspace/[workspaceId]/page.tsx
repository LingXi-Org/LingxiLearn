import { redirect } from 'next/navigation'

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi' }]
}

export default function WorkspacePage({ params }: { params: { workspaceId: string } }) {
  redirect(`/workspace/${params.workspaceId}/home`)
}
