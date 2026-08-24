'use client'

import { useCallback, useRef, useState } from 'react'
import { toast } from '@/components/ui-kit'
import { createLogger } from '@/lib/logger'
import { toError } from '@/lib/utils/errors'
import { useRouter } from 'next/navigation'
import type { WorkspaceFileRecord } from '@/lib/api/contracts/workspace-files'
import { getMimeTypeFromExtension } from '@/lib/uploads/utils/file-utils'
import {
  folderRowId,
  nextUntitledFolderName,
} from '@/app/workspace/[workspaceId]/components/folders'
import {
  DEFAULT_UNTITLED_NAME,
  uniqueMarkdownName,
} from '@/app/workspace/[workspaceId]/files/untitled-title'
import type { WorkspaceFileFolderApi } from '@/hooks/queries/workspace-file-folders'
import {
  useCreateWorkspaceFileFolder,
  useUpdateWorkspaceFileFolder,
} from '@/hooks/queries/workspace-file-folders'
import { useCreateWorkspaceFile, useRenameWorkspaceFile } from '@/hooks/queries/workspace-files'

const logger = createLogger('Files')

export interface UseFilesCreationParams {
  workspaceId: string
  currentFolderId: string | null
  /** Latest files/folders, read through refs so creation never captures a stale list. */
  filesRef: { current: WorkspaceFileRecord[] }
  folders: WorkspaceFileFolderApi[]
  /** Fires after a folder is created, so the list can enter inline rename on it. */
  onFolderCreated?: (folderRowId: string, folderName: string) => void
}

/**
 * The create commands: a new markdown file (named `untitled (n).md`, opened in the editor
 * via `?new=1`) and a new folder (dropped straight into inline rename).
 */
export function useFilesCreation({
  workspaceId,
  currentFolderId,
  filesRef,
  folders,
  onFolderCreated,
}: UseFilesCreationParams) {
  const router = useRouter()
  const createWorkspaceFile = useCreateWorkspaceFile()
  const createFolder = useCreateWorkspaceFileFolder()

  const [creatingFile, setCreatingFile] = useState(false)
  const creatingFileRef = useRef(creatingFile)
  creatingFileRef.current = creatingFile

  const handleCreateFile = useCallback(async () => {
    if (creatingFileRef.current) return
    setCreatingFile(true)

    try {
      const existingNames = new Set(
        filesRef.current.filter((f) => (f.folderId ?? null) === currentFolderId).map((f) => f.name)
      )
      const name = uniqueMarkdownName(DEFAULT_UNTITLED_NAME, existingNames)

      const mimeType = getMimeTypeFromExtension('md')
      const result = await createWorkspaceFile.mutateAsync({
        workspaceId,
        name,
        contentType: mimeType,
        folderId: currentFolderId ?? undefined,
      })
      const fileId = result.file.id
      if (fileId) {
        const params = new URLSearchParams({ new: '1' })
        if (currentFolderId) params.set('folderId', currentFolderId)
        router.push(`/workspace/${workspaceId}/files/${fileId}?${params.toString()}`)
      }
    } catch (err) {
      logger.error('Failed to create file:', err)
    } finally {
      setCreatingFile(false)
    }
  }, [workspaceId, router, currentFolderId, filesRef, createWorkspaceFile])

  const handleCreateFolder = useCallback(async () => {
    if (!workspaceId) return

    try {
      const folder = await createFolder.mutateAsync({
        workspaceId,
        name: nextUntitledFolderName(folders, currentFolderId),
        parentId: currentFolderId,
      })
      onFolderCreated?.(folderRowId(folder.id), folder.name)
    } catch (error) {
      logger.error('Failed to create folder:', error)
      toast.error(toError(error).message)
    }
  }, [workspaceId, folders, currentFolderId, createFolder, onFolderCreated])

  return {
    creatingFile,
    createFolderIsPending: createFolder.isPending,
    handleCreateFile,
    handleCreateFolder,
  }
}

/**
 * The rename commands: rows (file or folder), the open folder's breadcrumb crumb, and the
 * detail header — each bound to the mutation that persists its name.
 */
export function useFilesRenameMutations(workspaceId: string) {
  const renameFile = useRenameWorkspaceFile()
  const updateFolder = useUpdateWorkspaceFileFolder()

  const renameFileTo = useCallback(
    (fileId: string, name: string) => renameFile.mutateAsync({ workspaceId, fileId, name }),
    [workspaceId, renameFile]
  )
  const renameFolderTo = useCallback(
    (folderId: string, name: string) =>
      updateFolder.mutateAsync({ workspaceId, folderId, updates: { name } }),
    [workspaceId, updateFolder]
  )

  return { renameFileTo, renameFolderTo }
}
