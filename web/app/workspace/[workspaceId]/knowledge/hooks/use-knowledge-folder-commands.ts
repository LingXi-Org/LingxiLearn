'use client'

import { type MutableRefObject, useCallback } from 'react'
import { toast } from '@sim/emcn'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@sim/utils/errors'
import {
  folderRowId,
  nextUntitledFolderName,
  parseMoveOptionValue,
} from '@/app/workspace/[workspaceId]/components/folders'
import { useCreateFolder, useDeleteFolderMutation, useUpdateFolder } from '@/hooks/queries/folders'
import type { usePinItem, useUnpinItem } from '@/hooks/queries/pinned-items'
import { KNOWLEDGE_FOLDER_RESOURCE_TYPE, type KnowledgeFolder } from '../list/types'

const logger = createLogger('Knowledge')

export interface UseKnowledgeFolderCommandsOptions {
  workspaceId: string
  /** Ref-backed latest-list state, from `useKnowledgeListData`. */
  foldersRef: MutableRefObject<KnowledgeFolder[]>
  currentFolderIdRef: MutableRefObject<string | null>
  setCurrentFolderId: (folderId: string | null) => void
  pinnedFolderIds: ReadonlySet<string>
  pinItem: ReturnType<typeof usePinItem>
  unpinItem: ReturnType<typeof useUnpinItem>
  /** Clears the search so a freshly created folder row is visible and renamable. */
  clearSearch: () => void
  /** Drops a created/renamed folder straight into its inline rename field. */
  startRowRename: (rowId: string, currentName: string) => void
  /** Closes the folder context menu after a one-shot command. */
  closeMenu: () => void
}

/**
 * Every mutation a knowledge folder can trigger, in one place. Folders here are the
 * domain-neutral workspace folders of the `knowledge_base` tree — nothing workflow-era
 * leaks into their handling.
 */
export function useKnowledgeFolderCommands({
  workspaceId,
  foldersRef,
  currentFolderIdRef,
  setCurrentFolderId,
  pinnedFolderIds,
  pinItem,
  unpinItem,
  clearSearch,
  startRowRename,
  closeMenu,
}: UseKnowledgeFolderCommandsOptions) {
  const createFolder = useCreateFolder()
  const updateFolder = useUpdateFolder()
  const deleteFolder = useDeleteFolderMutation()

  const createFolderInCurrentFolder = useCallback(async () => {
    if (!workspaceId) return
    const parentId = currentFolderIdRef.current
    const name = nextUntitledFolderName(foldersRef.current, parentId)

    try {
      const folder = await createFolder.mutateAsync({
        workspaceId,
        resourceType: KNOWLEDGE_FOLDER_RESOURCE_TYPE,
        name,
        parentId: parentId ?? undefined,
      })
      /**
       * A live search term filters the folder list too, so a brand-new "New folder" would
       * not match it — the row never renders, the rename field never appears, and the
       * create reads as a no-op even though it succeeded. Clear the search so the thing
       * just created is on screen to be named.
       */
      clearSearch()
      // Drop straight into rename: the auto-generated name is a placeholder, and the user
      // should not have to hunt for a second action to replace it.
      startRowRename(folderRowId(folder.id), folder.name)
    } catch (createError) {
      logger.error('Failed to create folder', createError)
      toast.error(getErrorMessage(createError, 'Failed to create folder'))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ref-backed options and mutation flags are read at call time
  }, [workspaceId])

  const saveFolderName = useCallback(
    (folderId: string, name: string) =>
      updateFolder.mutateAsync({
        workspaceId,
        resourceType: KNOWLEDGE_FOLDER_RESOURCE_TYPE,
        id: folderId,
        updates: { name },
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mutation objects are unstable; mutateAsync is stable in v5
    [workspaceId]
  )

  /** Shared by the "Move to" submenu and by dropping a folder row onto another folder. */
  const moveFolderTo = useCallback(
    async (folderId: string, parentId: string | null) => {
      try {
        await updateFolder.mutateAsync({
          workspaceId,
          resourceType: KNOWLEDGE_FOLDER_RESOURCE_TYPE,
          id: folderId,
          updates: { parentId },
        })
      } catch (moveError) {
        logger.error('Failed to move folder', moveError)
        toast.error(getErrorMessage(moveError, 'Failed to move folder'))
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mutation objects are unstable; mutateAsync is stable in v5
    [workspaceId]
  )

  const moveFolderFromMenu = useCallback(
    async (folder: KnowledgeFolder, optionValue: string) => {
      const parentId = parseMoveOptionValue(optionValue)
      // Live placement, not the snapshot taken when the menu opened — a refetch or
      // concurrent move in between would otherwise skip the write the user just chose.
      const current = foldersRef.current.find((item) => item.id === folder.id) ?? folder
      if ((current.parentId ?? null) !== parentId) await moveFolderTo(folder.id, parentId)
      closeMenu()
    },
    [foldersRef, moveFolderTo, closeMenu]
  )

  const confirmDeleteFolder = useCallback(
    async (folder: KnowledgeFolder) => {
      try {
        await deleteFolder.mutateAsync({
          workspaceId,
          resourceType: KNOWLEDGE_FOLDER_RESOURCE_TYPE,
          id: folder.id,
        })
        // Deleting the folder you are standing in leaves the list pointed at an archived
        // folder, which renders as an empty page with a dead breadcrumb — step out to its
        // parent instead.
        if (currentFolderIdRef.current === folder.id) {
          setCurrentFolderId(folder.parentId)
        }
      } catch (deleteError) {
        logger.error('Failed to delete folder', deleteError)
        toast.error(getErrorMessage(deleteError, 'Failed to delete folder'))
        throw deleteError
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps -- ref-backed options and mutation flags are read at call time
    },
    [workspaceId, setCurrentFolderId]
  )

  const toggleFolderPin = useCallback(
    (folder: KnowledgeFolder) => {
      const mutation = pinnedFolderIds.has(folder.id) ? unpinItem : pinItem
      mutation.mutate({ workspaceId, resourceType: 'folder', resourceId: folder.id })
      closeMenu()
      // eslint-disable-next-line react-hooks/exhaustive-deps -- mutation objects are unstable; mutate is stable in v5
    },
    [workspaceId, pinnedFolderIds, pinItem, unpinItem, closeMenu]
  )

  const openFolder = useCallback(
    (folder: KnowledgeFolder) => setCurrentFolderId(folder.id),
    [setCurrentFolderId]
  )

  const copyFolderId = useCallback((folder: KnowledgeFolder) => {
    navigator.clipboard.writeText(folder.id)
  }, [])

  return {
    createFolderInCurrentFolder,
    isCreatingFolder: createFolder.isPending,
    saveFolderName,
    moveFolderTo,
    moveFolderFromMenu,
    confirmDeleteFolder,
    isDeletingFolder: deleteFolder.isPending,
    toggleFolderPin,
    openFolder,
    copyFolderId,
  }
}

export type KnowledgeFolderCommands = ReturnType<typeof useKnowledgeFolderCommands>
