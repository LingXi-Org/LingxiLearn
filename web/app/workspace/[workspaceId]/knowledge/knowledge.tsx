'use client'

import { useEffect, useMemo, useRef } from 'react'
import { Plus } from '@/components/ui-kit'
import { FolderPlus, Pencil, Trash } from '@/components/ui-kit/icons'
import { useParams, useRouter } from 'next/navigation'
import type {
  BreadcrumbItem,
  FilterTag,
  ResourceAction,
  SearchConfig,
  SortConfig,
} from '@/app/workspace/[workspaceId]/components'
import { Resource } from '@/app/workspace/[workspaceId]/components'
import type { MoveOptionNode } from '@/app/workspace/[workspaceId]/components/folders'
import {
  buildMoveOptions,
  FOLDERED_RESOURCE_HEADERS,
  FolderContextMenu,
  folderBreadcrumbItems,
  folderRowId,
  parseFolderedRowId,
  sortResources,
  useFolderRowDragDrop,
} from '@/app/workspace/[workspaceId]/components/folders'
import { useRegisterGlobalCommands } from '@/app/workspace/[workspaceId]/providers/global-commands-provider'
import { useUserPermissionsContext } from '@/app/workspace/[workspaceId]/providers/workspace-permissions-provider'
import { usePermissionConfig } from '@/hooks/use-permission-config'
import { KnowledgeBaseContextMenu, KnowledgeListContextMenu } from './components'
import { KnowledgeDialogsView } from './dialogs/knowledge-dialogs'
import { useKnowledgeBaseCommands } from './hooks/use-knowledge-base-commands'
import { useKnowledgeDialogs } from './hooks/use-knowledge-dialogs'
import { useKnowledgeFolderCommands } from './hooks/use-knowledge-folder-commands'
import { useKnowledgeListData } from './hooks/use-knowledge-list-data'
import { useKnowledgeListSelection } from './hooks/use-knowledge-list-selection'
import { useKnowledgeRename } from './hooks/use-knowledge-rename'
import { useKnowledgeUrlState } from './hooks/use-knowledge-url-state'
import {
  applyKnowledgeBaseFilters,
  filterKnowledgeBases,
  knowledgeBasesInFolder,
  visibleKnowledgeFolders,
} from './list/filters'
import { decorateKnowledgeListItems } from './list/sort'
import { KNOWLEDGE_FOLDER_RESOURCE_TYPE } from './list/types'
import { KnowledgeFilterPanel } from './presentation/knowledge-filter-panel'
import {
  applyRenameOverlay,
  buildKnowledgeRows,
  KNOWLEDGE_LIST_COLUMNS,
} from './presentation/knowledge-rows'

const ROOT_BREADCRUMB_LABEL = FOLDERED_RESOURCE_HEADERS[KNOWLEDGE_FOLDER_RESOURCE_TYPE].rootLabel

/**
 * The knowledge list page. This file is deliberately only composition: domain queries and
 * indexes come from the hooks, view state from the URL, filter/sort/row projection from
 * pure functions in `list/`, and dialogs from `KnowledgeDialogsView`. Nothing here owns
 * business rules.
 */
export function Knowledge() {
  const params = useParams()
  const router = useRouter()
  const workspaceId = params.workspaceId as string

  const { config: permissionConfig } = usePermissionConfig()
  useEffect(() => {
    if (permissionConfig.hideKnowledgeBaseTab) {
      router.replace(`/workspace/${workspaceId}`)
    }
  }, [permissionConfig.hideKnowledgeBaseTab, router, workspaceId])

  const userPermissions = useUserPermissionsContext()
  const canEdit = userPermissions.canEdit === true

  // --- Domain data -------------------------------------------------------------
  const {
    knowledgeBases,
    findKnowledgeBase,
    findFolder,
    members,
    membersById,
    memberNameById,
    pinnedBaseIds,
    pinnedFolderIds,
    pinItem,
    unpinItem,
    folderNavigation,
    folders,
    foldersRef,
    currentFolderIdRef,
    descendantsByFolderId,
  } = useKnowledgeListData(workspaceId)
  const {
    currentFolderId,
    setCurrentFolderId,
    ancestors: breadcrumbs,
    folderById,
    foldersResolved,
  } = folderNavigation

  // --- URL view state ----------------------------------------------------------
  const urlState = useKnowledgeUrlState()
  const { urlSearchQuery, debouncedSearchQuery, filters, sortColumn, sortDirection } = urlState

  // --- Selection & context menus ------------------------------------------------
  const selection = useKnowledgeListSelection({ findKnowledgeBase, findFolder })

  // --- Rename -------------------------------------------------------------------
  const rename = useKnowledgeRename(workspaceId)
  const { listRename, breadcrumbRename } = rename

  /** Handlers fire between renders; they must read the rename session as it is now. */
  const listRenameRef = useRef(listRename)
  listRenameRef.current = listRename
  const breadcrumbRenameRef = useRef(breadcrumbRename)
  breadcrumbRenameRef.current = breadcrumbRename

  // --- Commands ------------------------------------------------------------------
  const baseCommands = useKnowledgeBaseCommands({
    workspaceId,
    findKnowledgeBase,
    pinnedBaseIds,
    pinItem,
    unpinItem,
    closeMenu: selection.baseMenu.closeMenu,
  })

  const folderCommands = useKnowledgeFolderCommands({
    workspaceId,
    foldersRef,
    currentFolderIdRef,
    setCurrentFolderId,
    pinnedFolderIds,
    pinItem,
    unpinItem,
    clearSearch: () => urlState.setSearchQuery(''),
    startRowRename: listRename.startRename,
    closeMenu: selection.folderMenu.closeMenu,
  })

  // --- Dialogs --------------------------------------------------------------------
  const dialogs = useKnowledgeDialogs()

  useRegisterGlobalCommands(() => [
    { id: 'knowledge-new-base', handler: () => dialogs.openCreate() },
    {
      id: 'knowledge-new-folder',
      handler: () => void folderCommands.createFolderInCurrentFolder(),
    },
  ])

  // --- List pipeline: pure functions, memoized ------------------------------------
  /**
   * With no explicit sort the two blocks disagree on purpose — folders read best
   * alphabetically while bases read best most-recently-updated-first — which mirrors the
   * Files page. The resource filters (connectors/content/owner) describe properties a
   * folder does not have, so folders answer only to the search term.
   */
  const visibleFolders = useMemo(
    () => visibleKnowledgeFolders(folders, currentFolderId, debouncedSearchQuery),
    [folders, currentFolderId, debouncedSearchQuery]
  )

  const processedBases = useMemo(
    () =>
      applyKnowledgeBaseFilters(
        knowledgeBasesInFolder(filterKnowledgeBases(knowledgeBases, debouncedSearchQuery), {
          currentFolderId,
          folderById,
          foldersResolved,
        }),
        filters
      ),
    [knowledgeBases, debouncedSearchQuery, currentFolderId, folderById, foldersResolved, filters]
  )

  const sortedEntries = useMemo(
    () =>
      sortResources(
        decorateKnowledgeListItems({
          folders: visibleFolders,
          bases: processedBases,
          sortColumn,
          pinnedFolderIds,
          pinnedBaseIds,
          memberNameById,
        }),
        sortDirection
      ),
    [
      visibleFolders,
      processedBases,
      sortColumn,
      sortDirection,
      pinnedFolderIds,
      pinnedBaseIds,
      memberNameById,
    ]
  )

  const baseRows = useMemo(
    () => buildKnowledgeRows(sortedEntries, membersById),
    [sortedEntries, membersById]
  )

  const rows = useMemo(
    () => applyRenameOverlay(baseRows, listRename),
    [
      baseRows,
      listRename.editingId,
      listRename.editValue,
      listRename.isSaving,
      listRename.setEditValue,
      listRename.submitRename,
      listRename.cancelRename,
      listRename,
    ]
  )

  // --- Row interactions --------------------------------------------------------------
  const handleRowClick = (rowId: string) => {
    if (selection.isRowInteractionBlocked()) return
    if (listRenameRef.current.editingId === rowId) return

    const parsed = parseFolderedRowId(rowId)
    if (parsed.kind === 'folder') {
      setCurrentFolderId(parsed.id)
      return
    }

    const base = findKnowledgeBase(parsed.id)
    if (base) baseCommands.openBase(base)
  }

  const rowDragDropConfig = useFolderRowDragDrop({
    canEdit,
    editingRowId: listRename.editingId,
    descendantsByFolderId,
    getFolderParentId: (folderId) => findFolder(folderId)?.parentId,
    getResourceFolderId: (knowledgeBaseId) => findKnowledgeBase(knowledgeBaseId)?.folderId ?? null,
    getRowLabel: (rowId) => {
      const parsed = parseFolderedRowId(rowId)
      return parsed.kind === 'folder'
        ? (findFolder(parsed.id)?.name ?? 'Folder')
        : (findKnowledgeBase(parsed.id)?.name ?? 'Knowledge base')
    },
    onMoveFolder: (folderId, targetFolderId) =>
      void folderCommands.moveFolderTo(folderId, targetFolderId),
    onMoveResource: (knowledgeBaseId, targetFolderId) =>
      void baseCommands.moveBaseTo(knowledgeBaseId, targetFolderId),
  })

  // --- Move targets ---------------------------------------------------------------------
  /** Move targets for the folder under the cursor: itself and its subtree are unreachable. */
  const folderMoveOptions: MoveOptionNode[] = useMemo(() => {
    if (!selection.activeFolder) return []
    const excluded = new Set<string>([selection.activeFolder.id])
    for (const id of descendantsByFolderId.get(selection.activeFolder.id) ?? []) excluded.add(id)
    return buildMoveOptions({
      folders,
      rootLabel: ROOT_BREADCRUMB_LABEL,
      excludedFolderIds: excluded,
    })
  }, [folders, selection.activeFolder, descendantsByFolderId])

  /** Move targets for a knowledge base: every folder, since a base has no subtree. */
  const knowledgeBaseMoveOptions: MoveOptionNode[] = useMemo(
    () => buildMoveOptions({ folders, rootLabel: ROOT_BREADCRUMB_LABEL }),
    [folders]
  )

  // --- Header, breadcrumbs, search/sort/filter chrome ---------------------------------------
  const headerActions: ResourceAction[] = useMemo(
    () => [
      {
        text: 'New folder',
        icon: FolderPlus,
        onSelect: folderCommands.createFolderInCurrentFolder,
        disabled: folderCommands.isCreatingFolder || !canEdit,
      },
      {
        text: 'New base',
        icon: Plus,
        onSelect: dialogs.openCreate,
        disabled: !canEdit,
        variant: 'primary',
      },
    ],
    [
      folderCommands.createFolderInCurrentFolder,
      folderCommands.isCreatingFolder,
      dialogs.openCreate,
      canEdit,
    ]
  )

  const listBreadcrumbs: BreadcrumbItem[] = useMemo(
    () =>
      folderBreadcrumbItems({
        rootLabel: ROOT_BREADCRUMB_LABEL,
        rootIcon: FOLDERED_RESOURCE_HEADERS[KNOWLEDGE_FOLDER_RESOURCE_TYPE].rootIcon,
        breadcrumbs,
        onNavigate: setCurrentFolderId,
        currentFolderEditing:
          breadcrumbRename.editingId && breadcrumbRename.editingId === currentFolderId
            ? {
                isEditing: true,
                value: breadcrumbRename.editValue,
                onChange: breadcrumbRenameRef.current.setEditValue,
                onSubmit: breadcrumbRenameRef.current.submitRename,
                onCancel: breadcrumbRenameRef.current.cancelRename,
                disabled: breadcrumbRename.isSaving,
              }
            : undefined,
        currentFolderActions:
          canEdit && breadcrumbs.length > 0
            ? [
                {
                  label: 'Rename',
                  icon: Pencil,
                  onClick: () => {
                    const folder = breadcrumbs[breadcrumbs.length - 1]
                    breadcrumbRenameRef.current.startRename(folder.id, folder.name)
                  },
                },
                {
                  label: 'Delete',
                  icon: Trash,
                  onClick: () => dialogs.requestFolderDelete(breadcrumbs[breadcrumbs.length - 1]),
                },
              ]
            : undefined,
      }),
    [
      breadcrumbs,
      currentFolderId,
      setCurrentFolderId,
      canEdit,
      breadcrumbRename.editingId,
      breadcrumbRename.editValue,
      breadcrumbRename.isSaving,
      dialogs.requestFolderDelete,
    ]
  )

  const searchConfig: SearchConfig = useMemo(
    () => ({
      value: urlSearchQuery,
      onChange: urlState.setSearchQuery,
      onClearAll: () => urlState.setSearchQuery(''),
      placeholder: 'Search knowledge bases...',
    }),
    [urlSearchQuery, urlState.setSearchQuery]
  )

  const sortConfig: SortConfig = useMemo(
    () => ({
      options: [
        { id: 'name', label: 'Name' },
        { id: 'documents', label: 'Documents' },
        { id: 'tokens', label: 'Tokens' },
        { id: 'connectors', label: 'Connectors' },
        { id: 'created', label: 'Created' },
        { id: 'owner', label: 'Owner' },
        { id: 'updated', label: 'Last Updated' },
      ],
      active: urlState.activeSort,
      onSort: urlState.onSortColumn,
      onClear: urlState.onClearSort,
    }),
    [urlState.activeSort, urlState.onSortColumn, urlState.onClearSort]
  )

  const filterTags: FilterTag[] = useMemo(() => {
    const tags: FilterTag[] = []
    if (filters.connector.length > 0) {
      const label =
        filters.connector.length === 1
          ? `Connectors: ${filters.connector[0] === 'connected' ? 'With connectors' : 'Without connectors'}`
          : `Connectors: ${filters.connector.length} types`
      tags.push({ label, onRemove: () => urlState.setConnectorFilter([]) })
    }
    if (filters.content.length > 0) {
      const label =
        filters.content.length === 1
          ? `Content: ${filters.content[0] === 'has-docs' ? 'Has documents' : 'Empty'}`
          : `Content: ${filters.content.length} types`
      tags.push({ label, onRemove: () => urlState.setContentFilter([]) })
    }
    if (filters.owner.length > 0) {
      const label =
        filters.owner.length === 1
          ? `Owner: ${members?.find((m) => m.userId === filters.owner[0])?.name ?? '1 member'}`
          : `Owner: ${filters.owner.length} members`
      tags.push({ label, onRemove: () => urlState.setOwnerFilter([]) })
    }
    return tags
  }, [
    filters,
    members,
    urlState.setConnectorFilter,
    urlState.setContentFilter,
    urlState.setOwnerFilter,
  ])

  return (
    <>
      <Resource onContextMenu={selection.handleContentContextMenu}>
        <Resource.Header
          icon={FOLDERED_RESOURCE_HEADERS[KNOWLEDGE_FOLDER_RESOURCE_TYPE].rootIcon}
          title={ROOT_BREADCRUMB_LABEL}
          breadcrumbs={listBreadcrumbs}
          actions={headerActions}
        />
        <Resource.Options
          search={searchConfig}
          sort={sortConfig}
          filterTags={filterTags}
          filter={{
            content: (
              <KnowledgeFilterPanel
                filters={filters}
                members={members}
                onConnectorChange={urlState.setConnectorFilter}
                onContentChange={urlState.setContentFilter}
                onOwnerChange={urlState.setOwnerFilter}
              />
            ),
          }}
        />
        <Resource.Table
          columns={KNOWLEDGE_LIST_COLUMNS}
          rows={rows}
          rowDragDrop={rowDragDropConfig}
          onRowClick={handleRowClick}
          onRowContextMenu={selection.handleRowContextMenu}
        />
      </Resource>

      <KnowledgeListContextMenu
        isOpen={selection.listMenu.isOpen}
        position={selection.listMenu.position}
        onClose={selection.listMenu.closeMenu}
        onAddKnowledgeBase={dialogs.openCreate}
        onAddFolder={folderCommands.createFolderInCurrentFolder}
        disableAdd={!canEdit}
        disableAddFolder={folderCommands.isCreatingFolder || !canEdit}
      />

      {selection.activeBase && (
        <KnowledgeBaseContextMenu
          isOpen={selection.baseMenu.isOpen}
          position={selection.baseMenu.position}
          onClose={selection.baseMenu.closeMenu}
          onOpenInNewTab={() => baseCommands.openBaseInNewTab(selection.activeBase!)}
          onViewTags={dialogs.openTags}
          onCopyId={() => baseCommands.copyBaseId(selection.activeBase!)}
          onTogglePin={() => baseCommands.toggleBasePin(selection.activeBase!)}
          pinned={pinnedBaseIds.has(selection.activeBase.id)}
          onEdit={dialogs.openEdit}
          onDelete={dialogs.openDelete}
          onMove={(optionValue) =>
            void baseCommands.moveBaseFromMenu(selection.activeBase!, optionValue)
          }
          moveOptions={knowledgeBaseMoveOptions}
          showOpenInNewTab
          showViewTags
          showEdit
          showDelete
          disableEdit={!canEdit}
          disableDelete={!canEdit}
        />
      )}

      {selection.activeFolder && (
        <FolderContextMenu
          isOpen={selection.folderMenu.isOpen}
          position={selection.folderMenu.position}
          onClose={selection.folderMenu.closeMenu}
          onOpen={() => folderCommands.openFolder(selection.activeFolder!)}
          onRename={() =>
            listRenameRef.current.startRename(
              folderRowId(selection.activeFolder!.id),
              selection.activeFolder!.name
            )
          }
          onDelete={() => dialogs.requestFolderDelete(selection.activeFolder!)}
          onCopyId={() => folderCommands.copyFolderId(selection.activeFolder!)}
          onTogglePin={() => folderCommands.toggleFolderPin(selection.activeFolder!)}
          pinned={pinnedFolderIds.has(selection.activeFolder.id)}
          onMove={(optionValue) =>
            void folderCommands.moveFolderFromMenu(selection.activeFolder!, optionValue)
          }
          moveOptions={folderMoveOptions}
          canEdit={canEdit}
        />
      )}

      <KnowledgeDialogsView
        dialogs={dialogs}
        activeBase={selection.activeBase}
        currentFolderId={currentFolderId}
        onSaveBase={(id, name, description) => baseCommands.updateBase(id, { name, description })}
        onDeleteBase={async (id) => {
          await baseCommands.deleteBase(id)
          selection.setActiveBase(null)
        }}
        onCloseDelete={() => selection.setActiveBase(null)}
        onConfirmFolderDelete={folderCommands.confirmDeleteFolder}
        folderDeletePending={folderCommands.isDeletingFolder}
        onFolderDeleted={() => selection.setActiveFolder(null)}
      />
    </>
  )
}
