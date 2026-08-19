'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ComboboxOption } from '@sim/emcn'
import { ChipConfirmModal, Plus, Upload } from '@sim/emcn'
import { FolderPlus, Pencil, Trash } from '@sim/emcn/icons'
import { createLogger } from '@sim/logger'
import { useParams, useRouter } from 'next/navigation'
import type { TableDefinition } from '@/lib/table'
import type {
  DropdownOption,
  FilterTag,
  ResourceAction,
  ResourceColumn,
  ResourceRow,
  SearchConfig,
  SortConfig,
} from '@/app/workspace/[workspaceId]/components'
import { Resource } from '@/app/workspace/[workspaceId]/components'
import {
  FOLDERED_RESOURCE_HEADERS,
  FolderContextMenu,
  folderBreadcrumbItems,
  parseFolderedRowId,
  useFolderNavigation,
} from '@/app/workspace/[workspaceId]/components/folders'
import { useContextMenu } from '@/app/workspace/[workspaceId]/components/hooks'
import { useRegisterGlobalCommands } from '@/app/workspace/[workspaceId]/providers/global-commands-provider'
import { useUserPermissionsContext } from '@/app/workspace/[workspaceId]/providers/workspace-permissions-provider'
import {
  ImportCsvDialog,
  ImportProgressMenu,
  TableContextMenu,
  TablesFilterPanel,
  TablesListContextMenu,
} from '@/app/workspace/[workspaceId]/tables/components'
import { useCsvImport } from '@/app/workspace/[workspaceId]/tables/hooks/use-csv-import'
import { useExportTable } from '@/app/workspace/[workspaceId]/tables/hooks/use-table-export'
import { useTablesActions } from '@/app/workspace/[workspaceId]/tables/hooks/use-tables-actions'
import { useTablesListState } from '@/app/workspace/[workspaceId]/tables/hooks/use-tables-list-state'
import { useWorkspaceTablesRoom } from '@/app/workspace/[workspaceId]/tables/hooks/use-workspace-tables-room'
import {
  applyListRename,
  type TableResourceItem,
  toResourceRows,
} from '@/app/workspace/[workspaceId]/tables/rows'
import { usePinnedIds } from '@/hooks/queries/pinned-items'
import { useTablesList } from '@/hooks/queries/tables'
import { getCanonicalFolderPath } from '@/hooks/queries/utils/folder-tree'
import { useWorkspaceMembersQuery, type WorkspaceMember } from '@/hooks/queries/workspace'
import { usePermissionConfig } from '@/hooks/use-permission-config'
import type { WorkspaceFolder } from '@/stores/folders/types'

const logger = createLogger('Tables')

const COLUMNS: ResourceColumn[] = [
  { id: 'name', header: 'Name' },
  { id: 'columns', header: 'Columns' },
  { id: 'rows', header: 'Rows' },
  { id: 'created', header: 'Created' },
  { id: 'owner', header: '所有者' },
  { id: 'updated', header: 'Last Updated' },
]

/** Root label for breadcrumbs and the "move to workspace root" destination. */
const ROOT_LABEL = FOLDERED_RESOURCE_HEADERS.table.rootLabel

const EMPTY_TABLES: TableDefinition[] = []

/**
 * Tables page: pure composition. URL view state lives in {@link useTablesListState}, row
 * mapping in `rows.tsx`, table/folder mutations in {@link useTablesActions}, and CSV
 * import/export in their own controllers — this component wires them together and renders.
 */
export function Tables() {
  const params = useParams()
  const router = useRouter()
  const workspaceId = params.workspaceId as string

  const { config: permissionConfig } = usePermissionConfig()
  useEffect(() => {
    if (permissionConfig.hideTablesTab) {
      router.replace(`/workspace/${workspaceId}`)
    }
  }, [permissionConfig.hideTablesTab, router, workspaceId])

  const userPermissions = useUserPermissionsContext()
  const canEdit = userPermissions.canEdit === true

  // Joined for the live tables list: a `workspace-tables-changed` broadcast (fanned out by the table
  // mutation service) invalidates the list so this view refetches without waiting for staleness.
  useWorkspaceTablesRoom(workspaceId)

  const { data: tables = EMPTY_TABLES, error } = useTablesList(workspaceId)
  const { data: members } = useWorkspaceMembersQuery(workspaceId)
  const pinnedTableIds = usePinnedIds(workspaceId, 'table')
  // Folder pins live in their own `resourceType` namespace, so a page listing
  // folders alongside tables resolves two sets.
  const pinnedFolderIds = usePinnedIds(workspaceId, 'folder')

  const {
    currentFolderId,
    setCurrentFolderId,
    ancestors: folderChain,
    folders,
    folderById,
    foldersResolved,
  } = useFolderNavigation({
    resourceType: 'table',
    workspaceId,
  })

  /**
   * Logged from an effect, not the render body: a render-phase log fires again on every
   * re-render while the error persists, and on each of React's double renders in dev.
   */
  useEffect(() => {
    if (error) logger.error('Failed to load tables:', error)
  }, [error])

  const membersById = useMemo(() => {
    const map = new Map<string, WorkspaceMember>()
    for (const member of members ?? []) map.set(member.userId, member)
    return map
  }, [members])

  const listState = useTablesListState({
    tables,
    folders,
    folderById,
    foldersResolved,
    currentFolderId,
    membersById,
    pinnedFolderIds,
    pinnedTableIds,
  })

  const actions = useTablesActions({
    workspaceId,
    canEdit,
    tables,
    folders,
    folderById,
    currentFolderId,
    setCurrentFolderId,
    pinnedFolderIds,
    pinnedTableIds,
    // Stable setter identity keeps `createFolder` memoized across renders.
    clearSearch: listState.setSearchTerm,
  })
  const { listRename, breadcrumbRename } = actions

  const csvImport = useCsvImport({
    workspaceId,
    getFolderPath: () => getCanonicalFolderPath(currentFolderId, folderById),
  })
  const exportTableCsv = useExportTable(workspaceId)

  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [isDeleteFolderDialogOpen, setIsDeleteFolderDialogOpen] = useState(false)
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false)
  const [activeTable, setActiveTable] = useState<TableDefinition | null>(null)
  const [activeFolder, setActiveFolder] = useState<WorkspaceFolder | null>(null)

  const {
    isOpen: isListContextMenuOpen,
    position: listContextMenuPosition,
    handleContextMenu: handleListContextMenu,
    closeMenu: closeListContextMenu,
  } = useContextMenu()

  const {
    isOpen: isRowContextMenuOpen,
    position: rowContextMenuPosition,
    handleContextMenu: handleRowCtxMenu,
    closeMenu: closeRowContextMenu,
  } = useContextMenu()

  const [contextMenuKind, setContextMenuKind] = useState<'table' | 'folder'>('table')

  const baseRows: ResourceRow[] = useMemo(
    () => toResourceRows(listState.sortedEntries, membersById),
    [listState.sortedEntries, membersById]
  )

  /**
   * Layered on top of {@link baseRows} rather than folded into it so a keystroke
   * in the rename field rebuilds one cell instead of every row's cells.
   */
  const rows: ResourceRow[] = useMemo(
    () => applyListRename(baseRows, listRename),
    [
      baseRows,
      listRename.editingId,
      listRename.editValue,
      listRename.isSaving,
      listRename.setEditValue,
      listRename.submitRename,
      listRename.cancelRename,
    ]
  )

  const currentFolderActions: DropdownOption[] | undefined = useMemo(() => {
    if (!currentFolderId) return undefined
    const folder = folderById.get(currentFolderId)
    if (!folder) return undefined
    return [
      {
        label: 'Rename',
        icon: Pencil,
        disabled: !canEdit,
        onClick: () => breadcrumbRename.startRename(folder.id, folder.name),
      },
      {
        label: 'Delete',
        icon: Trash,
        disabled: !canEdit,
        /**
         * The only way to delete the folder you are inside — its own row is not in the list.
         * This is what makes the step-out in `handleDeleteFolder` reachable.
         */
        onClick: () => {
          setActiveFolder(folder)
          setIsDeleteFolderDialogOpen(true)
        },
      },
    ]
  }, [currentFolderId, folderById, canEdit, breadcrumbRename.startRename])

  const currentFolderEditing = useMemo(() => {
    if (!currentFolderId || breadcrumbRename.editingId !== currentFolderId) return undefined
    return {
      isEditing: true,
      value: breadcrumbRename.editValue,
      onChange: breadcrumbRename.setEditValue,
      onSubmit: breadcrumbRename.submitRename,
      onCancel: breadcrumbRename.cancelRename,
      disabled: breadcrumbRename.isSaving,
    }
  }, [
    currentFolderId,
    breadcrumbRename.editingId,
    breadcrumbRename.editValue,
    breadcrumbRename.isSaving,
    breadcrumbRename.setEditValue,
    breadcrumbRename.submitRename,
    breadcrumbRename.cancelRename,
  ])

  const breadcrumbs = useMemo(
    () =>
      folderBreadcrumbItems({
        breadcrumbs: folderChain,
        rootLabel: ROOT_LABEL,
        rootIcon: FOLDERED_RESOURCE_HEADERS.table.rootIcon,
        onNavigate: setCurrentFolderId,
        currentFolderActions,
        currentFolderEditing,
      }),
    [folderChain, setCurrentFolderId, currentFolderActions, currentFolderEditing]
  )

  const searchConfig: SearchConfig = useMemo(
    () => ({
      value: listState.searchValue,
      onChange: listState.setSearchTerm,
      onClearAll: () => listState.setSearchTerm(''),
      placeholder: 'Search tables...',
    }),
    [listState.searchValue, listState.setSearchTerm]
  )

  const sortConfig: SortConfig = useMemo(
    () => ({
      options: [
        { id: 'name', label: 'Name' },
        { id: 'columns', label: 'Columns' },
        { id: 'rows', label: 'Rows' },
        { id: 'created', label: 'Created' },
        { id: 'owner', label: '所有者' },
        { id: 'updated', label: 'Last Updated' },
      ],
      active: listState.activeSort,
      onSort: listState.onSort,
      onClear: listState.onClear,
    }),
    [listState.activeSort, listState.onSort, listState.onClear]
  )

  const memberOptions: ComboboxOption[] = useMemo(
    () =>
      (members ?? []).map((m) => ({
        value: m.userId,
        label: m.name,
        iconElement: m.image ? (
          <img
            src={m.image}
            alt={m.name}
            referrerPolicy='no-referrer'
            className='size-[14px] rounded-full border border-[var(--border)] object-cover'
          />
        ) : (
          <span className='flex size-[14px] items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface-3)] font-medium text-[8px] text-[var(--text-secondary)]'>
            {m.name.charAt(0).toUpperCase()}
          </span>
        ),
      })),
    [members]
  )

  const filterTags: FilterTag[] = useMemo(() => {
    const tags: FilterTag[] = []
    if (listState.rowCountFilter.length > 0) {
      const rowLabels: Record<string, string> = { empty: 'Empty', small: 'Small', large: 'Large' }
      const label =
        listState.rowCountFilter.length === 1
          ? `Rows: ${rowLabels[listState.rowCountFilter[0]]}`
          : `Rows: ${listState.rowCountFilter.length} selected`
      tags.push({ label, onRemove: () => listState.setRowCountFilter([]) })
    }
    if (listState.ownerFilter.length > 0) {
      const label =
        listState.ownerFilter.length === 1
          ? `所有者：${membersById.get(listState.ownerFilter[0])?.name ?? '1 名成员'}`
          : `所有者：${listState.ownerFilter.length} 名成员`
      tags.push({ label, onRemove: () => listState.setOwnerFilter([]) })
    }
    return tags
  }, [
    listState.rowCountFilter,
    listState.ownerFilter,
    listState.setRowCountFilter,
    listState.setOwnerFilter,
    membersById,
  ])

  const filterPanel = useMemo(
    () => (
      <TablesFilterPanel
        rowCountFilter={listState.rowCountFilter}
        ownerFilter={listState.ownerFilter}
        memberOptions={memberOptions}
        onRowCountFilterChange={listState.setRowCountFilter}
        onOwnerFilterChange={listState.setOwnerFilter}
      />
    ),
    [
      listState.rowCountFilter,
      listState.ownerFilter,
      listState.setRowCountFilter,
      listState.setOwnerFilter,
      memberOptions,
    ]
  )

  const handleContentContextMenu = useCallback(
    (e: React.MouseEvent) => {
      const target = e.target as HTMLElement
      if (
        target.closest('[data-resource-row]') ||
        target.closest('button, input, a, [role="button"]')
      ) {
        return
      }
      handleListContextMenu(e)
    },
    [handleListContextMenu]
  )

  const handleRowClick = useCallback(
    (rowId: string) => {
      if (isRowContextMenuOpen || listRename.editingId === rowId) return
      const parsed = parseFolderedRowId(rowId)
      if (parsed.kind === 'folder') {
        setCurrentFolderId(parsed.id)
        return
      }
      router.push(`/workspace/${workspaceId}/tables/${parsed.id}`)
    },
    [isRowContextMenuOpen, listRename.editingId, router, workspaceId, setCurrentFolderId]
  )

  const resolveRowItem = useCallback(
    (rowId: string): TableResourceItem | null => {
      const parsed = parseFolderedRowId(rowId)
      if (parsed.kind === 'folder') {
        const folder = folderById.get(parsed.id)
        return folder ? { kind: 'folder', folder } : null
      }
      const table = tables.find((t) => t.id === parsed.id)
      return table ? { kind: 'table', table } : null
    },
    [folderById, tables]
  )

  const handleRowContextMenu = useCallback(
    (e: React.MouseEvent, rowId: string) => {
      const item = resolveRowItem(rowId)
      if (!item) return
      if (item.kind === 'folder') {
        setActiveFolder(item.folder)
        setActiveTable(null)
        setContextMenuKind('folder')
      } else {
        setActiveTable(item.table)
        setActiveFolder(null)
        setContextMenuKind('table')
      }
      handleRowCtxMenu(e)
    },
    [resolveRowItem, handleRowCtxMenu]
  )

  const handleMoveTable = useCallback(
    (optionValue: string) => {
      if (!activeTable) return
      actions.moveTableTo(optionValue, activeTable)
      closeRowContextMenu()
    },
    [actions, activeTable, closeRowContextMenu]
  )

  const handleMoveFolder = useCallback(
    (optionValue: string) => {
      if (!activeFolder) return
      actions.moveFolderByOption(optionValue, activeFolder)
      closeRowContextMenu()
    },
    [actions, activeFolder, closeRowContextMenu]
  )

  const handleDelete = useCallback(async () => {
    if (!activeTable) return
    try {
      await actions.deleteTable(activeTable.id)
      setIsDeleteDialogOpen(false)
      setActiveTable(null)
    } catch {
      // Logged by the actions hook; keep the confirm dialog open so the user can retry.
    }
  }, [actions, activeTable])

  const handleDeleteFolder = useCallback(async () => {
    if (!activeFolder) return
    try {
      await actions.deleteFolder(activeFolder)
      setIsDeleteFolderDialogOpen(false)
      setActiveFolder(null)
    } catch {
      // Toasted and logged by the actions hook; keep the confirm dialog open.
    }
  }, [actions, activeFolder])

  const handleTogglePin = useCallback(() => {
    const target =
      contextMenuKind === 'folder'
        ? activeFolder && { resourceType: 'folder' as const, id: activeFolder.id }
        : activeTable && { resourceType: 'table' as const, id: activeTable.id }
    if (!target) return
    actions.togglePin(target)
    closeRowContextMenu()
  }, [actions, contextMenuKind, activeFolder, activeTable, closeRowContextMenu])

  const handleListUploadCsv = useCallback(() => {
    csvImport.openFilePicker()
    closeListContextMenu()
  }, [csvImport.openFilePicker, closeListContextMenu])

  useRegisterGlobalCommands(() => [
    { id: 'tables-new-table', handler: () => void actions.createTable() },
    { id: 'tables-new-folder', handler: () => void actions.createFolder() },
    {
      id: 'tables-import-csv',
      handler: () => {
        if (!csvImport.uploading) csvImport.openFilePicker()
      },
    },
  ])

  const headerActions: ResourceAction[] = useMemo(
    () => [
      {
        text: csvImport.uploadButtonLabel,
        icon: Upload,
        onSelect: csvImport.openFilePicker,
        disabled: csvImport.uploading || !canEdit,
      },
      {
        text: 'New folder',
        icon: FolderPlus,
        onSelect: actions.createFolder,
        disabled: !canEdit || actions.isCreatingFolder,
      },
      {
        text: 'New table',
        icon: Plus,
        onSelect: actions.createTable,
        disabled: csvImport.uploading || !canEdit || actions.isCreatingTable,
        variant: 'primary',
      },
    ],
    [
      csvImport.uploadButtonLabel,
      csvImport.openFilePicker,
      csvImport.uploading,
      canEdit,
      actions.createFolder,
      actions.createTable,
      actions.isCreatingFolder,
      actions.isCreatingTable,
    ]
  )

  // Stable identities so the memoized Resource.Header / Resource.Options can
  // actually bail — inline object/element props would defeat their memo.
  const headerAside = useMemo(() => <ImportProgressMenu workspaceId={workspaceId} />, [workspaceId])
  const filterConfig = useMemo(() => ({ content: filterPanel }), [filterPanel])
  const folderMoveOptions = useMemo(
    () => actions.folderMoveOptions(activeFolder),
    [actions.folderMoveOptions, activeFolder]
  )

  return (
    <>
      <Resource onContextMenu={handleContentContextMenu}>
        <Resource.Header
          icon={FOLDERED_RESOURCE_HEADERS.table.rootIcon}
          title={ROOT_LABEL}
          breadcrumbs={breadcrumbs}
          actions={headerActions}
          aside={headerAside}
        />
        <Resource.Options
          search={searchConfig}
          sort={sortConfig}
          filterTags={filterTags}
          filter={filterConfig}
        />
        <Resource.Table
          columns={COLUMNS}
          rows={rows}
          rowDragDrop={actions.rowDragDrop}
          onRowClick={handleRowClick}
          onRowContextMenu={handleRowContextMenu}
        />
      </Resource>

      <input
        ref={csvImport.csvInputRef}
        type='file'
        className='hidden'
        onChange={csvImport.handleCsvChange}
        disabled={csvImport.uploading}
        accept='.csv,.tsv'
        multiple
      />

      <TablesListContextMenu
        isOpen={isListContextMenuOpen}
        position={listContextMenuPosition}
        onClose={closeListContextMenu}
        onCreateTable={actions.createTable}
        onCreateFolder={actions.createFolder}
        onUploadCsv={handleListUploadCsv}
        disableCreate={!canEdit || actions.isCreatingTable}
        disableCreateFolder={!canEdit || actions.isCreatingFolder}
        disableUpload={csvImport.uploading || !canEdit}
      />

      <TableContextMenu
        isOpen={isRowContextMenuOpen && contextMenuKind === 'table'}
        position={rowContextMenuPosition}
        onClose={closeRowContextMenu}
        onCopyId={() => {
          if (activeTable) navigator.clipboard.writeText(activeTable.id)
        }}
        onDelete={() => setIsDeleteDialogOpen(true)}
        onRename={() => {
          if (activeTable) listRename.startRename(activeTable.id, activeTable.name)
        }}
        onImportCsv={() => setIsImportDialogOpen(true)}
        onExportCsv={() => {
          if (activeTable) void exportTableCsv(activeTable.id)
        }}
        onTogglePin={handleTogglePin}
        pinned={activeTable ? pinnedTableIds.has(activeTable.id) : false}
        onMove={canEdit ? handleMoveTable : undefined}
        moveOptions={canEdit ? actions.tableMoveOptions : undefined}
        disableDelete={!canEdit}
        disableRename={!canEdit}
        disableImport={!canEdit}
      />

      <FolderContextMenu
        isOpen={isRowContextMenuOpen && contextMenuKind === 'folder'}
        position={rowContextMenuPosition}
        onClose={closeRowContextMenu}
        onOpen={() => {
          if (activeFolder) setCurrentFolderId(activeFolder.id)
          closeRowContextMenu()
        }}
        onRename={() => {
          if (activeFolder) actions.startFolderRename(activeFolder)
        }}
        onCopyId={() => {
          if (activeFolder) navigator.clipboard.writeText(activeFolder.id)
        }}
        onDelete={() => setIsDeleteFolderDialogOpen(true)}
        onTogglePin={handleTogglePin}
        pinned={activeFolder ? pinnedFolderIds.has(activeFolder.id) : false}
        onMove={canEdit ? handleMoveFolder : undefined}
        moveOptions={canEdit ? folderMoveOptions : undefined}
        canEdit={canEdit}
      />

      {activeTable && (
        <ImportCsvDialog
          open={isImportDialogOpen}
          onOpenChange={(open) => {
            setIsImportDialogOpen(open)
            if (!open) setActiveTable(null)
          }}
          workspaceId={workspaceId}
          table={activeTable}
        />
      )}

      <ChipConfirmModal
        open={isDeleteDialogOpen}
        onOpenChange={(open) => {
          setIsDeleteDialogOpen(open)
          if (!open) setActiveTable(null)
        }}
        srTitle='Delete Table'
        title='Delete Table'
        text={[
          'Are you sure you want to delete ',
          { text: activeTable?.name ?? 'this table', bold: true },
          '? ',
          { text: `All ${activeTable?.rowCount ?? 0} rows will be removed.`, error: true },
          ' You can restore it from Recently Deleted in Settings.',
        ]}
        confirm={{
          label: 'Delete',
          onClick: handleDelete,
          pending: actions.isDeletingTable,
          pendingLabel: 'Deleting...',
        }}
      />

      <ChipConfirmModal
        open={isDeleteFolderDialogOpen}
        onOpenChange={(open) => {
          setIsDeleteFolderDialogOpen(open)
          if (!open) setActiveFolder(null)
        }}
        srTitle='Delete Folder'
        title='Delete Folder'
        text={[
          'Are you sure you want to delete ',
          { text: activeFolder?.name ?? 'this folder', bold: true },
          '? ',
          { text: 'Every table and subfolder inside it will be deleted too.', error: true },
          ' You can restore those tables from Recently Deleted in Settings.',
        ]}
        confirm={{
          label: 'Delete',
          onClick: handleDeleteFolder,
          pending: actions.isDeletingFolder,
          pendingLabel: 'Deleting...',
        }}
      />
    </>
  )
}
