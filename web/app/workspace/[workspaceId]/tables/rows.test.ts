/**
 * @vitest-environment node
 */
import { describe, expect, it, vi } from 'vitest'
import type { TableDefinition } from '@/lib/table'
import { sortResources } from '@/app/workspace/[workspaceId]/components/folders/resource-sort'
import {
  applyListRename,
  buildSortableEntries,
  filterTables,
  type ListRenameState,
  siblingFolders,
  tablesInFolder,
  tableRow,
  toResourceRows,
} from '@/app/workspace/[workspaceId]/tables/rows'
import type { WorkspaceMember } from '@/hooks/queries/workspace'
import type { WorkspaceFolder } from '@/stores/folders/types'

function makeTable(overrides: Partial<TableDefinition> & { id: string }): TableDefinition {
  return {
    name: overrides.id,
    schema: { columns: [{ id: 'c1', name: 'name', type: 'string' }] },
    rowCount: 0,
    maxRows: 1000,
    workspaceId: 'ws-1',
    folderId: null,
    createdBy: 'user-1',
    locks: {},
    createdAt: new Date('2026-01-01T00:00:00Z'),
    updatedAt: new Date('2026-01-02T00:00:00Z'),
    ...overrides,
  } as TableDefinition
}

function makeFolder(
  overrides: Partial<WorkspaceFolder> & { id: string }
): WorkspaceFolder {
  return {
    resourceType: 'table',
    name: overrides.id,
    userId: 'user-1',
    workspaceId: 'ws-1',
    parentId: null,
    locked: false,
    sortOrder: 0,
    createdAt: new Date('2026-01-01T00:00:00Z'),
    updatedAt: new Date('2026-01-01T00:00:00Z'),
    ...overrides,
  }
}

const MEMBERS = new Map<string, WorkspaceMember>([
  ['user-1', { userId: 'user-1', name: 'Ada', image: null } as WorkspaceMember],
])

const NO_FILTERS = { query: '', rowCountFilter: [], ownerFilter: [] }

describe('tablesInFolder', () => {
  it('keeps only tables directly in the open folder', () => {
    const tables = [
      makeTable({ id: 'root-table', folderId: null }),
      makeTable({ id: 'foldered', folderId: 'f1' }),
    ]
    const folderById = new Map([['f1', makeFolder({ id: 'f1' })]])

    const atRoot = tablesInFolder(tables, {
      currentFolderId: null,
      folderById,
      foldersResolved: true,
    })
    expect(atRoot.map((t) => t.id)).toEqual(['root-table'])

    const inFolder = tablesInFolder(tables, {
      currentFolderId: 'f1',
      folderById,
      foldersResolved: true,
    })
    expect(inFolder.map((t) => t.id)).toEqual(['foldered'])
  })

  it('falls a table with a vanished folderId back to the root once folders are resolved', () => {
    const tables = [makeTable({ id: 'orphan', folderId: 'gone' })]
    const resolved = tablesInFolder(tables, {
      currentFolderId: null,
      folderById: new Map(),
      foldersResolved: true,
    })
    expect(resolved.map((t) => t.id)).toEqual(['orphan'])
  })

  it('hides an orphaned table rather than guessing while the folder index is unresolved', () => {
    const tables = [makeTable({ id: 'orphan', folderId: 'gone' })]
    const unresolved = tablesInFolder(tables, {
      currentFolderId: null,
      folderById: new Map(),
      foldersResolved: false,
    })
    expect(unresolved).toEqual([])
  })
})

describe('filterTables', () => {
  const tables = [
    makeTable({ id: 'Leads', name: 'Leads', rowCount: 0, createdBy: 'user-1' }),
    makeTable({ id: 'Deals', name: 'Deals', rowCount: 50, createdBy: 'user-2' }),
    makeTable({ id: 'Events', name: 'Events', rowCount: 500, createdBy: 'user-1' }),
  ]

  it('matches the query case-insensitively against the name', () => {
    expect(filterTables(tables, { ...NO_FILTERS, query: ' lead ' }).map((t) => t.id)).toEqual([
      'Leads',
    ])
  })

  it('filters by row-count buckets', () => {
    expect(
      filterTables(tables, { ...NO_FILTERS, rowCountFilter: ['empty'] }).map((t) => t.id)
    ).toEqual(['Leads'])
    expect(
      filterTables(tables, { ...NO_FILTERS, rowCountFilter: ['small'] }).map((t) => t.id)
    ).toEqual(['Deals'])
    expect(
      filterTables(tables, { ...NO_FILTERS, rowCountFilter: ['large'] }).map((t) => t.id)
    ).toEqual(['Events'])
    expect(
      filterTables(tables, { ...NO_FILTERS, rowCountFilter: ['empty', 'large'] }).map((t) => t.id)
    ).toEqual(['Leads', 'Events'])
  })

  it('filters by owner and combines with the other filters', () => {
    expect(
      filterTables(tables, { ...NO_FILTERS, ownerFilter: ['user-1'] }).map((t) => t.id)
    ).toEqual(['Leads', 'Events'])
    expect(
      filterTables(tables, {
        query: 'e',
        rowCountFilter: ['small'],
        ownerFilter: ['user-2'],
      }).map((t) => t.id)
    ).toEqual(['Deals'])
  })
})

describe('siblingFolders', () => {
  const folders = [
    makeFolder({ id: 'a', name: 'Reports', parentId: null }),
    makeFolder({ id: 'b', name: 'Archive', parentId: null }),
    makeFolder({ id: 'c', name: 'Nested', parentId: 'a' }),
  ]

  it('keeps only the direct children of the open folder', () => {
    expect(siblingFolders(folders, null, '').map((f) => f.id)).toEqual(['a', 'b'])
    expect(siblingFolders(folders, 'a', '').map((f) => f.id)).toEqual(['c'])
  })

  it('narrows siblings by the search term', () => {
    expect(siblingFolders(folders, null, 'repo').map((f) => f.id)).toEqual(['a'])
  })
})

describe('buildSortableEntries', () => {
  it('decorates every row with its pinned flag and a column-typed sort key', () => {
    const folder = makeFolder({ id: 'f1', name: 'Reports' })
    const table = makeTable({ id: 't1', name: 'Leads', rowCount: 7, folderId: 'f1' })

    const byName = buildSortableEntries({
      folders: [folder],
      tables: [table],
      sortColumn: 'name',
      membersById: MEMBERS,
      pinnedFolderIds: new Set(['f1']),
      pinnedTableIds: new Set(),
    })
    expect(byName).toHaveLength(2)
    expect(byName[0]).toMatchObject({ item: { kind: 'folder' }, pinned: true, key: 'Reports' })
    expect(byName[1]).toMatchObject({ item: { kind: 'table' }, pinned: false, key: 'Leads' })

    // Folders carry no column/row count — `null` keys land them last in both directions.
    const byRows = buildSortableEntries({
      folders: [folder],
      tables: [table],
      sortColumn: 'rows',
      membersById: MEMBERS,
      pinnedFolderIds: new Set(),
      pinnedTableIds: new Set(),
    })
    // Entries are built folders-first; folders carry no column/row count, so their `null`
    // keys land them last in both sort directions.
    expect(byRows[0].key).toBeNull()
    expect(byRows[1].key).toBe(7)
  })

  it('resolves the owner sort key through the member map and tolerates unknown users', () => {
    const known = makeTable({ id: 't1', createdBy: 'user-1' })
    const stranger = makeTable({ id: 't2', createdBy: 'user-missing' })

    const entries = buildSortableEntries({
      folders: [],
      tables: [known, stranger],
      sortColumn: 'owner',
      membersById: MEMBERS,
      pinnedFolderIds: new Set(),
      pinnedTableIds: new Set(),
    })
    expect(entries[0].key).toBe('Ada')
    expect(entries[1].key).toBeNull()
  })

  it('sorts pinned rows to the top as one list', () => {
    const table = makeTable({ id: 't1', name: 'Leads', updatedAt: new Date('2026-02-01') })
    const folder = makeFolder({ id: 'f1', name: 'Reports', updatedAt: new Date('2026-03-01') })

    const sorted = sortResources(
      buildSortableEntries({
        folders: [folder],
        tables: [table],
        sortColumn: 'updated',
        membersById: MEMBERS,
        pinnedFolderIds: new Set(),
        pinnedTableIds: new Set(['t1']),
      }),
      'desc'
    )
    // The table is older, but its pin outranks the folder's newer timestamp.
    expect(sorted.map((entry) => entry.item.kind)).toEqual(['table', 'folder'])
  })
})

describe('tableRow / toResourceRows', () => {
  it('maps a table to a row with count labels and its pin flag', () => {
    const table = makeTable({
      id: 't1',
      name: 'Leads',
      rowCount: 42,
      schema: { columns: [{ id: 'c1', name: 'name', type: 'string' }] },
    } as Partial<TableDefinition> & { id: string })

    const row = tableRow(table, { pinned: true, membersById: MEMBERS })
    expect(row.id).toBe('t1')
    expect(row.cells.name.label).toBe('Leads')
    expect(row.cells.name.pinned).toBe(true)
    expect(row.cells.columns.label).toBe('1')
    expect(row.cells.rows.label).toBe('42')
    expect(row.cells.owner.label).toBe('Ada')
  })

  it('renders folder entries with the placeholder cells', () => {
    const entries = [
      {
        item: { kind: 'folder' as const, folder: makeFolder({ id: 'f1', name: 'Reports' }) },
        pinned: false,
        name: 'Reports',
        key: 'Reports',
      },
    ]
    const rows = toResourceRows(entries, MEMBERS)
    expect(rows[0].cells.columns.label).toBe('—')
    expect(rows[0].cells.rows.label).toBe('—')
    expect(rows[0].cells.name.label).toBe('Reports')
  })
})

describe('applyListRename', () => {
  const renameBase: ListRenameState = {
    editingId: null,
    editValue: '',
    isSaving: false,
    setEditValue: vi.fn(),
    submitRename: vi.fn(),
    cancelRename: vi.fn(),
  }

  it('returns the rows untouched when no rename session is active', () => {
    const rows = [{ id: 't1', cells: { name: { label: 'Leads' } } }]
    expect(applyListRename(rows as never, renameBase)).toBe(rows)
  })

  it('attaches the editing cell only to the row being renamed', () => {
    const rows = [
      { id: 't1', cells: { name: { label: 'Leads' } } },
      { id: 't2', cells: { name: { label: 'Deals' } } },
    ]
    const renamed = applyListRename(rows as never, {
      ...renameBase,
      editingId: 't2',
      editValue: 'Renamed',
      isSaving: true,
    })
    expect(renamed[0]).toBe(rows[0])
    expect(renamed[1].cells.name.editing).toMatchObject({ value: 'Renamed', disabled: true })
  })
})
