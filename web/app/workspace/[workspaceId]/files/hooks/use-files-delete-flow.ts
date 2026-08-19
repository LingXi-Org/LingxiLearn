'use client'

import { useCallback, useRef, useState } from 'react'
import { createLogger } from '@/lib/logger'
import {
  useBulkArchiveWorkspaceFileItems,
  useMoveWorkspaceFileItems,
} from '@/hooks/queries/workspace-file-folders'
import { useDeleteWorkspaceFile } from '@/hooks/queries/workspace-files'

const logger = createLogger('Files')

export interface FilesDeleteTarget {
  fileIds: string[]
  folderIds: string[]
  name: string
}

/**
 * The archive/delete confirmation flow shared by the list and the detail view: holds the
 * pending target + modal state, and executes the right mutation — the bulk archive endpoint
 * for folders or multi-file batches, the single delete otherwise.
 */
export function useFilesDeleteFlow(workspaceId: string) {
  const deleteFile = useDeleteWorkspaceFile()
  const bulkArchiveItems = useBulkArchiveWorkspaceFileItems()

  const [deleteTarget, setDeleteTarget] = useState<FilesDeleteTarget | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const deleteTargetRef = useRef(deleteTarget)
  deleteTargetRef.current = deleteTarget

  const requestDelete = useCallback((target: FilesDeleteTarget) => {
    setDeleteTarget(target)
    setShowDeleteConfirm(true)
  }, [])

  /** Runs the confirmed delete; `onDeleted` fires after the mutation settles. */
  const confirmDelete = useCallback(
    async (onDeleted?: () => void) => {
      const target = deleteTargetRef.current
      if (!target) return

      try {
        if (target.folderIds.length > 0 || target.fileIds.length > 1) {
          await bulkArchiveItems.mutateAsync({
            workspaceId,
            fileIds: target.fileIds,
            folderIds: target.folderIds,
          })
        } else if (target.fileIds.length === 1) {
          await deleteFile.mutateAsync({
            workspaceId,
            fileId: target.fileIds[0],
          })
        } else {
          setShowDeleteConfirm(false)
          setDeleteTarget(null)
          return
        }
        setShowDeleteConfirm(false)
        setDeleteTarget(null)
        onDeleted?.()
      } catch (err) {
        logger.error('Failed to delete file:', err)
      }
    },
    [workspaceId]
  )

  /** Moves the current selection into a destination folder. */
  const moveItems = useMoveWorkspaceFileItems()
  const moveSelection = useCallback(
    async (fileIds: string[], folderIds: string[], targetFolderId: string | null) => {
      await moveItems.mutateAsync({ workspaceId, fileIds, folderIds, targetFolderId })
    },
    [workspaceId, moveItems]
  )

  return {
    deleteTarget,
    showDeleteConfirm,
    setShowDeleteConfirm,
    requestDelete,
    confirmDelete,
    moveSelection,
    isDeleting: deleteFile.isPending || bulkArchiveItems.isPending,
    isMoving: moveItems.isPending,
  }
}

export type FilesDeleteFlow = ReturnType<typeof useFilesDeleteFlow>
