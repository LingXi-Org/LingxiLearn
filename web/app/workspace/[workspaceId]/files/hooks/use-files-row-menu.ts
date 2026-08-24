'use client'

import { type MouseEvent, useCallback, useMemo, useRef } from 'react'
import { createLogger } from '@/lib/logger'
import type { WorkspaceFileRecord } from '@/lib/api/contracts/workspace-files'
import {
  buildMoveOptions,
  folderRowId,
  type MoveOptionNode,
  parseMoveOptionValue,
} from '@/app/workspace/[workspaceId]/components/folders'
import { useContextMenu } from '@/app/workspace/[workspaceId]/components/hooks'
import type { FilesDeleteFlow } from '@/app/workspace/[workspaceId]/files/hooks/use-files-delete-flow'
import type { FilesDownloadsController } from '@/app/workspace/[workspaceId]/files/hooks/use-files-downloads'
import { fileRowId, parseFilesRowId } from '@/app/workspace/[workspaceId]/files/lib/file-row-ids'
import type { FileResourceItem } from '@/app/workspace/[workspaceId]/files/lib/file-types'
import type { WorkspaceFileFolderApi } from '@/hooks/queries/workspace-file-folders'

const logger = createLogger('Files')

export interface UseFilesRowMenuParams {
  /** Latest files, read through a ref so menu handlers never capture a stale list. */
  filesRef: { current: WorkspaceFileRecord[] }
  folders: WorkspaceFileFolderApi[]
  selectedRowIds: ReadonlySet<string>
  visibleRowIds: string[]
  selectedFileIds: string[]
  selectedFolderIds: string[]
  /** Right-clicking an unselected row selects it (replacing the selection) first. */
  selectOnly: (rowId: string, index: number) => void
  onOpenFolder: (folderId: string) => void
  onOpenFile: (file: WorkspaceFileRecord) => void
  onStartRenameRow: (rowId: string, name: string) => void
  onShareFile: (fileId: string) => void
  /** Bulk delete of the current selection (used when the right-clicked row is selected). */
  onBulkDelete: () => void
  downloads: FilesDownloadsController
  deleteFlow: FilesDeleteFlow
  pinnedFolderIds: ReadonlySet<string>
  pinnedFileIds: ReadonlySet<string>
  togglePin: (item: FileResourceItem) => void
  descendantIndex: Map<string, Set<string>>
  /** Fires after a successful move so the list can clear its selection. */
  onMoved: () => void
}

/**
 * The row context menu controller: which row was right-clicked, and every command the menu
 * offers (open, download, rename, share, delete, move, pin). Availability itself comes from
 * the command matrix in the list view; this hook only executes.
 */
export function useFilesRowMenu({
  filesRef,
  folders,
  selectedRowIds,
  visibleRowIds,
  selectedFileIds,
  selectedFolderIds,
  selectOnly,
  onOpenFolder,
  onOpenFile,
  onStartRenameRow,
  onShareFile,
  onBulkDelete,
  downloads,
  deleteFlow,
  pinnedFolderIds,
  pinnedFileIds,
  togglePin,
  descendantIndex,
  onMoved,
}: UseFilesRowMenuParams) {
  const { isOpen, position, handleContextMenu, closeMenu } = useContextMenu()

  const contextMenuItemRef = useRef<FileResourceItem | null>(null)

  const handleRowContextMenu = useCallback(
    (e: MouseEvent, rowId: string) => {
      const parsed = parseFilesRowId(rowId)
      const item =
        parsed.kind === 'folder'
          ? folders.find((folder) => folder.id === parsed.id)
          : filesRef.current.find((file) => file.id === parsed.id)
      if (!item) return
      contextMenuItemRef.current =
        parsed.kind === 'folder'
          ? { kind: 'folder', id: parsed.id, folder: item as WorkspaceFileFolderApi }
          : { kind: 'file', id: parsed.id, file: item as WorkspaceFileRecord }
      if (!selectedRowIds.has(rowId)) {
        selectOnly(rowId, visibleRowIds.indexOf(rowId))
      }
      handleContextMenu(e)
    },
    [folders, filesRef, selectedRowIds, visibleRowIds, selectOnly, handleContextMenu]
  )

  const handleOpen = useCallback(() => {
    const item = contextMenuItemRef.current
    if (!item) return
    if (item.kind === 'folder') {
      onOpenFolder(item.folder.id)
      closeMenu()
      return
    }
    onOpenFile(item.file)
    closeMenu()
  }, [onOpenFolder, onOpenFile, closeMenu])

  const handleDownload = useCallback(() => {
    const item = contextMenuItemRef.current
    if (!item) return
    const rowId = item.kind === 'file' ? fileRowId(item.file.id) : folderRowId(item.folder.id)
    if (selectedRowIds.has(rowId) && selectedRowIds.size > 1) {
      void downloads.downloadSelection(
        filesRef.current.filter((file) => selectedFileIds.includes(file.id)),
        selectedFolderIds
      )
      closeMenu()
      return
    }
    if (item.kind === 'folder') {
      const folderId = item.folder.id
      closeMenu()
      void downloads.downloadArchive({ folderIds: [folderId] })
      return
    }
    void downloads.downloadFile(item.file)
    closeMenu()
  }, [selectedRowIds, selectedFileIds, selectedFolderIds, filesRef, downloads, closeMenu])

  const handleRename = useCallback(() => {
    const item = contextMenuItemRef.current
    if (item?.kind === 'file') onStartRenameRow(fileRowId(item.file.id), item.file.name)
    if (item?.kind === 'folder') onStartRenameRow(folderRowId(item.folder.id), item.folder.name)
    closeMenu()
  }, [onStartRenameRow, closeMenu])

  const handleShare = useCallback(() => {
    const item = contextMenuItemRef.current
    if (item?.kind === 'file') onShareFile(item.file.id)
    closeMenu()
  }, [onShareFile, closeMenu])

  const handleDelete = useCallback(() => {
    const item = contextMenuItemRef.current
    if (!item) return
    const rowId = item.kind === 'file' ? fileRowId(item.file.id) : folderRowId(item.folder.id)
    if (selectedRowIds.has(rowId) && selectedRowIds.size > 1) {
      onBulkDelete()
      closeMenu()
      return
    }
    deleteFlow.requestDelete(
      item.kind === 'file'
        ? { fileIds: [item.file.id], folderIds: [], name: item.file.name }
        : { fileIds: [], folderIds: [item.folder.id], name: item.folder.name }
    )
    closeMenu()
  }, [selectedRowIds, onBulkDelete, deleteFlow, closeMenu])

  const handleTogglePin = useCallback(() => {
    const item = contextMenuItemRef.current
    if (!item) return
    togglePin(item)
    closeMenu()
  }, [togglePin, closeMenu])

  const handleMove = useCallback(
    async (optionValue: string) => {
      const targetFolderId = parseMoveOptionValue(optionValue)
      try {
        await deleteFlow.moveSelection(selectedFileIds, selectedFolderIds, targetFolderId)
        onMoved()
        closeMenu()
      } catch (error) {
        logger.error('Failed to move items:', error)
      }
    },
    [deleteFlow, selectedFileIds, selectedFolderIds, onMoved, closeMenu]
  )

  /**
   * The "Move to" tree, minus the selected folders and everything under them — moving a
   * folder into its own subtree would close a cycle.
   */
  const moveOptions = useMemo((): MoveOptionNode[] => {
    const excluded = new Set<string>(selectedFolderIds)
    for (const folderId of selectedFolderIds) {
      for (const descendantId of descendantIndex.get(folderId) ?? []) excluded.add(descendantId)
    }
    return buildMoveOptions({ folders, rootLabel: 'Files', excludedFolderIds: excluded })
  }, [folders, selectedFolderIds, descendantIndex])

  /**
   * Read off the same ref the handlers use, so the menu's Pin/Unpin label describes the row
   * that was right-clicked. Opening the menu is a state change, so this re-reads on the
   * render that shows it.
   */
  const contextMenuItem = contextMenuItemRef.current
  const isItemPinned = contextMenuItem
    ? (contextMenuItem.kind === 'folder' ? pinnedFolderIds : pinnedFileIds).has(contextMenuItem.id)
    : false

  return {
    isOpen,
    position,
    closeMenu,
    contextMenuItem,
    isItemPinned,
    moveOptions,
    handleRowContextMenu,
    handleOpen,
    handleDownload,
    handleRename,
    handleShare,
    handleDelete,
    handleTogglePin,
    handleMove,
  }
}
