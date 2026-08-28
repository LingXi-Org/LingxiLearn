import { ArtifactLibrary } from '@/features/artifact/artifact-library'

export default async function ArtifactsPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = await params
  return <ArtifactLibrary workspaceId={workspaceId} />
}
