'use client'

import { useCallback, useMemo, useState } from 'react'
import { ChipConfirmModal } from '@sim/emcn'
import {
  ChevronDown,
  ChevronUp,
  Database,
  FileText,
  Pencil,
  Plus,
  TagIcon,
  Trash,
} from '@sim/emcn/icons'
import { useParams, useRouter } from 'next/navigation'
import type { ChunkData } from '@/lib/knowledge/types'
import type {
  BreadcrumbItem,
  FilterTag,
  PaginationConfig,
  ResourceAction,
  ResourceColumn,
  SearchConfig,
  SelectableConfig,
  SortConfig,
} from '@/app/workspace/[workspaceId]/components'
import { Resource } from '@/app/workspace/[workspaceId]/components'
import {
  folderedResourceListHref,
  useFolderAncestors,
} from '@/app/workspace/[workspaceId]/components/folders'
import { useContextMenu } from '@/app/workspace/[workspaceId]/components/hooks'
import {
  ChunkContextMenu,
  ChunkEditor,
  DeleteChunkModal,
  DocumentTagsModal,
} from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/components'
import { useChunkCommands } from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/hooks/use-chunk-commands'
import { useChunkEditorController } from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/hooks/use-chunk-editor-controller'
import { useChunkListController } from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/hooks/use-chunk-list-controller'
import { useDocumentCommands } from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/hooks/use-document-commands'
import { useDocumentDetailDialogs } from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/hooks/use-document-detail-dialogs'
import { ChunkFilterPanel } from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/presentation/chunk-filter-panel'
import {
  buildChunkRows,
  buildProcessingPlaceholderRow,
} from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/presentation/chunk-rows'
import { buildDocumentTrail } from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/presentation/document-breadcrumbs'
import { UnsavedChangesModal } from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/presentation/unsaved-changes-modal'
import { ActionBar } from '@/app/workspace/[workspaceId]/knowledge/[id]/components'
import { getDocumentIcon } from '@/app/workspace/[workspaceId]/knowledge/components'
import { useUserPermissionsContext } from '@/app/workspace/[workspaceId]/providers/workspace-permissions-provider'
import { useDocument, useKnowledgeBase } from '@/hooks/kb/use-knowledge'

const CHUNK_COLUMNS: ResourceColumn[] = [
  { id: 'content', header: 'Content' },
  { id: 'index', header: 'Index', widthMultiplier: 0.6 },
  { id: 'tokens', header: 'Tokens', widthMultiplier: 0.6 },
  { id: 'status', header: 'Status', widthMultiplier: 0.75 },
]

interface DocumentProps {
  knowledgeBaseId: string
  documentId: string
  knowledgeBaseName?: string
  documentName?: string
}

/**
 * Document detail shell. Deliberately only composition: the chunk list lives
 * in `useChunkListController`, the inline editor in `useChunkEditorController`,
 * chunk mutations in `useChunkCommands`, document-level commands in
 * `useDocumentCommands`, dialog state in `useDocumentDetailDialogs`, and row /
 * breadcrumb / filter rendering in `presentation/`.
 */
export function Document({
  knowledgeBaseId,
  documentId,
  knowledgeBaseName,
  documentName,
}: DocumentProps) {
  const workspaceId = useParams().workspaceId as string
  const router = useRouter()
  const userPermissions = useUserPermissionsContext()
  const canEdit = userPermissions.canEdit === true

  const { knowledgeBase } = useKnowledgeBase(knowledgeBaseId)
  const { document: documentData, error: documentError } = useDocument(knowledgeBaseId, documentId)

  /** The base's folder trail, so this route's header matches the base's and the list's. */
  const { ancestors: folderChain } = useFolderAncestors({
    resourceType: 'knowledge_base',
    workspaceId,
    folderId: knowledgeBase?.folderId,
  })

  // --- Controllers --------------------------------------------------------------
  const list = useChunkListController({ knowledgeBaseId, documentId })
  const editor = useChunkEditorController({
    displayChunks: list.displayChunks,
    currentPage: list.currentPage,
    totalPages: list.totalPages,
    goToPage: list.goToPage,
  })
  const chunkCommands = useChunkCommands({
    knowledgeBaseId,
    documentId,
    displayChunks: list.displayChunks,
    updateChunk: list.updateChunk,
    selectedChunks: list.selectedChunks,
    clearSelection: list.clearSelection,
  })

  // --- Derived document metadata ---------------------------------------------------
  const effectiveDocumentName = documentData?.filename || documentName || 'Document'
  /**
   * Breadcrumb labels. Fall back to the canonical '…' placeholder while names
   * load (mirroring loading.tsx) instead of the generic "Knowledge Base" /
   * "Document" labels used elsewhere.
   */
  const knowledgeBaseCrumbLabel = knowledgeBase?.name || knowledgeBaseName || '…'
  const documentCrumbLabel = documentData?.filename || documentName || '…'
  const DocumentIcon = getDocumentIcon(documentData?.mimeType ?? '', effectiveDocumentName)
  const isCompleted = documentData?.processingStatus === 'completed'

  const documentCommands = useDocumentCommands({
    knowledgeBaseId,
    documentId,
    workspaceId,
    documentName: effectiveDocumentName,
  })
  const { docRename } = documentCommands

  const dialogs = useDocumentDetailDialogs()

  const combinedError = documentError || list.searchError || list.chunksError

  // --- Context menu ---------------------------------------------------------------
  const {
    isOpen: isContextMenuOpen,
    position: contextMenuPosition,
    handleContextMenu: baseHandleContextMenu,
    closeMenu: closeContextMenu,
  } = useContextMenu()
  const [contextMenuChunk, setContextMenuChunk] = useState<ChunkData | null>(null)

  const handleChunkContextMenu = useCallback(
    (e: React.MouseEvent, rowId: string) => {
      const chunk = list.displayChunks.find((c) => c.id === rowId)
      if (!chunk) return

      if (userPermissions.canEdit && !list.selectedChunks.has(chunk.id)) {
        list.selectOnly(chunk.id)
      }

      setContextMenuChunk(chunk)
      baseHandleContextMenu(e)
    },
    [
      list.displayChunks,
      list.selectedChunks,
      list.selectOnly,
      baseHandleContextMenu,
      userPermissions.canEdit,
    ]
  )

  const handleEmptyContextMenu = useCallback(
    (e: React.MouseEvent) => {
      setContextMenuChunk(null)
      baseHandleContextMenu(e)
    },
    [baseHandleContextMenu]
  )

  const handleContextMenuClose = useCallback(() => {
    closeContextMenu()
    setContextMenuChunk(null)
  }, [closeContextMenu])

  // --- Navigation (guarded against unsaved edits) --------------------------------------
  const handleNavToFolder = useCallback(
    (folderId: string | null) => {
      editor.guardRouteChange(() =>
        router.push(folderedResourceListHref('knowledge_base', workspaceId, folderId))
      )
    },
    [editor.guardRouteChange, router, workspaceId]
  )

  const handleNavToKBDetail = useCallback(() => {
    editor.guardRouteChange(() =>
      router.push(`/workspace/${workspaceId}/knowledge/${knowledgeBaseId}`)
    )
  }, [editor.guardRouteChange, router, workspaceId, knowledgeBaseId])

  const handleClearSelectedChunk = useCallback(
    () => editor.setSelectedChunkId(null),
    [editor.setSelectedChunkId]
  )

  // --- Breadcrumbs ----------------------------------------------------------------------
  const documentTrail = useCallback(
    (last: BreadcrumbItem, onDocumentClick?: () => void): BreadcrumbItem[] =>
      buildDocumentTrail(
        {
          folderChain,
          onNavigateFolder: handleNavToFolder,
          knowledgeBaseCrumbLabel,
          knowledgeBaseCrumbIcon: Database,
          documentCrumbLabel,
          documentIcon: DocumentIcon,
          onKnowledgeBaseClick: handleNavToKBDetail,
        },
        last,
        onDocumentClick
      ),
    [
      folderChain,
      handleNavToFolder,
      handleNavToKBDetail,
      knowledgeBaseCrumbLabel,
      documentCrumbLabel,
      DocumentIcon,
    ]
  )

  const breadcrumbs = useMemo<BreadcrumbItem[]>(
    () =>
      documentTrail(
        combinedError
          ? { label: 'Error', terminal: true }
          : {
              label: documentCrumbLabel,
              icon: DocumentIcon,
              editing: docRename.editingId
                ? {
                    isEditing: true,
                    value: docRename.editValue,
                    onChange: docRename.setEditValue,
                    onSubmit: docRename.submitRename,
                    onCancel: docRename.cancelRename,
                    disabled: docRename.isSaving,
                  }
                : undefined,
              dropdownItems: [
                ...(userPermissions.canEdit
                  ? [
                      { label: 'Rename', icon: Pencil, onClick: documentCommands.startRename },
                      { label: 'Tags', icon: TagIcon, onClick: dialogs.tagsModal.open },
                      { label: 'Delete', icon: Trash, onClick: dialogs.deleteDocumentDialog.open },
                    ]
                  : []),
              ],
            }
      ),
    [
      documentTrail,
      combinedError,
      documentCrumbLabel,
      DocumentIcon,
      docRename.editingId,
      docRename.editValue,
      docRename.isSaving,
      docRename.setEditValue,
      docRename.submitRename,
      docRename.cancelRename,
      userPermissions.canEdit,
      documentCommands.startRename,
      dialogs.tagsModal.open,
      dialogs.deleteDocumentDialog.open,
    ]
  )

  const newChunkBreadcrumbs = useMemo<BreadcrumbItem[]>(
    () => documentTrail({ label: 'New Chunk', terminal: true }, editor.handleBackAttempt),
    [documentTrail, editor.handleBackAttempt]
  )

  const editChunkBreadcrumbs = useMemo<BreadcrumbItem[]>(
    () =>
      documentTrail(
        {
          label: editor.selectedChunk ? `Chunk #${editor.selectedChunk.chunkIndex}` : '',
          terminal: true,
        },
        editor.handleBackAttempt
      ),
    [documentTrail, editor.handleBackAttempt, editor.selectedChunk]
  )

  const loadingBreadcrumbs = useMemo<BreadcrumbItem[]>(
    () => documentTrail({ label: '…', terminal: true }, handleClearSelectedChunk),
    [documentTrail, handleClearSelectedChunk]
  )

  // --- Table configs ----------------------------------------------------------------------
  const searchConfig: SearchConfig | undefined = isCompleted
    ? {
        value: list.searchQuery,
        onChange: list.handleSearchChange,
        placeholder: 'Search chunks...',
      }
    : undefined

  const sortConfig: SortConfig = useMemo(
    () => ({
      options: [
        { id: 'index', label: 'Index' },
        { id: 'tokens', label: 'Tokens' },
        { id: 'status', label: 'Status' },
      ],
      active: list.activeSort,
      /** Sorting (or clearing the sort) resets pagination to the first page. */
      onSort: (column, direction) => {
        list.onSortColumn(column, direction)
        void list.goToPage(1)
      },
      onClear: () => {
        list.onClearSort()
        void list.goToPage(1)
      },
    }),
    [list.activeSort, list.onSortColumn, list.onClearSort, list.goToPage]
  )

  const filterTags: FilterTag[] = useMemo(
    () =>
      list.enabledFilter.map((value) => ({
        label: `Status: ${value === 'enabled' ? 'Enabled' : 'Disabled'}`,
        onRemove: () => {
          list.setEnabledFilter(list.enabledFilter.filter((v) => v !== value))
        },
      })),
    [list.enabledFilter, list.setEnabledFilter]
  )

  const selectableConfig: SelectableConfig | undefined = isCompleted
    ? {
        selectedIds: list.selectedChunks,
        onSelectRow: list.handleSelectChunk,
        onSelectAll: list.handleSelectAll,
        isAllSelected: list.isAllSelected,
        disabled: !canEdit,
      }
    : undefined

  const paginationConfig: PaginationConfig | undefined =
    isCompleted && list.totalPages > 1
      ? {
          currentPage: list.currentPage,
          totalPages: list.totalPages,
          onPageChange: list.goToPage,
        }
      : undefined

  const chunkRows = useMemo(
    () =>
      isCompleted
        ? buildChunkRows({ chunks: list.displayChunks, searchQuery: list.searchQuery })
        : buildProcessingPlaceholderRow(documentData?.processingStatus),
    [isCompleted, documentData?.processingStatus, list.displayChunks, list.searchQuery]
  )

  const handleChunkClick = useCallback(
    (rowId: string) => {
      editor.setSelectedChunkId(rowId)
    },
    [editor.setSelectedChunkId]
  )

  const handleDeleteChunk = useCallback(
    (chunkId: string) => {
      const chunk = list.displayChunks.find((c) => c.id === chunkId)
      if (chunk) {
        dialogs.deleteChunkDialog.request(chunk)
      }
    },
    [list.displayChunks, dialogs.deleteChunkDialog.request]
  )

  const handleCloseDeleteChunkModal = () => {
    const target = dialogs.deleteChunkDialog.target
    if (target) {
      list.removeFromSelection(target.id)
    }
    dialogs.deleteChunkDialog.close()
  }

  // --- Editor actions ----------------------------------------------------------------------
  const createAction = useMemo(
    () => ({
      label: 'New chunk',
      onClick: editor.handleNewChunk,
      disabled: documentData?.processingStatus === 'failed' || !canEdit,
    }),
    [editor.handleNewChunk, documentData?.processingStatus, canEdit]
  )

  const handleSaveClick = useCallback(() => {
    void editor.handleSave()
  }, [editor.handleSave])

  const createActions = useMemo<ResourceAction[]>(
    () => [
      {
        text: editor.saveLabel,
        onSelect: handleSaveClick,
        disabled: !editor.isDirty || editor.saveStatus === 'saving',
      },
    ],
    [editor.saveLabel, handleSaveClick, editor.isDirty, editor.saveStatus]
  )

  const editorActions = useMemo<ResourceAction[]>(() => {
    const actions: ResourceAction[] = [
      {
        text: 'Previous chunk',
        icon: ChevronUp,
        onSelect: () => editor.handleNavigateChunk('prev'),
        disabled: !editor.canNavigatePrev,
      },
      {
        text: 'Next chunk',
        icon: ChevronDown,
        onSelect: () => editor.handleNavigateChunk('next'),
        disabled: !editor.canNavigateNext,
      },
    ]
    if (canEdit) {
      actions.push({
        text: editor.saveLabel,
        onSelect: handleSaveClick,
        disabled: !editor.isDirty || editor.saveStatus === 'saving',
      })
    }
    return actions
  }, [
    editor.handleNavigateChunk,
    editor.canNavigatePrev,
    editor.canNavigateNext,
    canEdit,
    editor.saveLabel,
    handleSaveClick,
    editor.isDirty,
    editor.saveStatus,
  ])

  // --- Editor views --------------------------------------------------------------------------
  if (editor.isCreatingNewChunk && documentData) {
    return (
      <>
        <Resource>
          <Resource.Header
            icon={FileText}
            breadcrumbs={newChunkBreadcrumbs}
            actions={createActions}
          />
          <ChunkEditor
            key='new-chunk'
            mode='create'
            document={documentData}
            knowledgeBaseId={knowledgeBaseId}
            canEdit
            maxChunkSize={knowledgeBase?.chunkingConfig?.maxSize}
            onDirtyChange={editor.setIsDirty}
            onSaveStatusChange={editor.setSaveStatus}
            saveRef={editor.saveRef}
            onCreated={editor.handleChunkCreated}
          />
        </Resource>

        <UnsavedChangesModal
          open={editor.showUnsavedChangesAlert}
          onOpenChange={editor.handleUnsavedChangesOpenChange}
          onDiscard={editor.handleDiscardChanges}
        />
      </>
    )
  }

  if (editor.selectedChunkId) {
    if (!editor.selectedChunk || !documentData) {
      return (
        <Resource>
          <Resource.Header icon={FileText} breadcrumbs={loadingBreadcrumbs} />
          <div className='flex flex-1 items-center justify-center'>
            <span className='text-[var(--text-muted)] text-sm'>Loading chunk…</span>
          </div>
        </Resource>
      )
    }

    return (
      <>
        <Resource>
          <Resource.Header
            icon={FileText}
            breadcrumbs={editChunkBreadcrumbs}
            actions={editorActions}
          />
          <ChunkEditor
            key={editor.selectedChunk.id}
            chunk={editor.selectedChunk}
            document={documentData}
            knowledgeBaseId={knowledgeBaseId}
            canEdit={canEdit}
            maxChunkSize={knowledgeBase?.chunkingConfig?.maxSize}
            onDirtyChange={editor.setIsDirty}
            onSaveStatusChange={editor.setSaveStatus}
            saveRef={editor.saveRef}
          />
        </Resource>

        <UnsavedChangesModal
          open={editor.showUnsavedChangesAlert}
          onOpenChange={editor.handleUnsavedChangesOpenChange}
          onDiscard={editor.handleDiscardChanges}
        />
      </>
    )
  }

  return (
    <>
      <Resource onContextMenu={handleEmptyContextMenu}>
        <Resource.Header
          icon={FileText}
          title={effectiveDocumentName}
          breadcrumbs={breadcrumbs}
          actions={[
            {
              text: createAction.label,
              icon: Plus,
              onSelect: createAction.onClick,
              disabled: createAction.disabled,
              variant: 'primary',
            },
          ]}
        />
        <Resource.Options
          search={combinedError ? undefined : searchConfig}
          sort={combinedError ? undefined : sortConfig}
          filterTags={combinedError ? undefined : filterTags}
          filter={
            combinedError
              ? undefined
              : {
                  content: (
                    <ChunkFilterPanel
                      enabledFilter={list.enabledFilter}
                      onEnabledFilterChange={list.setEnabledFilter}
                    />
                  ),
                }
          }
        />
        <Resource.Table
          columns={CHUNK_COLUMNS}
          rows={combinedError ? [] : chunkRows}
          selectable={combinedError ? undefined : selectableConfig}
          onRowClick={isCompleted ? handleChunkClick : undefined}
          onRowContextMenu={isCompleted ? handleChunkContextMenu : undefined}
          pagination={paginationConfig}
        />
      </Resource>

      <DocumentTagsModal
        open={dialogs.tagsModal.isOpen}
        onOpenChange={dialogs.tagsModal.setOpen}
        knowledgeBaseId={knowledgeBaseId}
        documentId={documentId}
        documentData={documentData}
      />

      <DeleteChunkModal
        chunk={dialogs.deleteChunkDialog.target}
        knowledgeBaseId={knowledgeBaseId}
        documentId={documentId}
        isOpen={dialogs.deleteChunkDialog.target !== null}
        onClose={handleCloseDeleteChunkModal}
      />

      <ActionBar
        className={paginationConfig ? 'bottom-[72px]' : undefined}
        selectedCount={list.selectedChunks.size}
        onEnable={list.selectedCounts.disabled > 0 ? chunkCommands.bulkEnable : undefined}
        onDisable={list.selectedCounts.enabled > 0 ? chunkCommands.bulkDisable : undefined}
        onDelete={chunkCommands.bulkDelete}
        enabledCount={list.selectedCounts.enabled}
        disabledCount={list.selectedCounts.disabled}
        isLoading={chunkCommands.isBulkOperating}
      />

      <ChipConfirmModal
        open={dialogs.deleteDocumentDialog.isOpen}
        onOpenChange={dialogs.deleteDocumentDialog.setOpen}
        srTitle='Delete Document'
        title='Delete Document'
        text={[
          'Are you sure you want to delete ',
          { text: effectiveDocumentName, bold: true },
          '? ',
          {
            text: `This will permanently delete the document and all ${documentData?.chunkCount ?? 0} chunk${documentData?.chunkCount === 1 ? '' : 's'} within it.`,
            error: true,
          },
          ' This action cannot be undone.',
        ]}
        confirm={{
          label: 'Delete Document',
          onClick: documentCommands.deleteDocument,
          pending: documentCommands.isDeletingDocument,
          pendingLabel: 'Deleting...',
        }}
      />

      <ChunkContextMenu
        isOpen={isContextMenuOpen}
        position={contextMenuPosition}
        onClose={handleContextMenuClose}
        hasChunk={contextMenuChunk !== null}
        isChunkEnabled={contextMenuChunk?.enabled ?? true}
        selectedCount={list.selectedChunks.size}
        enabledCount={list.selectedCounts.enabled}
        disabledCount={list.selectedCounts.disabled}
        onOpenInNewTab={
          contextMenuChunk
            ? () => {
                const url = `/workspace/${workspaceId}/knowledge/${knowledgeBaseId}/${documentId}?chunk=${contextMenuChunk.id}`
                window.open(url, '_blank')
              }
            : undefined
        }
        onEdit={
          contextMenuChunk
            ? () => {
                editor.setSelectedChunkId(contextMenuChunk.id)
              }
            : undefined
        }
        onCopyContent={
          contextMenuChunk
            ? () => {
                navigator.clipboard.writeText(contextMenuChunk.content)
              }
            : undefined
        }
        onToggleEnabled={
          contextMenuChunk
            ? list.selectedChunks.size > 1
              ? () => {
                  if (list.selectedCounts.disabled > 0) {
                    chunkCommands.bulkEnable()
                  } else {
                    chunkCommands.bulkDisable()
                  }
                }
              : () => chunkCommands.toggleEnabled(contextMenuChunk.id)
            : undefined
        }
        onDelete={
          contextMenuChunk
            ? list.selectedChunks.size > 1
              ? chunkCommands.bulkDelete
              : () => handleDeleteChunk(contextMenuChunk.id)
            : undefined
        }
        onAddChunk={editor.handleNewChunk}
        disableToggleEnabled={!canEdit}
        disableDelete={!canEdit}
        disableEdit={!canEdit}
        disableAddChunk={!canEdit || documentData?.processingStatus === 'failed'}
      />
    </>
  )
}
