'use client'

import { useMemo } from 'react'
import type { WorkspaceFileRecord } from '@/lib/uploads/contexts/workspace'
import type { SortDirection } from '@/lib/url-state'
import type { ResourceRow } from '@/app/workspace/[workspaceId]/components'
import { sortResources } from '@/app/workspace/[workspaceId]/components/folders'
import {
  type FilesListFilters,
  listFolderFiles,
  listFolderSiblings,
  toSearchNeedle,
} from '@/app/workspace/[workspaceId]/files/lib/file-filters'
import { mapFileEntriesToRows } from '@/app/workspace/[workspaceId]/files/lib/file-rows'
import {
  buildSortableFileEntries,
  type FileSortColumn,
} from '@/app/workspace/[workspaceId]/files/lib/file-sort'
import type { WorkspaceMember } from '@/hooks/queries/workspace'
import type { WorkspaceFileFolderApi } from '@/hooks/queries/workspace-file-folders'

/** The inline-rename fields the row overlay binds to, shaped like `useInlineRename`'s return. */
export interface RowRenameState {
  editingId: string | null
  editValue: string
  setEditValue: (value: string) => void
  submitRename: () => void | Promise<void>
  cancelRename: () => void
  isSaving: boolean
}

export interface UseFilesRowsParams {
  files: WorkspaceFileRecord[]
  folders: WorkspaceFileFolderApi[]
  currentFolderId: string | null
  /** The raw (instant) search input; the pipeline debounces nothing itself. */
  debouncedSearchTerm: string
  filters: FilesListFilters
  sortColumn: FileSortColumn
  sortDirection: SortDirection
  pinnedFileIds: ReadonlySet<string>
  pinnedFolderIds: ReadonlySet<string>
  membersById: Map<string, WorkspaceMember>
  folderSizeMap: Map<string, number>
  listRename: RowRenameState
}

/**
 * The list controller's row pipeline: folder/file scoping → search + URL filters → unified
 * sort → `ResourceRow` mapping → the inline-rename overlay. Every stage delegates to a pure
 * domain function, so this hook is memoization glue only.
 */
export function useFilesRows({
  files,
  folders,
  currentFolderId,
  debouncedSearchTerm,
  filters,
  sortColumn,
  sortDirection,
  pinnedFileIds,
  pinnedFolderIds,
  membersById,
  folderSizeMap,
  listRename,
}: UseFilesRowsParams) {
  const needle = useMemo(() => toSearchNeedle(debouncedSearchTerm), [debouncedSearchTerm])

  const visibleFolders = useMemo(
    () => listFolderSiblings(folders, currentFolderId, needle),
    [folders, currentFolderId, needle]
  )

  const filteredFiles = useMemo(
    () => listFolderFiles(files, currentFolderId, needle, filters),
    [files, currentFolderId, needle, filters]
  )

  const sortedEntries = useMemo(
    () =>
      sortResources(
        buildSortableFileEntries({
          visibleFolders,
          filteredFiles,
          sortColumn,
          pinnedFolderIds,
          pinnedFileIds,
          ctx: { membersById, folderSizeMap },
        }),
        sortDirection
      ),
    [
      visibleFolders,
      filteredFiles,
      sortColumn,
      sortDirection,
      pinnedFolderIds,
      pinnedFileIds,
      membersById,
      folderSizeMap,
    ]
  )

  const baseRows = useMemo(
    () => mapFileEntriesToRows(sortedEntries, { membersById, folderSizeMap }),
    [sortedEntries, membersById, folderSizeMap]
  )

  const rows: ResourceRow[] = useMemo(() => {
    if (!listRename.editingId) return baseRows
    return baseRows.map((row) => {
      if (row.id !== listRename.editingId) return row
      return {
        ...row,
        cells: {
          ...row.cells,
          name: {
            ...row.cells.name,
            editing: {
              value: listRename.editValue,
              onChange: listRename.setEditValue,
              onSubmit: listRename.submitRename,
              onCancel: listRename.cancelRename,
              disabled: listRename.isSaving,
            },
          },
        },
      }
    })
  }, [
    baseRows,
    listRename.editingId,
    listRename.editValue,
    listRename.setEditValue,
    listRename.submitRename,
    listRename.cancelRename,
    listRename.isSaving,
  ])

  const visibleRowIds = useMemo(() => rows.map((row) => row.id), [rows])

  return { rows, visibleRowIds }
}
