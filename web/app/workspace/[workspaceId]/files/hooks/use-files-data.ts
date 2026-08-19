'use client'

import { useMemo } from 'react'
import { createLogger } from '@/lib/logger'
import type { WorkspaceFileRecord } from '@/lib/uploads/contexts/workspace'
import { buildDescendantIndex } from '@/app/workspace/[workspaceId]/components/folders'
import { buildFolderSizeMap } from '@/app/workspace/[workspaceId]/files/lib/folder-size-map'
import { usePinItem, usePinnedIds, useUnpinItem } from '@/hooks/queries/pinned-items'
import type { WorkspaceMember } from '@/hooks/queries/workspace'
import { useWorkspaceMembersQuery } from '@/hooks/queries/workspace'
import {
  useWorkspaceFileFolders,
  type WorkspaceFileFolderApi,
} from '@/hooks/queries/workspace-file-folders'
import { useWorkspaceFiles } from '@/hooks/queries/workspace-files'

const logger = createLogger('Files')

export const EMPTY_WORKSPACE_FILES: WorkspaceFileRecord[] = []
export const EMPTY_WORKSPACE_FILE_FOLDERS: WorkspaceFileFolderApi[] = []

/**
 * The Files feature's query + derived-data bundle: workspace files, their folders, members,
 * pin state, and the indexes the list layer sorts, sizes, and drop-validates against.
 * Both the list and the detail view draw from here; React Query dedupes the queries.
 */
export function useFilesData(workspaceId: string) {
  const { data: files = EMPTY_WORKSPACE_FILES, isLoading, error } = useWorkspaceFiles(workspaceId)
  const { data: folders = EMPTY_WORKSPACE_FILE_FOLDERS } = useWorkspaceFileFolders(workspaceId)
  const { data: members } = useWorkspaceMembersQuery(workspaceId)
  const pinnedFileIds = usePinnedIds(workspaceId, 'file')
  // Folders pin under their own resource type, so their pinned set is a separate query.
  const pinnedFolderIds = usePinnedIds(workspaceId, 'folder')
  const pinItem = usePinItem()
  const unpinItem = useUnpinItem()

  if (error) {
    logger.error('Failed to load files:', error)
  }

  const membersById = useMemo(() => {
    const map = new Map<string, WorkspaceMember>()
    for (const member of members ?? []) map.set(member.userId, member)
    return map
  }, [members])

  const folderById = useMemo(() => new Map(folders.map((folder) => [folder.id, folder])), [folders])

  const folderSizeMap = useMemo(() => buildFolderSizeMap(files, folders), [files, folders])

  const descendantIndex = useMemo(() => buildDescendantIndex(folders), [folders])

  return {
    files,
    folders,
    members,
    isLoading,
    pinnedFileIds,
    pinnedFolderIds,
    pinItem,
    unpinItem,
    membersById,
    folderById,
    folderSizeMap,
    descendantIndex,
  }
}

export type FilesData = ReturnType<typeof useFilesData>
