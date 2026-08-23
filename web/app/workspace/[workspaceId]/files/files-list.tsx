'use client'

import { type MouseEvent, useCallback, useMemo, useRef } from 'react'
import { type ComboboxOption, FolderPlus, Pencil, Plus, Upload } from '@/components/ui-kit'
import type { WorkspaceFileRecord } from '@/lib/uploads/contexts/workspace'
import type {
  BreadcrumbItem,
  FilterTag,
  ResourceAction,
  ResourceColumn,
  SearchConfig,
  SortConfig,
} from '@/app/workspace/[workspaceId]/components'
import { Resource } from '@/app/workspace/[workspaceId]/components'
import {
  breadcrumbFolderChain,
  FOLDERED_RESOURCE_HEADERS,
  folderBreadcrumbItems,
} from '@/app/workspace/[workspaceId]/components/folders'
import { useContextMenu } from '@/app/workspace/[workspaceId]/components/hooks'
import { FilesActionBar } from '@/app/workspace/[workspaceId]/files/components/action-bar'
import { DeleteConfirmModal } from '@/app/workspace/[workspaceId]/files/components/delete-confirm-modal'
import { FileRowContextMenu } from '@/app/workspace/[workspaceId]/files/components/file-row-context-menu'
import { FilesListContextMenu } from '@/app/workspace/[workspaceId]/files/components/files-list-context-menu'
import { FilesFilterPanel } from '@/app/workspace/[workspaceId]/files/components/filter-panel'
import {
  useFilesCreation,
  useFilesRenameMutations,
} from '@/app/workspace/[workspaceId]/files/hooks/use-files-creation'
import type { FilesData } from '@/app/workspace/[workspaceId]/files/hooks/use-files-data'
import { useFilesDeleteFlow } from '@/app/workspace/[workspaceId]/files/hooks/use-files-delete-flow'
import { useFilesDownloads } from '@/app/workspace/[workspaceId]/files/hooks/use-files-downloads'
import { useFilesFilters } from '@/app/workspace/[workspaceId]/files/hooks/use-files-filters'
import { useFilesRowDragDrop } from '@/app/workspace/[workspaceId]/files/hooks/use-files-row-drag-drop'
import { useFilesRowMenu } from '@/app/workspace/[workspaceId]/files/hooks/use-files-row-menu'
import { useFilesRows } from '@/app/workspace/[workspaceId]/files/hooks/use-files-rows'
import { useFilesSelection } from '@/app/workspace/[workspaceId]/files/hooks/use-files-selection'
import { useFilesUpload } from '@/app/workspace/[workspaceId]/files/hooks/use-files-upload'
import { parseFilesRowId } from '@/app/workspace/[workspaceId]/files/lib/file-row-ids'
import type { FileResourceItem } from '@/app/workspace/[workspaceId]/files/lib/file-types'
import { getFilesCommandAvailability } from '@/app/workspace/[workspaceId]/files/lib/files-command-matrix'
import { useRegisterGlobalCommands } from '@/app/workspace/[workspaceId]/providers/global-commands-provider'
import { useInlineRename } from '@/hooks/use-inline-rename'

const FILES_HEADER = FOLDERED_RESOURCE_HEADERS.file

const COLUMNS: ResourceColumn[] = [
  { id: 'name', header: 'Name', widthMultiplier: 1.15 },
  { id: 'size', header: 'Size', widthMultiplier: 0.85 },
  { id: 'type', header: 'Type', widthMultiplier: 1.0 },
  { id: 'created', header: 'Created' },
  { id: 'owner', header: 'Owner' },
  { id: 'updated', header: 'Last Updated' },
]

export interface FilesListProps {
  workspaceId: string
  canEdit: boolean
  /** While permissions load, the folder crumb keeps its Rename slot to avoid layout shift. */
  permissionsLoading: boolean
  /** Query + derived-data bundle, owned by the Files shell and shared with the detail view. */
  data: FilesData
  currentFolderId: string | null
  /** Folder navigation within the list (root crumb passes null to close the open folder). */
  onNavigateListFolder: (folderId: string | null) => void
  onOpenFile: (file: WorkspaceFileRecord) => void
  onShareFile: (fileId: string) => void
}

/**
 * The Files list view: composes the query bundle with the filter/sort, rows, selection,
 * upload, create, delete, download, row-menu, and drag-drop controllers, then presents them
 * through the shared `Resource` table. All CRUD details live in the hooks and the `files/lib`
 * domain layer; this component wires them together.
 */
export function FilesList({
  workspaceId,
  canEdit,
  permissionsLoading,
  data,
  currentFolderId,
  onNavigateListFolder,
  onOpenFile,
  onShareFile,
}: FilesListProps) {
  const commands = useMemo(() => getFilesCommandAvailability(canEdit), [canEdit])

  const {
    files,
    folders,
    members,
    pinnedFileIds,
    pinnedFolderIds,
    pinItem,
    unpinItem,
    membersById,
    folderById,
    folderSizeMap,
    descendantIndex,
  } = data

  const filesRef = useRef(files)
  filesRef.current = files
  const foldersRef = useRef(folders)
  foldersRef.current = folders

  const filtersController = useFilesFilters()
  const { renameFileTo, renameFolderTo } = useFilesRenameMutations(workspaceId)

  const listRename = useInlineRename({
    onSave: (rowId, name) => {
      const parsed = parseFilesRowId(rowId)
      if (parsed.kind === 'folder') return renameFolderTo(parsed.id, name)
      return renameFileTo(parsed.id, name)
    },
  })
  const breadcrumbRename = useInlineRename({
    onSave: (folderId, name) => renameFolderTo(folderId, name),
  })

  const { rows, visibleRowIds } = useFilesRows({
    files,
    folders,
    currentFolderId,
    debouncedSearchTerm: filtersController.debouncedSearchTerm,
    filters: filtersController.filters,
    sortColumn: filtersController.sortColumn,
    sortDirection: filtersController.sortDirection,
    pinnedFileIds,
    pinnedFolderIds,
    membersById,
    folderSizeMap,
    listRename,
  })

  /**
   * The keyboard shortcut needs the bulk delete callback before selection exists, so it reads
   * through a ref the callback re-arms every render.
   */
  const bulkDeleteRef = useRef<() => void>(() => {})
  const selection = useFilesSelection(visibleRowIds, {
    enabled: true,
    inlineRenameActive: listRename.editingId !== null,
    onDelete: () => bulkDeleteRef.current(),
  })

  const upload = useFilesUpload({ workspaceId, canUpload: commands.upload, currentFolderId })
  const deleteFlow = useFilesDeleteFlow(workspaceId)
  const downloads = useFilesDownloads(workspaceId)
  const creation = useFilesCreation({
    workspaceId,
    currentFolderId,
    filesRef,
    folders,
    onFolderCreated: listRename.startRename,
  })

  const handleBulkDelete = useCallback(() => {
    if (selection.selectedFileIds.length === 0 && selection.selectedFolderIds.length === 0) return
    deleteFlow.requestDelete({
      fileIds: selection.selectedFileIds,
      folderIds: selection.selectedFolderIds,
      name:
        selection.selectedFileIds.length + selection.selectedFolderIds.length === 1
          ? (files.find((file) => file.id === selection.selectedFileIds[0])?.name ??
            folders.find((folder) => folder.id === selection.selectedFolderIds[0])?.name ??
            'selected item')
          : `${selection.selectedFileIds.length + selection.selectedFolderIds.length} selected items`,
    })
  }, [
    selection.selectedFileIds,
    selection.selectedFolderIds,
    files,
    folders,
    deleteFlow.requestDelete,
  ])
  bulkDeleteRef.current = handleBulkDelete

  const handleTogglePin = useCallback(
    (item: FileResourceItem) => {
      const resourceType = item.kind === 'folder' ? 'folder' : 'file'
      const pinned = (item.kind === 'folder' ? pinnedFolderIds : pinnedFileIds).has(item.id)
      const mutation = pinned ? unpinItem : pinItem
      mutation.mutate({ workspaceId, resourceType, resourceId: item.id })
    },
    [workspaceId, pinnedFolderIds, pinnedFileIds, pinItem, unpinItem]
  )

  const handleBulkDownload = useCallback(() => {
    void downloads.downloadSelection(
      files.filter((file) => selection.selectedFileIds.includes(file.id)),
      selection.selectedFolderIds
    )
  }, [downloads.downloadSelection, files, selection.selectedFileIds, selection.selectedFolderIds])

  const handleOpenFolder = useCallback(
    (folderId: string) => onNavigateListFolder(folderId),
    [onNavigateListFolder]
  )

  const rowMenu = useFilesRowMenu({
    filesRef,
    folders,
    selectedRowIds: selection.selectedRowIds,
    visibleRowIds,
    selectedFileIds: selection.selectedFileIds,
    selectedFolderIds: selection.selectedFolderIds,
    selectOnly: selection.selectOnly,
    onOpenFolder: handleOpenFolder,
    onOpenFile,
    onStartRenameRow: listRename.startRename,
    onShareFile,
    onBulkDelete: handleBulkDelete,
    downloads,
    deleteFlow,
    pinnedFolderIds,
    pinnedFileIds,
    togglePin: handleTogglePin,
    descendantIndex,
    onMoved: selection.clearSelection,
  })

  const handleMoveItems = useCallback(
    async (fileIds: string[], folderIds: string[], targetFolderId: string) => {
      await deleteFlow.moveSelection(fileIds, folderIds, targetFolderId)
      selection.clearSelection()
    },
    [deleteFlow.moveSelection, selection.clearSelection]
  )

  const getRowLabel = useCallback((rowId: string) => {
    const parsed = parseFilesRowId(rowId)
    return parsed.kind === 'file'
      ? filesRef.current.find((file) => file.id === parsed.id)?.name
      : foldersRef.current.find((folder) => folder.id === parsed.id)?.name
  }, [])

  const rowDragDropConfig = useFilesRowDragDrop({
    canMove: commands.move,
    editingRowId: listRename.editingId,
    selectedRowIds: selection.selectedRowIds,
    visibleRowIds,
    descendantIndex,
    getFileFolderId: (fileId) => filesRef.current.find((file) => file.id === fileId)?.folderId,
    getFolderParentId: (folderId) =>
      foldersRef.current.find((folder) => folder.id === folderId)?.parentId ?? null,
    getRowLabel,
    onDragSelect: selection.selectOnly,
    onMoveItems: handleMoveItems,
    uploadFiles: upload.uploadFiles,
    resetExternalDrag: upload.resetExternalDrag,
  })

  const listRenameRef = useRef(listRename)
  listRenameRef.current = listRename
  const handleRowClick = useCallback(
    (rowId: string) => {
      if (listRenameRef.current.editingId !== rowId) {
        const parsed = parseFilesRowId(rowId)
        if (parsed.kind === 'folder') {
          onNavigateListFolder(parsed.id)
          return
        }
        const file = filesRef.current.find((f) => f.id === parsed.id)
        if (file) onOpenFile(file)
      }
    },
    [onNavigateListFolder, onOpenFile]
  )

  const {
    isOpen: isListContextMenuOpen,
    position: listContextMenuPosition,
    handleContextMenu: handleListContextMenu,
    closeMenu: closeListContextMenu,
  } = useContextMenu()

  const handleContentContextMenu = useCallback(
    (e: MouseEvent) => {
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

  const handleListUploadFile = useCallback(() => {
    if (!commands.upload || upload.uploading) return
    upload.openFilePicker()
    closeListContextMenu()
  }, [commands.upload, upload.uploading, upload.openFilePicker, closeListContextMenu])

  useRegisterGlobalCommands(() => [
    { id: 'files-upload', handler: () => upload.openFilePicker() },
    { id: 'files-new-file', handler: () => void creation.handleCreateFile() },
    { id: 'files-new-folder', handler: () => void creation.handleCreateFolder() },
  ])

  const searchConfig: SearchConfig = {
    value: filtersController.searchTerm,
    onChange: filtersController.setSearchTerm,
    onClearAll: () => filtersController.setSearchTerm(''),
    placeholder: 'Search files...',
  }

  const sortConfig: SortConfig = useMemo(
    () => ({
      options: [
        { id: 'name', label: 'Name' },
        { id: 'size', label: 'Size' },
        { id: 'type', label: 'Type' },
        { id: 'created', label: 'Created' },
        { id: 'updated', label: 'Last Updated' },
        { id: 'owner', label: 'Owner' },
      ],
      active: filtersController.activeSort,
      onSort: filtersController.onSort,
      onClear: filtersController.onClear,
    }),
    [filtersController.activeSort, filtersController.onSort, filtersController.onClear]
  )

  const headerActionsConfig = useMemo<ResourceAction[]>(
    () => [
      {
        text: upload.uploadButtonLabel,
        icon: Upload,
        onSelect: upload.openFilePicker,
        disabled: upload.uploading || !commands.upload,
      },
      {
        text: 'New folder',
        icon: FolderPlus,
        onSelect: creation.handleCreateFolder,
        disabled: creation.createFolderIsPending || !commands.createFolder,
      },
      {
        text: 'New file',
        icon: Plus,
        onSelect: creation.handleCreateFile,
        disabled: upload.uploading || creation.creatingFile || !commands.createFile,
        variant: 'primary',
      },
    ],
    [
      upload.uploadButtonLabel,
      upload.openFilePicker,
      upload.uploading,
      creation.handleCreateFolder,
      creation.handleCreateFile,
      creation.createFolderIsPending,
      creation.creatingFile,
      commands.upload,
      commands.createFolder,
      commands.createFile,
    ]
  )

  const listFolderChain = useMemo(
    () => breadcrumbFolderChain(currentFolderId, folderById),
    [currentFolderId, folderById]
  )

  const openListFolder = currentFolderId ? folderById.get(currentFolderId) : undefined

  const listBreadcrumbs = useMemo(
    (): BreadcrumbItem[] =>
      folderBreadcrumbItems({
        rootLabel: FILES_HEADER.rootLabel,
        rootIcon: FILES_HEADER.rootIcon,
        breadcrumbs: listFolderChain,
        onNavigate: onNavigateListFolder,
        currentFolderEditing:
          openListFolder && breadcrumbRename.editingId === openListFolder.id
            ? {
                isEditing: true,
                value: breadcrumbRename.editValue,
                onChange: breadcrumbRename.setEditValue,
                onSubmit: breadcrumbRename.submitRename,
                onCancel: breadcrumbRename.cancelRename,
              }
            : undefined,
        currentFolderActions:
          openListFolder && (canEdit || permissionsLoading)
            ? [
                {
                  label: 'Rename',
                  icon: Pencil,
                  disabled: !canEdit,
                  onClick: () =>
                    breadcrumbRename.startRename(openListFolder.id, openListFolder.name),
                },
              ]
            : undefined,
      }),
    [
      listFolderChain,
      openListFolder,
      onNavigateListFolder,
      canEdit,
      permissionsLoading,
      breadcrumbRename.editingId,
      breadcrumbRename.editValue,
      breadcrumbRename.setEditValue,
      breadcrumbRename.submitRename,
      breadcrumbRename.cancelRename,
      breadcrumbRename.startRename,
    ]
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
    if (filtersController.typeFilter.length > 0) {
      const typeLabels: Record<string, string> = {
        document: 'Documents',
        image: 'Images',
        audio: 'Audio',
        video: 'Video',
      }
      const label =
        filtersController.typeFilter.length === 1
          ? `Type: ${typeLabels[filtersController.typeFilter[0]]}`
          : `Type: ${filtersController.typeFilter.length} selected`
      tags.push({ label, onRemove: () => filtersController.setTypeFilter([]) })
    }
    if (filtersController.sizeFilter.length > 0) {
      const sizeLabels: Record<string, string> = {
        small: 'Small',
        medium: 'Medium',
        large: 'Large',
      }
      const label =
        filtersController.sizeFilter.length === 1
          ? `Size: ${sizeLabels[filtersController.sizeFilter[0]]}`
          : `Size: ${filtersController.sizeFilter.length} selected`
      tags.push({ label, onRemove: () => filtersController.setSizeFilter([]) })
    }
    if (filtersController.uploadedByFilter.length > 0) {
      const label =
        filtersController.uploadedByFilter.length === 1
          ? `Uploaded by: ${membersById.get(filtersController.uploadedByFilter[0])?.name ?? '1 member'}`
          : `Uploaded by: ${filtersController.uploadedByFilter.length} members`
      tags.push({ label, onRemove: () => filtersController.setUploadedByFilter([]) })
    }
    return tags
  }, [
    filtersController.typeFilter,
    filtersController.sizeFilter,
    filtersController.uploadedByFilter,
    filtersController.setTypeFilter,
    filtersController.setSizeFilter,
    filtersController.setUploadedByFilter,
    membersById,
  ])

  return (
    <div
      className='relative flex h-full min-h-0 w-full min-w-0 max-w-none flex-1 flex-col overflow-hidden'
      onDragEnter={commands.upload ? upload.handleDragEnter : undefined}
      onDragLeave={commands.upload ? upload.handleDragLeave : undefined}
      onDragOver={commands.upload ? upload.handleDragOver : undefined}
      onDrop={commands.upload ? upload.handleDrop : undefined}
    >
      <Resource onContextMenu={handleContentContextMenu}>
        <Resource.Header
          icon={FILES_HEADER.rootIcon}
          title={FILES_HEADER.rootLabel}
          breadcrumbs={listBreadcrumbs}
          actions={headerActionsConfig}
        />
        <Resource.Options
          search={searchConfig}
          sort={sortConfig}
          filterTags={filterTags}
          filter={{
            content: (
              <FilesFilterPanel
                typeFilter={filtersController.typeFilter}
                sizeFilter={filtersController.sizeFilter}
                uploadedByFilter={filtersController.uploadedByFilter}
                memberOptions={memberOptions}
                membersById={membersById}
                onTypeChange={filtersController.setTypeFilter}
                onSizeChange={filtersController.setSizeFilter}
                onUploadedByChange={filtersController.setUploadedByFilter}
                onClearAll={filtersController.clearFilters}
              />
            ),
          }}
        />
        <Resource.Table
          columns={COLUMNS}
          rows={rows}
          selectable={selection.selectableConfig}
          rowDragDrop={rowDragDropConfig}
          onRowClick={handleRowClick}
          onRowContextMenu={rowMenu.handleRowContextMenu}
          overlay={
            <>
              <FilesActionBar
                selectedCount={selection.selectedRowIds.size}
                onDownload={handleBulkDownload}
                onMove={commands.move ? rowMenu.handleMove : undefined}
                moveOptions={commands.move ? rowMenu.moveOptions : undefined}
                onDelete={commands.delete ? handleBulkDelete : undefined}
                isLoading={
                  deleteFlow.isDeleting || deleteFlow.isMoving || downloads.isDownloadingArchive
                }
              />
              {upload.isDraggingOver ? (
                <div className='pointer-events-none absolute inset-0 z-[var(--z-dropdown)] flex flex-col items-center justify-center gap-2 border border-[var(--brand-secondary)] border-dashed bg-[var(--surface-4)] transition-colors'>
                  <Upload className='size-5 text-[var(--brand-secondary)]' />
                  <div className='flex flex-col gap-0.5 text-center'>
                    <p className='text-[14px] text-[var(--brand-secondary)]'>Drop to upload</p>
                    <p className='text-[11px] text-[var(--text-tertiary)]'>
                      Release files here to add them to this workspace
                    </p>
                  </div>
                </div>
              ) : null}
            </>
          }
        />
      </Resource>

      <FilesListContextMenu
        isOpen={isListContextMenuOpen}
        position={listContextMenuPosition}
        onClose={closeListContextMenu}
        onCreateFile={creation.handleCreateFile}
        onCreateFolder={creation.handleCreateFolder}
        onUploadFile={handleListUploadFile}
        disableCreate={upload.uploading || creation.creatingFile || !commands.createFile}
        disableCreateFolder={creation.createFolderIsPending || !commands.createFolder}
        disableUpload={upload.uploading || !commands.upload}
      />

      <FileRowContextMenu
        isOpen={rowMenu.isOpen}
        position={rowMenu.position}
        onClose={rowMenu.closeMenu}
        onOpen={rowMenu.handleOpen}
        onDownload={rowMenu.handleDownload}
        onRename={rowMenu.handleRename}
        onDelete={rowMenu.handleDelete}
        onMove={rowMenu.handleMove}
        onShare={
          commands.share && rowMenu.contextMenuItem?.kind === 'file'
            ? rowMenu.handleShare
            : undefined
        }
        onTogglePin={rowMenu.handleTogglePin}
        pinned={rowMenu.isItemPinned}
        moveOptions={rowMenu.moveOptions}
        canEdit={canEdit}
        selectedCount={selection.selectedRowIds.size}
      />

      <DeleteConfirmModal
        open={deleteFlow.showDeleteConfirm}
        onOpenChange={deleteFlow.setShowDeleteConfirm}
        fileName={deleteFlow.deleteTarget?.name}
        fileCount={deleteFlow.deleteTarget?.fileIds.length ?? 0}
        folderCount={deleteFlow.deleteTarget?.folderIds.length ?? 0}
        onDelete={() => void deleteFlow.confirmDelete(selection.clearSelection)}
        isPending={deleteFlow.isDeleting}
      />

      <input
        ref={upload.fileInputRef}
        type='file'
        className='hidden'
        onChange={upload.handleFileChange}
        disabled={upload.uploading || !commands.upload}
        accept={upload.fileInputAccept}
        multiple
      />
    </div>
  )
}
