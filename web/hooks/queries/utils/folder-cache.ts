import type { FolderResourceType } from '@/lib/api/contracts/folders'
import { getQueryClient } from '@/app/_shell/providers/get-query-client'
import { folderKeys } from '@/hooks/queries/utils/folder-keys'
import type { WorkspaceFolder } from '@/lib/folders/types'

const EMPTY_FOLDERS: WorkspaceFolder[] = []

function getFolders(
  workspaceId: string,
  resourceType: FolderResourceType = 'workflow'
): WorkspaceFolder[] {
  return (
    getQueryClient().getQueryData<WorkspaceFolder[]>(
      folderKeys.list(workspaceId, 'active', resourceType)
    ) ?? EMPTY_FOLDERS
  )
}

export function getFolderMap(
  workspaceId: string,
  resourceType: FolderResourceType = 'workflow'
): Record<string, WorkspaceFolder> {
  return Object.fromEntries(
    getFolders(workspaceId, resourceType).map((folder) => [folder.id, folder])
  )
}
