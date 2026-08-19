/**
 * @vitest-environment node
 *
 * Interaction-semantics regression for the Tables list commands: the extracted controller
 * runs against mocked React/query layers — never mounting the Resource list — proving
 * create/delete/rename/move/pin and drag-drop keep their pre-split behavior.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { TableDefinition } from '@/lib/table'
import {
  folderRowId,
  ROOT_MOVE_OPTION_VALUE,
} from '@/app/workspace/[workspaceId]/components/folders'
import type { WorkspaceFolder } from '@/stores/folders/types'

const { routerPush, toastError, startRenameSpy, renameSessions, mutations } = vi.hoisted(() => ({
  routerPush: vi.fn(),
  toastError: vi.fn(),
  startRenameSpy: vi.fn(),
  /** The `onSave` prop of each `useInlineRename` call, in call order (list, breadcrumb). */
  renameSessions: [] as Array<{
    onSave: (id: string, name: string) => undefined | Promise<unknown>
  }>,
  mutations: {
    createTableAsync: vi.fn(),
    deleteTableAsync: vi.fn(),
    renameTableAsync: vi.fn(),
    moveTableMutate: vi.fn(),
    createFolderAsync: vi.fn(),
    updateFolderMutate: vi.fn(),
    updateFolderAsync: vi.fn(),
    deleteFolderAsync: vi.fn(),
    pinMutate: vi.fn(),
    unpinMutate: vi.fn(),
  },
}))

vi.mock('react', () => ({
  // `memo` is called at module scope by components pulled in through the folders barrel.
  memo: (component: unknown) => component,
  useCallback: (fn: unknown) => fn,
  useMemo: (fn: () => unknown) => fn(),
  useRef: (init: unknown) => ({ current: init }),
  useState: (init: unknown) => [typeof init === 'function' ? init() : init, vi.fn()],
  useEffect: () => {},
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: routerPush, replace: vi.fn(), refresh: vi.fn() }),
}))

vi.mock('@sim/emcn', () => ({
  toast: { success: vi.fn(), error: (...args: unknown[]) => toastError(...args) },
}))

vi.mock('@/lib/logger', () => ({
  createLogger: () => ({ debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() }),
}))

vi.mock('@/hooks/use-inline-rename', () => ({
  useInlineRename: (props: { onSave: (id: string, name: string) => undefined | Promise<unknown> }) => {
    renameSessions.push(props)
    return {
      editingId: null,
      editValue: '',
      isSaving: false,
      setEditValue: vi.fn(),
      startRename: startRenameSpy,
      submitRename: vi.fn(),
      cancelRename: vi.fn(),
    }
  },
}))

vi.mock('@/hooks/queries/tables', () => ({
  useCreateTable: () => ({ mutateAsync: mutations.createTableAsync, isPending: false }),
  useDeleteTable: () => ({ mutateAsync: mutations.deleteTableAsync, isPending: false }),
  useRenameTable: () => ({ mutateAsync: mutations.renameTableAsync, isPending: false }),
  useMoveTable: () => ({ mutate: mutations.moveTableMutate, isPending: false }),
}))

vi.mock('@/hooks/queries/folders', () => ({
  // Loaded transitively through the folders barrel; the actions hook itself never calls it.
  useFolders: () => ({ data: [], isSuccess: true, isPlaceholderData: false }),
  useCreateFolder: () => ({ mutateAsync: mutations.createFolderAsync, isPending: false }),
  useUpdateFolder: () => ({
    mutate: mutations.updateFolderMutate,
    mutateAsync: mutations.updateFolderAsync,
    isPending: false,
  }),
  useDeleteFolderMutation: () => ({
    mutateAsync: mutations.deleteFolderAsync,
    isPending: false,
  }),
}))

vi.mock('@/hooks/queries/pinned-items', () => ({
  usePinItem: () => ({ mutate: mutations.pinMutate }),
  useUnpinItem: () => ({ mutate: mutations.unpinMutate }),
}))

import {
  useTablesActions,
  type UseTablesActionsOptions,
} from '@/app/workspace/[workspaceId]/tables/hooks/use-tables-actions'

const WORKSPACE_ID = 'ws-1'

function makeTable(overrides: Partial<TableDefinition> & { id: string }): TableDefinition {
  return {
    name: overrides.id,
    schema: { columns: [{ id: 'c1', name: 'name', type: 'string' }] },
    rowCount: 0,
    maxRows: 1000,
    workspaceId: WORKSPACE_ID,
    folderId: null,
    createdBy: 'user-1',
    locks: {},
    createdAt: new Date('2026-01-01T00:00:00Z'),
    updatedAt: new Date('2026-01-02T00:00:00Z'),
    ...overrides,
  } as TableDefinition
}

function makeFolder(overrides: Partial<WorkspaceFolder> & { id: string }): WorkspaceFolder {
  return {
    resourceType: 'table',
    name: overrides.id,
    userId: 'user-1',
    workspaceId: WORKSPACE_ID,
    parentId: null,
    locked: false,
    sortOrder: 0,
    createdAt: new Date('2026-01-01T00:00:00Z'),
    updatedAt: new Date('2026-01-01T00:00:00Z'),
    ...overrides,
  }
}

function makeActions(overrides: Partial<UseTablesActionsOptions> = {}) {
  const options: UseTablesActionsOptions = {
    workspaceId: WORKSPACE_ID,
    canEdit: true,
    tables: [],
    folders: [],
    folderById: new Map(),
    currentFolderId: null,
    setCurrentFolderId: vi.fn(),
    pinnedFolderIds: new Set(),
    pinnedTableIds: new Set(),
    clearSearch: vi.fn(),
    ...overrides,
  }
  return { options, actions: useTablesActions(options) }
}

/** A drop event carrying the given source row in the drag payload. */
function dropEvent(sourceRowId: string) {
  return {
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
    dataTransfer: {
      getData: (mime: string) => (mime === 'application/x-sim-foldered-row' ? sourceRowId : ''),
    },
  } as never
}

beforeEach(() => {
  vi.clearAllMocks()
  renameSessions.length = 0
})

describe('move commands', () => {
  it('moves a table to the chosen folder, reading the live row rather than the snapshot', () => {
    const live = makeTable({ id: 't1', folderId: 'f1' })
    const { actions } = makeActions({ tables: [live] })

    // The menu snapshot predates a concurrent move into f1 — choosing f1 must be a no-op.
    actions.moveTableTo('f1', { ...live, folderId: null })
    expect(mutations.moveTableMutate).not.toHaveBeenCalled()

    actions.moveTableTo(ROOT_MOVE_OPTION_VALUE, live)
    expect(mutations.moveTableMutate).toHaveBeenCalledWith({ tableId: 't1', folderId: null })
  })

  it('moves a folder only when the destination actually differs from its live parent', () => {
    const folder = makeFolder({ id: 'f2', parentId: 'f1' })
    const { actions } = makeActions({
      folders: [folder],
      folderById: new Map([[folder.id, folder]]),
    })

    actions.moveFolderByOption('f1', folder)
    expect(mutations.updateFolderMutate).not.toHaveBeenCalled()

    actions.moveFolderByOption(ROOT_MOVE_OPTION_VALUE, folder)
    expect(mutations.updateFolderMutate).toHaveBeenCalledWith(
      {
        workspaceId: WORKSPACE_ID,
        resourceType: 'table',
        id: 'f2',
        updates: { parentId: null },
      },
      expect.objectContaining({ onError: expect.any(Function) })
    )
  })

  it('excludes the folder itself and its subtree from its own move options', () => {
    const parent = makeFolder({ id: 'f1', parentId: null })
    const child = makeFolder({ id: 'f2', parentId: 'f1' })
    const other = makeFolder({ id: 'f3', parentId: null })
    const { actions } = makeActions({ folders: [parent, child, other] })

    const values = (nodes: { value: string; children: unknown[] }[]): string[] =>
      nodes.flatMap((node) => [
        node.value,
        ...values(node.children as { value: string; children: unknown[] }[]),
      ])
    const offered = values(actions.folderMoveOptions(parent))
    expect(offered).toContain(ROOT_MOVE_OPTION_VALUE)
    expect(offered).toContain('f3')
    expect(offered).not.toContain('f1')
    expect(offered).not.toContain('f2')
  })
})

describe('pin command', () => {
  it('pins an unpinned row and unpins a pinned one, per resource kind', () => {
    const { actions } = makeActions({ pinnedTableIds: new Set(['t1']) })

    actions.togglePin({ resourceType: 'table', id: 't1' })
    expect(mutations.unpinMutate).toHaveBeenCalledWith({
      workspaceId: WORKSPACE_ID,
      resourceType: 'table',
      resourceId: 't1',
    })

    actions.togglePin({ resourceType: 'folder', id: 'f9' })
    expect(mutations.pinMutate).toHaveBeenCalledWith({
      workspaceId: WORKSPACE_ID,
      resourceType: 'folder',
      resourceId: 'f9',
    })
  })
})

describe('delete commands', () => {
  it('rethrows a failed table delete so the confirm dialog stays open', async () => {
    const { actions } = makeActions()
    mutations.deleteTableAsync.mockRejectedValueOnce(new Error('lock conflict'))

    await expect(actions.deleteTable('t1')).rejects.toThrow('lock conflict')
  })

  it('steps out to the parent when the open folder is deleted', async () => {
    const folder = makeFolder({ id: 'f2', parentId: 'f1' })
    const { options, actions } = makeActions({ currentFolderId: 'f2' })
    mutations.deleteFolderAsync.mockResolvedValue({})

    await actions.deleteFolder(folder)

    expect(mutations.deleteFolderAsync).toHaveBeenCalledWith({
      workspaceId: WORKSPACE_ID,
      resourceType: 'table',
      id: 'f2',
    })
    expect(options.setCurrentFolderId).toHaveBeenCalledWith('f1')
  })

  it('keeps the location when another folder is deleted, and rethrows failures', async () => {
    const folder = makeFolder({ id: 'f2', parentId: 'f1' })
    const { options, actions } = makeActions({ currentFolderId: 'f9' })
    mutations.deleteFolderAsync.mockResolvedValueOnce({})

    await actions.deleteFolder(folder)
    expect(options.setCurrentFolderId).not.toHaveBeenCalled()

    mutations.deleteFolderAsync.mockRejectedValueOnce(new Error('nope'))
    await expect(actions.deleteFolder(folder)).rejects.toThrow('nope')
    expect(toastError).toHaveBeenCalled()
  })
})

describe('create commands', () => {
  it('creates a table in the open folder and routes to it', async () => {
    const { actions } = makeActions({ currentFolderId: 'f1' })
    mutations.createTableAsync.mockResolvedValue({ data: { table: { id: 't-new' } } })

    await actions.createTable()

    expect(mutations.createTableAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        name: expect.any(String),
        folderId: 'f1',
        schema: { columns: [{ name: 'name', type: 'string' }] },
        initialRowCount: 1,
      })
    )
    expect(routerPush).toHaveBeenCalledWith(`/workspace/${WORKSPACE_ID}/tables/t-new`)
  })

  it('stays put when the table create fails', async () => {
    const { actions } = makeActions()
    mutations.createTableAsync.mockRejectedValueOnce(new Error('limit reached'))

    await actions.createTable()

    expect(routerPush).not.toHaveBeenCalled()
  })

  it('creates a folder, clears the search, and opens the inline rename on its row', async () => {
    const { options, actions } = makeActions({ currentFolderId: null })
    mutations.createFolderAsync.mockResolvedValue(makeFolder({ id: 'f-new', name: 'New folder' }))

    await actions.createFolder()

    expect(mutations.createFolderAsync).toHaveBeenCalledWith({
      workspaceId: WORKSPACE_ID,
      resourceType: 'table',
      name: 'New folder',
      parentId: undefined,
    })
    expect(options.clearSearch).toHaveBeenCalledWith('')
    expect(startRenameSpy).toHaveBeenCalledWith(folderRowId('f-new'), 'New folder')
  })
})

describe('rename sessions', () => {
  it('routes a folder row rename to the folder mutation and a bare row id to the table mutation', async () => {
    makeActions()
    mutations.updateFolderAsync.mockResolvedValue({})
    mutations.renameTableAsync.mockResolvedValue({})
    const [listRename] = renameSessions

    await listRename.onSave(folderRowId('f1'), 'Renamed folder')
    expect(mutations.updateFolderAsync).toHaveBeenCalledWith({
      workspaceId: WORKSPACE_ID,
      resourceType: 'table',
      id: 'f1',
      updates: { name: 'Renamed folder' },
    })

    await listRename.onSave('t1', 'Renamed table')
    expect(mutations.renameTableAsync).toHaveBeenCalledWith({
      tableId: 't1',
      name: 'Renamed table',
    })
  })

  it('rejects with a toast when a folder rename fails, so the session can revive', async () => {
    makeActions()
    mutations.updateFolderAsync.mockRejectedValueOnce(new Error('conflict'))
    const [listRename] = renameSessions

    await expect(listRename.onSave(folderRowId('f1'), 'X')).rejects.toThrow('conflict')
    expect(toastError).toHaveBeenCalled()
  })

  it('binds the breadcrumb session to the open folder', async () => {
    makeActions()
    mutations.updateFolderAsync.mockResolvedValue({})
    const [, breadcrumbRename] = renameSessions

    await breadcrumbRename.onSave('f1', 'Q3 Reports')
    expect(mutations.updateFolderAsync).toHaveBeenCalledWith({
      workspaceId: WORKSPACE_ID,
      resourceType: 'table',
      id: 'f1',
      updates: { name: 'Q3 Reports' },
    })
  })
})

describe('row drag/drop', () => {
  it('drops a table row onto a folder row as a move', () => {
    const table = makeTable({ id: 't1', folderId: null })
    const { actions } = makeActions({ tables: [table] })

    actions.rowDragDrop.onDrop(dropEvent('t1'), folderRowId('f2'))

    expect(mutations.moveTableMutate).toHaveBeenCalledWith({ tableId: 't1', folderId: 'f2' })
  })

  it('drops a folder row onto another folder as a reparent', () => {
    const moving = makeFolder({ id: 'f1', parentId: null })
    const target = makeFolder({ id: 'f2', parentId: null })
    const { actions } = makeActions({
      folders: [moving, target],
      folderById: new Map([
        [moving.id, moving],
        [target.id, target],
      ]),
    })

    actions.rowDragDrop.onDrop(dropEvent(folderRowId('f1')), folderRowId('f2'))

    expect(mutations.updateFolderMutate).toHaveBeenCalledWith(
      {
        workspaceId: WORKSPACE_ID,
        resourceType: 'table',
        id: 'f1',
        updates: { parentId: 'f2' },
      },
      expect.objectContaining({ onError: expect.any(Function) })
    )
  })

  it('rejects a no-op drop back into the folder the row already sits in', () => {
    const table = makeTable({ id: 't1', folderId: 'f2' })
    const { actions } = makeActions({ tables: [table] })

    actions.rowDragDrop.onDrop(dropEvent('t1'), folderRowId('f2'))

    expect(mutations.moveTableMutate).not.toHaveBeenCalled()
  })

  it('rejects dropping a folder into its own subtree', () => {
    const parent = makeFolder({ id: 'f1', parentId: null })
    const child = makeFolder({ id: 'f2', parentId: 'f1' })
    const { actions } = makeActions({
      folders: [parent, child],
      folderById: new Map([
        [parent.id, parent],
        [child.id, child],
      ]),
    })

    actions.rowDragDrop.onDrop(dropEvent(folderRowId('f1')), folderRowId('f2'))

    expect(mutations.updateFolderMutate).not.toHaveBeenCalled()
  })

  it('disables dragging and drop targets entirely for a read-only user', () => {
    const table = makeTable({ id: 't1' })
    const folder = makeFolder({ id: 'f1' })
    const { actions } = makeActions({ canEdit: false, tables: [table], folders: [folder] })

    expect(actions.rowDragDrop.isRowDraggable('t1')).toBe(false)
    expect(actions.rowDragDrop.isRowDropTarget(folderRowId('f1'))).toBe(false)
  })
})
