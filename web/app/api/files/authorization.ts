import { getFileMetadataByKey } from '@/lib/uploads/server/metadata'
import type { StorageContext } from '@/lib/uploads/shared/types'
import { getUserEntityPermissions } from '@/lib/workspaces/permissions/utils'

const PUBLIC_CONTEXTS = new Set<StorageContext>([
  'og-images',
  'profile-pictures',
  'workspace-logos',
])

/**
 * Authorize server-side access to a stored file before generating a URL or
 * reading its bytes. Workspace membership is the tenant boundary; the upload
 * owner is accepted for legacy personal files that have no workspace scope.
 */
export async function verifyFileAccess(
  key: string,
  userId: string,
  workspaceId?: string,
  context?: StorageContext,
  allowPublic = false
): Promise<boolean> {
  if (!key || !userId) return false
  if (allowPublic && context && PUBLIC_CONTEXTS.has(context)) return true

  const metadata = await getFileMetadataByKey(key, context)
  if (!metadata) return false

  if (metadata.userId === userId) return true

  const scopedWorkspaceId = workspaceId ?? metadata.workspaceId
  if (!scopedWorkspaceId) return false

  try {
    return (await getUserEntityPermissions(userId, 'workspace', scopedWorkspaceId)) !== null
  } catch {
    return false
  }
}
