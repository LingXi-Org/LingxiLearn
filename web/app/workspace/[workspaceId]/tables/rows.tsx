import { Columns3, Rows3, Table as TableIcon } from '@/components/ui-kit/icons'
import type { TableDefinition } from '@/lib/table/types'
import type { ResourceRow } from '@/app/workspace/[workspaceId]/components'
import { EMPTY_CELL_PLACEHOLDER } from '@/app/workspace/[workspaceId]/components'
import type { SortableResource } from '@/app/workspace/[workspaceId]/components/folders'
import { folderRow } from '@/app/workspace/[workspaceId]/components/folders'
import { ownerCell } from '@/app/workspace/[workspaceId]/components/resource/components/owner-cell'
import { timeCell } from '@/app/workspace/[workspaceId]/components/resource/components/time-cell'
import type { WorkspaceMember } from '@/hooks/queries/workspace'
import type { WorkspaceFolder } from '@/lib/folders/types'

/** A list row (and the right-clicked row), resolved to the entity it refers to. */
export type TableResourceItem =
  | { kind: 'table'; table: TableDefinition }
  | { kind: 'folder'; folder: WorkspaceFolder }

export interface TableFolderScope {
  currentFolderId: string | null
  folderById: ReadonlyMap<string, WorkspaceFolder>
  foldersResolved: boolean
}

/**
 * The tables sitting directly in the open folder.
 *
 * A `folderId` that no longer names an active folder — restored on its own out of Recently
 * Deleted while its folder stayed archived — would otherwise match no level at all and leave
 * the table unreachable from every view. Fall it back to the root instead — but only once
 * `foldersResolved` says the index is the complete set for THIS workspace. Gating on a
 * loading flag instead would treat an errored fetch, a disabled query, or the previous
 * workspace's cached folders as "no such folder" and drag every foldered table to the root.
 */
export function tablesInFolder(
  tables: TableDefinition[],
  scope: TableFolderScope
): TableDefinition[] {
  return tables.filter((table) => {
    const folderId = table.folderId ?? null
    const effectiveFolderId =
      !scope.foldersResolved || !folderId || scope.folderById.has(folderId) ? folderId : null
    return effectiveFolderId === scope.currentFolderId
  })
}

export interface TableListFilters {
  /** Live search term; matched case-insensitively against the table name. */
  query: string
  /** Row-count buckets: `'empty'`, `'small'` (1–100), `'large'` (101+). */
  rowCountFilter: string[]
  /** Creator user ids. */
  ownerFilter: string[]
}

/**
 * Applies the search term and the row-count/owner filters to the tables of the open folder.
 * Pure over its inputs so the whole pipeline is testable without URL state or a mounted list.
 */
export function filterTables(
  tables: TableDefinition[],
  filters: TableListFilters
): TableDefinition[] {
  const query = filters.query.trim().toLowerCase()
  let result = query ? tables.filter((t) => t.name.toLowerCase().includes(query)) : tables

  if (filters.rowCountFilter.length > 0) {
    result = result.filter((t) => {
      if (filters.rowCountFilter.includes('empty') && t.rowCount === 0) return true
      if (filters.rowCountFilter.includes('small') && t.rowCount >= 1 && t.rowCount <= 100)
        return true
      if (filters.rowCountFilter.includes('large') && t.rowCount > 100) return true
      return false
    })
  }
  if (filters.ownerFilter.length > 0) {
    result = result.filter((t) => Boolean(t.createdBy && filters.ownerFilter.includes(t.createdBy)))
  }
  return result
}

/** The folders directly inside `parentId`, optionally narrowed by a search term. */
export function siblingFolders(
  folders: WorkspaceFolder[],
  parentId: string | null,
  query: string
): WorkspaceFolder[] {
  const siblings = folders.filter((folder) => (folder.parentId ?? null) === parentId)
  const needle = query.trim().toLowerCase()
  return needle ? siblings.filter((folder) => folder.name.toLowerCase().includes(needle)) : siblings
}

export interface BuildSortableEntriesOptions {
  folders: WorkspaceFolder[]
  tables: TableDefinition[]
  sortColumn: string
  membersById: ReadonlyMap<string, WorkspaceMember>
  pinnedFolderIds: ReadonlySet<string>
  pinnedTableIds: ReadonlySet<string>
}

/**
 * Decorates folders and tables for {@link sortResources}: each row's sort key + pinned flag is
 * computed ONCE (O(N)) so the comparator never re-runs Date parsing or member lookups per
 * comparison. Folders carry no column or row count, so those keys are `null` and land the
 * folders last in both directions — matching the em-dash they show in those cells.
 */
export function buildSortableEntries(
  options: BuildSortableEntriesOptions
): SortableResource<TableResourceItem>[] {
  const { folders, tables, sortColumn, membersById, pinnedFolderIds, pinnedTableIds } = options
  const entries: SortableResource<TableResourceItem>[] = []

  for (const folder of folders) {
    entries.push({
      item: { kind: 'folder', folder },
      pinned: pinnedFolderIds.has(folder.id),
      name: folder.name,
      key:
        sortColumn === 'columns' || sortColumn === 'rows'
          ? null
          : sortColumn === 'created'
            ? new Date(folder.createdAt).getTime()
            : sortColumn === 'updated'
              ? new Date(folder.updatedAt).getTime()
              : sortColumn === 'owner'
                ? (membersById.get(folder.userId)?.name ?? null)
                : folder.name,
    })
  }

  for (const table of tables) {
    entries.push({
      item: { kind: 'table', table },
      pinned: pinnedTableIds.has(table.id),
      name: table.name,
      key:
        sortColumn === 'columns'
          ? table.schema.columns.length
          : sortColumn === 'rows'
            ? table.rowCount
            : sortColumn === 'created'
              ? new Date(table.createdAt).getTime()
              : sortColumn === 'updated'
                ? new Date(table.updatedAt).getTime()
                : sortColumn === 'owner'
                  ? table.createdBy
                    ? (membersById.get(table.createdBy)?.name ?? null)
                    : null
                  : table.name,
    })
  }

  return entries
}

export interface TableRowOptions {
  pinned: boolean
  membersById: ReadonlyMap<string, WorkspaceMember>
}

/** Pure `table → ResourceRow` mapper for the Tables list. */
export function tableRow(table: TableDefinition, options: TableRowOptions): ResourceRow {
  return {
    id: table.id,
    cells: {
      name: {
        icon: <TableIcon className='size-[14px]' />,
        label: table.name,
        pinned: options.pinned,
      },
      columns: {
        icon: <Columns3 className='size-[14px]' />,
        label: String(table.schema.columns.length),
      },
      rows: {
        icon: <Rows3 className='size-[14px]' />,
        label: String(table.rowCount),
      },
      created: timeCell(table.createdAt),
      owner: table.createdBy
        ? ownerCell(table.createdBy, options.membersById)
        : { label: EMPTY_CELL_PLACEHOLDER },
      updated: timeCell(table.updatedAt),
    },
  }
}

/**
 * Maps sorted entries to list rows — folders via the shared {@link folderRow}, tables via
 * {@link tableRow}. Pure presentation mapping: entity in, `ResourceRow` out.
 */
export function toResourceRows(
  entries: SortableResource<TableResourceItem>[],
  membersById: ReadonlyMap<string, WorkspaceMember>
): ResourceRow[] {
  return entries.map(({ item, pinned }): ResourceRow => {
    if (item.kind === 'folder') {
      return folderRow(item.folder, {
        pinned,
        cells: {
          columns: { label: EMPTY_CELL_PLACEHOLDER },
          rows: { label: EMPTY_CELL_PLACEHOLDER },
          created: timeCell(item.folder.createdAt),
          owner: ownerCell(item.folder.userId, membersById),
          updated: timeCell(item.folder.updatedAt),
        },
      })
    }
    return tableRow(item.table, { pinned, membersById })
  })
}

/** The subset of an inline-rename session the rows need to render the editing cell. */
export interface ListRenameState {
  editingId: string | null
  editValue: string
  isSaving: boolean
  setEditValue: (value: string) => void
  submitRename: () => void
  cancelRename: () => void
}

/**
 * Layers the active rename session on top of built rows rather than folding it in, so a
 * keystroke in the rename field rebuilds one cell instead of every row's cells.
 */
export function applyListRename(rows: ResourceRow[], rename: ListRenameState): ResourceRow[] {
  if (!rename.editingId) return rows
  return rows.map((row) => {
    if (row.id !== rename.editingId) return row
    return {
      ...row,
      cells: {
        ...row.cells,
        name: {
          ...row.cells.name,
          editing: {
            value: rename.editValue,
            onChange: rename.setEditValue,
            onSubmit: rename.submitRename,
            onCancel: rename.cancelRename,
            disabled: rename.isSaving,
          },
        },
      },
    }
  })
}
