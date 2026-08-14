import { redirect } from 'next/navigation'

export default async function IntegrationsRedirect({
  params,
}: {
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = await params
  redirect(`/workspace/${workspaceId}/skills`)
}
