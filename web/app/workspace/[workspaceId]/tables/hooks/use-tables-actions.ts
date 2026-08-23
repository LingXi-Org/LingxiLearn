'use client'

import { useCallback, useMemo, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from '@/components/ui-kit'
import { createLogger } from '@/lib/logger'
import { generateUniqueTableName } from '@/lib/table/constants'
import type { TableDefinition } from '@/lib/table/types'
import { getErrorMessage } from '@/lib/utils/errors'
import type { RowDragDropConfig } from '@/app/workspace/[workspaceId]/components'
import type { MoveOptionNode } from '@/app/workspace/[workspaceId]/components/folders'
import {
  buildDescendantIndex,
  buildMoveOptions,
  FOLDERED_RESOURCE_HEADERS,
  folderRowId,
  nextUntitledFolderName,
  parseFolderedRowId,
  parseMoveOptionValue,
  useFolderRowDragDrop,
} from '@/app/workspace/[workspaceId]/components/folders'
import { useCreateFolder, useDeleteFolderMutation, useUpdateFolder } from '@/hooks/queries/folders'
import { usePinItem, useUnpinItem } from '@/hooks/queries/pinned-items'
import {
  useCreateTable,
  useDeleteTable,
  useMoveTable,
  useRenameTable,
} from '@/hooks/queries/tables'
import { useInlineRename } from '@/hooks/use-inline-rename'
import type { WorkspaceFolder } from '@/stores/folders/types'

const logger = createLogger('TablesActions')

/** Root label for the "move to workspace root" destination. */
const ROOT_LABEL = FOLDERED_RESOURCE_HEADERS.table.rootLabel

export interface UseTablesActionsOptions {
  workspaceId: string
  canEdit: boolean
  tables: TableDefinition[]
  folders: WorkspaceFolder[]
  folderById: ReadonlyMap<string, WorkspaceFolder>
  currentFolderId: string | null
  setCurrentFolderId: (folderId: string | null) => void
  pinnedFolderIds: ReadonlySet<string>
  pinnedTableIds: ReadonlySet<string>
  /** Sets the live search term — called with `''` so a brand-new "New folder" is visible to be renamed. */
  clearSearch: (value: string) => void
}

export interface TablesActions {
  /** Rename session multiplexed over table and folder rows. */
  listRename: ReturnType<typeof useInlineRename>
  /** Rename session bound to the open folder's breadcrumb crumb. */
  breadcrumbRename: ReturnType<typeof useInlineRename>
  startFolderRename: (folder: WorkspaceFolder) => void
  createTable: () => Promise<void>
  createFolder: () => Promise<void>
  isCreatingTable: boolean
  isCreatingFolder: boolean
  deleteTable: (tableId: string) => Promise<void>
  deleteFolder: (folder: WorkspaceFolder) => Promise<void>
  isDeletingTable: boolean
  isDeletingFolder: boolean
  /** Applies a "Move to" menu option to a table; no-op when it already sits there. */
  moveTableTo: (optionValue: string, table: TableDefinition) => void
  moveFolderTo: (folderId: string, parentId: string | null) => void
  /** Applies a "Move to" menu option to a folder; no-op when it already sits there. */
  moveFolderByOption: (optionValue: string, folder: WorkspaceFolder) => void
  togglePin: (target: { resourceType: 'table' | 'folder'; id: string }) => void
  tableMoveOptions: MoveOptionNode[]
  /** Move options for a folder row, excluding itself and its own subtree. */
  folderMoveOptions: (folder: WorkspaceFolder | null) => MoveOptionNode[]
  rowDragDrop: RowDragDropConfig
}

/**
 * Table and folder mutations for the Tables list: create/delete/rename/move/pin and row
 * drag-drop. Reads and writes the table/folder domain only — URL view state lives in
 * `useTablesListState`, CSV flows in the CSV controller, neither of which this hook touches.
 */
export function useTablesActions({
  workspaceId,
  canEdit,
  tables,
  folders,
  folderById,
  currentFolderId,
  setCurrentFolderId,
  pinnedFolderIds,
  pinnedTableIds,
  clearSearch,
}: UseTablesActionsOptions): TablesActions {
  const router = useRouter()

  const deleteTable = useDeleteTable(workspaceId)
  const renameTable = useRenameTable(workspaceId)
  const createTable = useCreateTable(workspaceId)
  const moveTable = useMoveTable(workspaceId)
  const createFolder = useCreateFolder()
  const updateFolder = useUpdateFolder()
  const deleteFolderMutation = useDeleteFolderMutation()
  const pinItem = usePinItem()
  const unpinItem = useUnpinItem()

  const tablesRef = useRef(tables)
  tablesRef.current = tables

  /**
   * One rename session multiplexed over both row kinds — the shared `Resource` table has a
   * single editing cell, so the id it carries has to resolve to either a folder or a table.
   * Both mutations toast their own failure; the hook restores the original name and keeps the
   * field open.
   */
  const listRename = useInlineRename({
    onSave: (rowId, name) => {
      const parsed = parseFolderedRowId(rowId)
      if (parsed.kind === 'folder') {
        return updateFolder
          .mutateAsync({
            workspaceId,
            resourceType: 'table',
            id: parsed.id,
            updates: { name },
          })
          .catch((err: unknown) => {
            toast.error(getErrorMessage(err, 'Failed to rename folder'), { duration: 5000 })
            throw err
          })
      }
      return renameTable.mutateAsync({ tableId: parsed.id, name })
    },
  })

  const breadcrumbRename = useInlineRename({
    onSave: (folderId, name) =>
      updateFolder
        .mutateAsync({ workspaceId, resourceType: 'table', id: folderId, updates: { name } })
        .catch((err: unknown) => {
          toast.error(getErrorMessage(err, 'Failed to rename folder'), { duration: 5000 })
          throw err
        }),
  })

  const startFolderRename = useCallback(
    (folder: WorkspaceFolder) => listRename.startRename(folderRowId(folder.id), folder.name),
    [listRename.startRename]
  )

  // `mutateAsync` is stable in TanStack Query v5 — extract it so the callback
  // can list it as a dep instead of the unstable mutation object.
  const createTableAsync = createTable.mutateAsync
  const handleCreateTable = useCallback(async () => {
    const existingNames = tablesRef.current.map((t) => t.name)
    const name = generateUniqueTableName(existingNames)
    try {
      const result = await createTableAsync({
        name,
        folderId: currentFolderId,
        schema: {
          columns: [{ name: 'name', type: 'string' }],
        },
        initialRowCount: 1,
      })
      const tableId = result?.data?.table?.id
      if (tableId) {
        router.push(`/workspace/${workspaceId}/tables/${tableId}`)
      }
    } catch (err) {
      logger.error('Failed to create table:', err)
    }
  }, [router, workspaceId, currentFolderId, createTableAsync])

  const createFolderAsync = createFolder.mutateAsync
  const handleCreateFolder = useCallback(async () => {
    try {
      const folder = await createFolderAsync({
        workspaceId,
        resourceType: 'table',
        name: nextUntitledFolderName(folders, currentFolderId),
        parentId: currentFolderId ?? undefined,
      })
      /**
       * A live search term filters the folder list too, so a brand-new "New folder" would not
       * match it — the row never renders, the rename field never appears, and the create reads
       * as a no-op even though it succeeded. Clear the search so the thing just created is on
       * screen to be named.
       */
      clearSearch('')
      startFolderRename(folder)
    } catch (err) {
      logger.error('Failed to create folder:', err)
      toast.error(getErrorMessage(err, 'Failed to create folder'), { duration: 5000 })
    }
  }, [workspaceId, folders, currentFolderId, createFolderAsync, clearSearch, startFolderRename])

  const handleDeleteTable = useCallback(
    async (tableId: string) => {
      try {
        await deleteTable.mutateAsync(tableId)
      } catch (err) {
        logger.error('Failed to delete table:', err)
        // Rethrown so the caller keeps its confirm dialog open on failure.
        throw err
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mutation objects are unstable; mutateAsync is stable in v5
    [deleteTable.mutateAsync]
  )

  const handleDeleteFolder = useCallback(
    async (folder: WorkspaceFolder) => {
      try {
        await deleteFolderMutation.mutateAsync({
          workspaceId,
          resourceType: 'table',
          id: folder.id,
        })
        // The open folder just disappeared — fall back to its parent rather than
        // leaving a `?folderId=` pointing at an archived folder.
        if (currentFolderId === folder.id) {
          setCurrentFolderId(folder.parentId)
        }
      } catch (err) {
        logger.error('Failed to delete folder:', err)
        toast.error(getErrorMessage(err, 'Failed to delete folder'), { duration: 5000 })
        throw err
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mutation objects are unstable; mutateAsync is stable in v5
    [workspaceId, currentFolderId, setCurrentFolderId, deleteFolderMutation.mutateAsync]
  )

  const handleMoveTable = useCallback(
    (optionValue: string, table: TableDefinition) => {
      const folderId = parseMoveOptionValue(optionValue)
      /**
       * Placement is re-read from the live list rather than trusted from the caller's table,
       * which is a snapshot taken when the menu opened. A refetch or a concurrent move since
       * then would make the no-op check compare against a stale location and skip a write the
       * user asked for. Matches the knowledge-base move.
       */
      const current = tablesRef.current.find((t) => t.id === table.id) ?? table
      if ((current.folderId ?? null) === folderId) return
      moveTable.mutate({ tableId: table.id, folderId })
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mutation objects are unstable; mutate is stable in v5
    []
  )

  /** Shared by the "Move to" submenu and by dropping a folder row onto another folder. */
  const moveFolderTo = useCallback(
    (folderId: string, parentId: string | null) => {
      updateFolder.mutate(
        { workspaceId, resourceType: 'table', id: folderId, updates: { parentId } },
        {
          onError: (err) =>
            toast.error(getErrorMessage(err, 'Failed to move folder'), { duration: 5000 }),
        }
      )
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mutation objects are unstable; mutate is stable in v5
    [workspaceId]
  )

  const handleMoveFolderByOption = useCallback(
    (optionValue: string, folder: WorkspaceFolder) => {
      const parentId = parseMoveOptionValue(optionValue)
      // Same reasoning as `handleMoveTable`: compare against the live row, not the snapshot.
      const current = folderById.get(folder.id) ?? folder
      if ((current.parentId ?? null) !== parentId) moveFolderTo(folder.id, parentId)
    },
    [folderById, moveFolderTo]
  )

  const handleTogglePin = useCallback(
    ({ resourceType, id }: { resourceType: 'table' | 'folder'; id: string }) => {
      const pinned = resourceType === 'folder' ? pinnedFolderIds.has(id) : pinnedTableIds.has(id)
      const mutation = pinned ? unpinItem : pinItem
      mutation.mutate({ workspaceId, resourceType, resourceId: id })
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mutation objects are unstable; mutate is stable in v5
    [workspaceId, pinnedFolderIds, pinnedTableIds]
  )

  /**
   * Descendants of every folder, so a move destination that sits inside the moved folder can
   * be excluded — reparenting a folder under its own child would close a cycle (the server
   * rejects it; this keeps it out of the menu, and out of a valid drop target, entirely).
   */
  const descendantFolderIds = useMemo(() => buildDescendantIndex(folders), [folders])

  const tableMoveOptions: MoveOptionNode[] = useMemo(
    () => buildMoveOptions({ folders, rootLabel: ROOT_LABEL }),
    [folders]
  )

  const folderMoveOptions = useCallback(
    (folder: WorkspaceFolder | null): MoveOptionNode[] => {
      if (!folder) return []
      const excluded = new Set<string>([folder.id])
      for (const id of descendantFolderIds.get(folder.id) ?? []) excluded.add(id)
      return buildMoveOptions({ folders, rootLabel: ROOT_LABEL, excludedFolderIds: excluded })
    },
    [folders, descendantFolderIds]
  )

  const rowDragDrop = useFolderRowDragDrop({
    canEdit,
    editingRowId: listRename.editingId,
    descendantsByFolderId: descendantFolderIds,
    getFolderParentId: (folderId) => folderById.get(folderId)?.parentId ?? null,
    getResourceFolderId: (tableId) =>
      tablesRef.current.find((table) => table.id === tableId)?.folderId ?? null,
    getRowLabel: (rowId) => {
      const parsed = parseFolderedRowId(rowId)
      return parsed.kind === 'folder'
        ? (folderById.get(parsed.id)?.name ?? 'Folder')
        : (tablesRef.current.find((table) => table.id === parsed.id)?.name ?? 'Table')
    },
    onMoveFolder: (folderId, targetFolderId) => moveFolderTo(folderId, targetFolderId),
    onMoveResource: (tableId, targetFolderId) =>
      moveTable.mutate({ tableId, folderId: targetFolderId }),
  })

  return {
    listRename,
    breadcrumbRename,
    startFolderRename,
    createTable: handleCreateTable,
    createFolder: handleCreateFolder,
    isCreatingTable: createTable.isPending,
    isCreatingFolder: createFolder.isPending,
    deleteTable: handleDeleteTable,
    deleteFolder: handleDeleteFolder,
    isDeletingTable: deleteTable.isPending,
    isDeletingFolder: deleteFolderMutation.isPending,
    moveTableTo: handleMoveTable,
    moveFolderTo,
    moveFolderByOption: handleMoveFolderByOption,
    togglePin: handleTogglePin,
    tableMoveOptions,
    folderMoveOptions,
    rowDragDrop,
  }
}
