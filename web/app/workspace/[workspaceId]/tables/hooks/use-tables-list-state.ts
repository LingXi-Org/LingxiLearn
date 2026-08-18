'use client'

import { useCallback, useMemo } from 'react'
import { useQueryStates } from 'nuqs'
import type { TableDefinition } from '@/lib/table'
import { SEARCH_DEBOUNCE_MS, type SortDirection } from '@/lib/url-state'
import type { SortableResource } from '@/app/workspace/[workspaceId]/components/folders'
import { sortResources } from '@/app/workspace/[workspaceId]/components/folders'
import {
  buildSortableEntries,
  filterTables,
  siblingFolders,
  type TableResourceItem,
  tablesInFolder,
} from '@/app/workspace/[workspaceId]/tables/rows'
import {
  tablesParsers,
  tablesSortParams,
  tablesUrlKeys,
} from '@/app/workspace/[workspaceId]/tables/search-params'
import type { WorkspaceMember } from '@/hooks/queries/workspace'
import { useDebounce } from '@/hooks/use-debounce'
import { useDebouncedSearchSetter } from '@/hooks/use-debounced-search-setter'
import type { ActiveSort } from '@/hooks/use-url-sort'
import { useUrlSort } from '@/hooks/use-url-sort'
import type { WorkspaceFolder } from '@/stores/folders/types'

export interface UseTablesListStateOptions {
  tables: TableDefinition[]
  folders: WorkspaceFolder[]
  folderById: ReadonlyMap<string, WorkspaceFolder>
  foldersResolved: boolean
  currentFolderId: string | null
  membersById: ReadonlyMap<string, WorkspaceMember>
  pinnedFolderIds: ReadonlySet<string>
  pinnedTableIds: ReadonlySet<string>
}

export interface TablesListState {
  /** Instant nuqs value — controls the search input directly. */
  searchValue: string
  setSearchTerm: (value: string) => void
  rowCountFilter: string[]
  setRowCountFilter: (next: string[]) => void
  ownerFilter: string[]
  setOwnerFilter: (next: string[]) => void
  activeSort: ActiveSort | null
  onSort: (column: string, direction: SortDirection) => void
  onClear: () => void
  /** Folders and tables of the open folder, filtered and sorted as ONE list. */
  sortedEntries: SortableResource<TableResourceItem>[]
}

/**
 * URL-backed view state for the Tables list: search, row-count/owner filters, and sort, plus
 * the derived, filter-applied, sorted entries. Pure presentation of URL state — no mutations,
 * no selection, no CSV; those live in the list actions and the CSV controller.
 */
export function useTablesListState({
  tables,
  folders,
  folderById,
  foldersResolved,
  currentFolderId,
  membersById,
  pinnedFolderIds,
  pinnedTableIds,
}: UseTablesListStateOptions): TablesListState {
  const [{ search: urlSearchTerm, rows: rowCountFilter, owner: ownerFilter }, setTableFilters] =
    useQueryStates(tablesParsers, tablesUrlKeys)

  const {
    sort: sortColumn,
    dir: sortDirection,
    activeSort,
    onSort,
    onClear,
  } = useUrlSort(tablesSortParams, tablesUrlKeys)

  /**
   * The input is controlled directly by the instant nuqs value; only the URL write is
   * debounced. The in-memory filter below still reads a debounced value so it doesn't
   * recompute on every keystroke.
   */
  const setSearchTerm = useDebouncedSearchSetter((value, options) =>
    setTableFilters({ search: value }, options)
  )
  const debouncedSearchTerm = useDebounce(urlSearchTerm, SEARCH_DEBOUNCE_MS)

  const setRowCountFilter = useCallback(
    (next: string[]) => setTableFilters({ rows: next }),
    [setTableFilters]
  )
  const setOwnerFilter = useCallback(
    (next: string[]) => setTableFilters({ owner: next }),
    [setTableFilters]
  )

  const visibleFolders = useMemo(
    () => siblingFolders(folders, currentFolderId, debouncedSearchTerm),
    [folders, currentFolderId, debouncedSearchTerm]
  )

  const filteredTables = useMemo(
    () =>
      filterTables(tablesInFolder(tables, { currentFolderId, folderById, foldersResolved }), {
        query: debouncedSearchTerm,
        rowCountFilter,
        ownerFilter,
      }),
    [
      tables,
      currentFolderId,
      folderById,
      foldersResolved,
      debouncedSearchTerm,
      rowCountFilter,
      ownerFilter,
    ]
  )

  /**
   * Folders and tables sort as ONE list — a folder never outranks a table it ties with, so a
   * pinned table reaches the top of the list rather than the top of the table section.
   */
  const sortedEntries = useMemo(
    () =>
      sortResources(
        buildSortableEntries({
          folders: visibleFolders,
          tables: filteredTables,
          sortColumn,
          membersById,
          pinnedFolderIds,
          pinnedTableIds,
        }),
        sortDirection
      ),
    [
      visibleFolders,
      filteredTables,
      sortColumn,
      sortDirection,
      membersById,
      pinnedFolderIds,
      pinnedTableIds,
    ]
  )

  return {
    searchValue: urlSearchTerm,
    setSearchTerm,
    rowCountFilter,
    setRowCountFilter,
    ownerFilter,
    setOwnerFilter,
    activeSort,
    onSort,
    onClear,
    sortedEntries,
  }
}
