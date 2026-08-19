'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Database, DatabaseX, Pencil, Plus, TagIcon, Trash } from '@sim/emcn/icons'
import { useParams, useRouter } from 'next/navigation'
import { usePostHog } from 'posthog-js/react'
import type { DocumentData } from '@/lib/knowledge/types'
import { captureEvent } from '@/lib/posthog/client'
import type {
  BreadcrumbItem,
  FilterTag,
  ResourceAction,
  ResourceColumn,
  SelectableConfig,
  SortConfig,
} from '@/app/workspace/[workspaceId]/components'
import { Resource } from '@/app/workspace/[workspaceId]/components'
import {
  FOLDERED_RESOURCE_HEADERS,
  folderBreadcrumbItems,
  useFolderAncestors,
} from '@/app/workspace/[workspaceId]/components/folders'
import { useContextMenu } from '@/app/workspace/[workspaceId]/components/hooks'
import {
  ActionBar,
  DocumentContextMenu,
} from '@/app/workspace/[workspaceId]/knowledge/[id]/components'
import { BaseDetailDialogsView } from '@/app/workspace/[workspaceId]/knowledge/[id]/dialogs/base-detail-dialogs'
import { useBaseDetailDialogs } from '@/app/workspace/[workspaceId]/knowledge/[id]/hooks/use-base-detail-dialogs'
import { useDocumentCommands } from '@/app/workspace/[workspaceId]/knowledge/[id]/hooks/use-document-list-commands'
import {
  type DocumentListController,
  useDocumentListController,
} from '@/app/workspace/[workspaceId]/knowledge/[id]/hooks/use-document-list-controller'
import { useDocumentTagFilters } from '@/app/workspace/[workspaceId]/knowledge/[id]/hooks/use-document-tag-filters'
import { useKnowledgeBaseCommands } from '@/app/workspace/[workspaceId]/knowledge/[id]/hooks/use-knowledge-base-commands'
import { DocumentFilterPanel } from '@/app/workspace/[workspaceId]/knowledge/[id]/presentation/document-filter-panel'
import { buildDocumentRows } from '@/app/workspace/[workspaceId]/knowledge/[id]/presentation/document-rows'
import { useUserPermissionsContext } from '@/app/workspace/[workspaceId]/providers/workspace-permissions-provider'
import { useKnowledgeBase } from '@/hooks/kb/use-knowledge'
import { useKnowledgeBaseTagDefinitions } from '@/hooks/kb/use-knowledge-base-tag-definitions'

const DOCUMENT_COLUMNS: ResourceColumn[] = [
  { id: 'name', header: 'Name', widthMultiplier: 0.8 },
  { id: 'size', header: 'Size', widthMultiplier: 0.75 },
  { id: 'tokens', header: 'Tokens', widthMultiplier: 0.75 },
  { id: 'chunks', header: 'Chunks', widthMultiplier: 0.75 },
  { id: 'uploaded', header: 'Uploaded' },
  { id: 'status', header: 'Status', widthMultiplier: 0.75 },
  { id: 'tags', header: 'Tags' },
]

interface KnowledgeBaseProps {
  id: string
  knowledgeBaseName?: string
  workspaceId?: string
}

/**
 * Knowledge-base detail shell. Deliberately only composition: the document
 * list lives in `useDocumentListController`, tag filters in
 * `useDocumentTagFilters`, mutations in the command hooks, dialog state in
 * `useBaseDetailDialogs`, and row/filter rendering in `presentation/`.
 */
export function KnowledgeBase({
  id,
  knowledgeBaseName: passedKnowledgeBaseName,
  workspaceId: propWorkspaceId,
}: KnowledgeBaseProps) {
  const params = useParams()
  const workspaceId = propWorkspaceId || (params.workspaceId as string)
  const router = useRouter()
  const posthog = usePostHog()

  useEffect(() => {
    captureEvent(posthog, 'knowledge_base_opened', {
      knowledge_base_id: id,
      knowledge_base_name: passedKnowledgeBaseName ?? 'Unknown',
    })
  }, [id, passedKnowledgeBaseName, posthog])

  const userPermissions = useUserPermissionsContext()

  const { knowledgeBase, error: knowledgeBaseError } = useKnowledgeBase(id)
  const { tagDefinitions } = useKnowledgeBaseTagDefinitions(id)

  const knowledgeBaseName = knowledgeBase?.name || passedKnowledgeBaseName || 'Knowledge Base'
  /**
   * Breadcrumb leaf label. Falls back to the canonical '…' placeholder while
   * the name loads (mirroring loading.tsx) instead of duplicating the root
   * "Knowledge bases" crumb.
   */
  const knowledgeBaseCrumbLabel = knowledgeBase?.name || passedKnowledgeBaseName || '…'

  // --- Dialogs ---------------------------------------------------------------
  const dialogs = useBaseDetailDialogs()

  // --- Base commands -----------------------------------------------------------
  const baseCommands = useKnowledgeBaseCommands({
    knowledgeBaseId: id,
    workspaceId,
    knowledgeBaseName,
    onOpenAddDocuments: dialogs.addDocumentsModal.open,
    onOpenTags: dialogs.tagsModal.open,
    onOpenDelete: dialogs.deleteBaseDialog.open,
  })
  const { kbRename } = baseCommands

  // --- Document list -----------------------------------------------------------
  /**
   * The tag-filter controller is created before the list controller (the list
   * consumes its projection), so its change side effect reaches the list
   * through a ref — by the time a filter interaction fires, the ref is set.
   */
  const listRef = useRef<DocumentListController | null>(null)
  const tagFilters = useDocumentTagFilters({
    onFiltersChange: useCallback(() => {
      listRef.current?.setCurrentPage(1)
      listRef.current?.clearSelection()
    }, []),
  })
  const list = useDocumentListController({
    knowledgeBaseId: id,
    tagFilters: tagFilters.activeFilters,
    suspendPolling: baseCommands.isDeleting,
  })
  listRef.current = list

  // --- Document commands ---------------------------------------------------------
  const documentCommands = useDocumentCommands({
    knowledgeBaseId: id,
    documents: list.documents,
    updateDocument: list.updateDocument,
    selectedDocuments: list.selectedDocuments,
    isSelectAllMode: list.isSelectAllMode,
    enabledFilter: list.enabledFilter,
    clearSelection: list.clearSelection,
    removeFromSelection: list.removeFromSelection,
  })

  // --- Context menu ---------------------------------------------------------------
  const {
    isOpen: isContextMenuOpen,
    position: contextMenuPosition,
    handleContextMenu: baseHandleContextMenu,
    closeMenu: closeContextMenu,
  } = useContextMenu()

  const [contextMenuDocument, setContextMenuDocument] = useState<DocumentData | null>(null)

  const handleDocumentContextMenu = useCallback(
    (e: React.MouseEvent, docId: string) => {
      const doc = list.documents.find((d) => d.id === docId)
      if (!doc) return

      if (!list.selectedDocuments.has(doc.id)) {
        list.selectOnly(doc.id)
      }

      setContextMenuDocument(doc)
      baseHandleContextMenu(e)
    },
    [list.documents, list.selectedDocuments, list.selectOnly, baseHandleContextMenu]
  )

  const handleEmptyContextMenu = useCallback(
    (e: React.MouseEvent) => {
      setContextMenuDocument(null)
      baseHandleContextMenu(e)
    },
    [baseHandleContextMenu]
  )

  const handleContextMenuClose = useCallback(() => {
    closeContextMenu()
    setContextMenuDocument(null)
  }, [closeContextMenu])

  /**
   * The base's own folder trail, so the header reads `Knowledge Base / Research / Papers`
   * exactly as the list does one level up.
   */
  const { ancestors: folderChain } = useFolderAncestors({
    resourceType: 'knowledge_base',
    workspaceId,
    folderId: knowledgeBase?.folderId,
  })

  const error = knowledgeBaseError || list.documentsError

  const breadcrumbs: BreadcrumbItem[] = useMemo(
    () =>
      folderBreadcrumbItems({
        rootLabel: FOLDERED_RESOURCE_HEADERS.knowledge_base.rootLabel,
        rootIcon: FOLDERED_RESOURCE_HEADERS.knowledge_base.rootIcon,
        breadcrumbs: folderChain,
        onNavigate: baseCommands.navigateToFolder,
        trailing: [
          {
            label: knowledgeBaseCrumbLabel,
            icon: Database,
            editing: kbRename.editingId
              ? {
                  isEditing: true,
                  value: kbRename.editValue,
                  onChange: kbRename.setEditValue,
                  onSubmit: kbRename.submitRename,
                  onCancel: kbRename.cancelRename,
                  disabled: kbRename.isSaving,
                }
              : undefined,
            dropdownItems: [
              ...(userPermissions.canEdit || userPermissions.isLoading
                ? [
                    {
                      label: 'Rename',
                      icon: Pencil,
                      disabled: !userPermissions.canEdit,
                      onClick: () => kbRename.startRename(id, knowledgeBaseName),
                    },
                    {
                      label: 'Tags',
                      icon: TagIcon,
                      disabled: !userPermissions.canEdit,
                      onClick: dialogs.tagsModal.open,
                    },
                    {
                      label: 'Delete',
                      icon: Trash,
                      disabled: !userPermissions.canEdit,
                      onClick: dialogs.deleteBaseDialog.open,
                    },
                  ]
                : []),
            ],
          },
        ],
      }),
    [
      folderChain,
      baseCommands.navigateToFolder,
      knowledgeBaseCrumbLabel,
      knowledgeBaseName,
      id,
      kbRename.editingId,
      kbRename.editValue,
      kbRename.isSaving,
      kbRename.setEditValue,
      kbRename.submitRename,
      kbRename.cancelRename,
      kbRename.startRename,
      userPermissions.canEdit,
      userPermissions.isLoading,
      dialogs.tagsModal.open,
      dialogs.deleteBaseDialog.open,
    ]
  )

  const headerActions: ResourceAction[] = useMemo(
    () => [
      {
        text: 'New documents',
        icon: Plus,
        onSelect: dialogs.addDocumentsModal.open,
        disabled: userPermissions.canEdit !== true,
        variant: 'primary',
      },
    ],
    [userPermissions.canEdit, dialogs.addDocumentsModal.open]
  )

  const sortConfig: SortConfig = useMemo(
    () => ({
      options: [
        { id: 'filename', label: 'Name' },
        { id: 'fileSize', label: 'Size' },
        { id: 'tokenCount', label: 'Tokens' },
        { id: 'chunkCount', label: 'Chunks' },
        { id: 'uploadedAt', label: 'Uploaded' },
        { id: 'enabled', label: 'Status' },
      ],
      active: list.activeSort,
      /** Sorting (or clearing the sort) resets pagination to the first page. */
      onSort: (column, direction) => {
        list.onSortColumn(column, direction)
        list.setCurrentPage(1)
      },
      onClear: () => {
        list.onClearSort()
        list.setCurrentPage(1)
      },
    }),
    [list.activeSort, list.onSortColumn, list.onClearSort, list.setCurrentPage]
  )

  const filterTags: FilterTag[] = useMemo(
    () => [
      ...(list.enabledFilter !== 'all'
        ? [
            {
              label: `Status: ${list.enabledFilter === 'enabled' ? 'Enabled' : 'Disabled'}`,
              onRemove: () => list.setEnabledFilter('all'),
            },
          ]
        : []),
      ...tagFilters.filterTags,
    ],
    [list.enabledFilter, list.setEnabledFilter, tagFilters.filterTags]
  )

  const selectableConfig: SelectableConfig = {
    selectedIds: list.selectedDocuments,
    onSelectRow: list.handleSelectDocument,
    onSelectAll: list.handleSelectAll,
    isAllSelected: list.isAllSelected,
    disabled: !userPermissions.canEdit,
  }

  const documentRows = useMemo(
    () =>
      buildDocumentRows({
        documents: list.documents,
        tagDefinitions,
        highlightQuery: list.highlightQuery,
      }),
    [list.documents, tagDefinitions, list.highlightQuery]
  )

  /**
   * Handles clicking on a document row to navigate to detail view
   */
  const handleDocumentClick = useCallback(
    (docId: string) => {
      const document = list.documents.find((doc) => doc.id === docId)
      if (document?.processingStatus !== 'completed') return
      const urlParams = new URLSearchParams({
        kbName: knowledgeBaseName,
        docName: document?.filename || 'Document',
      })
      router.push(`/workspace/${workspaceId}/knowledge/${id}/${docId}?${urlParams.toString()}`)
    },
    [list.documents, knowledgeBaseName, router, workspaceId, id]
  )

  const requestBulkDelete = useCallback(() => {
    dialogs.bulkDeleteDialog.request(list.selectedDocuments.size > 0)
  }, [dialogs.bulkDeleteDialog.request, list.selectedDocuments.size])

  if (error && !knowledgeBase) {
    return (
      <div className='flex h-full flex-col items-center justify-center gap-3'>
        <DatabaseX className='size-[32px] text-[var(--text-muted)]' />
        <div className='flex flex-col items-center gap-1'>
          <h2 className='text-[20px] text-[var(--text-secondary)]'>Knowledge base not found</h2>
          <p className='text-[var(--text-muted)] text-small'>
            This knowledge base may have been deleted or moved
          </p>
        </div>
      </div>
    )
  }

  return (
    <>
      <Resource onContextMenu={handleEmptyContextMenu}>
        <Resource.Header
          icon={FOLDERED_RESOURCE_HEADERS.knowledge_base.rootIcon}
          title={FOLDERED_RESOURCE_HEADERS.knowledge_base.rootLabel}
          breadcrumbs={breadcrumbs}
          actions={headerActions}
        />
        <Resource.Options
          search={{
            value: list.searchQuery,
            onChange: list.handleSearchChange,
            placeholder: 'Search documents...',
          }}
          sort={sortConfig}
          filter={{
            content: (
              <DocumentFilterPanel
                enabledFilter={list.enabledFilter}
                onEnabledFilterChange={list.setEnabledFilter}
                tagDefinitions={tagDefinitions}
                tagFilterEntries={tagFilters.entries}
                onTagFilterEntriesChange={tagFilters.updateEntries}
              />
            ),
          }}
          filterTags={filterTags}
        />
        <Resource.Table
          columns={DOCUMENT_COLUMNS}
          rows={documentRows}
          selectable={selectableConfig}
          onRowClick={handleDocumentClick}
          onRowContextMenu={handleDocumentContextMenu}
          pagination={{
            currentPage: list.currentPage,
            totalPages: list.totalPages,
            onPageChange: (page) => list.setCurrentPage(page),
          }}
          overlay={
            <ActionBar
              className={list.totalPages > 1 ? 'bottom-[72px]' : undefined}
              selectedCount={list.selectedDocuments.size}
              onEnable={list.selectedCounts.disabled > 0 ? documentCommands.bulkEnable : undefined}
              onDisable={list.selectedCounts.enabled > 0 ? documentCommands.bulkDisable : undefined}
              onDelete={requestBulkDelete}
              enabledCount={list.selectedCounts.enabled}
              disabledCount={list.selectedCounts.disabled}
              isLoading={documentCommands.isBulkOperating}
              totalCount={list.pagination.total}
              isAllPageSelected={list.isAllSelected}
              isAllSelected={list.isSelectAllMode}
              onSelectAll={() => list.setIsSelectAllMode(true)}
              onClearSelectAll={list.clearSelection}
            />
          }
        />
      </Resource>

      <BaseDetailDialogsView
        knowledgeBaseId={id}
        knowledgeBaseName={knowledgeBaseName}
        documentTotal={list.pagination.total}
        documents={list.documents}
        chunkingConfig={knowledgeBase?.chunkingConfig}
        dialogs={dialogs}
        commands={documentCommands}
        isDeletingBase={baseCommands.isDeleting}
        onDeleteBase={baseCommands.deleteKnowledgeBase}
        updateDocument={list.updateDocument}
        selectedCount={list.selectedDocuments.size}
      />

      <DocumentContextMenu
        isOpen={isContextMenuOpen}
        position={contextMenuPosition}
        onClose={handleContextMenuClose}
        hasDocument={contextMenuDocument !== null}
        isDocumentEnabled={contextMenuDocument?.enabled ?? true}
        selectedCount={list.selectedDocuments.size}
        enabledCount={list.selectedCounts.enabled}
        disabledCount={list.selectedCounts.disabled}
        onOpenInNewTab={
          contextMenuDocument && list.selectedDocuments.size === 1
            ? () => {
                const urlParams = new URLSearchParams({
                  kbName: knowledgeBaseName,
                  docName: contextMenuDocument.filename || 'Document',
                })
                window.open(
                  `/workspace/${workspaceId}/knowledge/${id}/${contextMenuDocument.id}?${urlParams.toString()}`,
                  '_blank'
                )
              }
            : undefined
        }
        onRename={
          contextMenuDocument
            ? () => dialogs.renameDocumentModal.request(contextMenuDocument)
            : undefined
        }
        onToggleEnabled={
          contextMenuDocument
            ? list.selectedDocuments.size > 1
              ? () => {
                  if (list.selectedCounts.disabled > 0) {
                    documentCommands.bulkEnable()
                  } else {
                    documentCommands.bulkDisable()
                  }
                }
              : () => documentCommands.toggleEnabled(contextMenuDocument.id)
            : undefined
        }
        onViewTags={
          contextMenuDocument && list.selectedDocuments.size === 1 && userPermissions.canEdit
            ? () => dialogs.documentTagsModal.request(contextMenuDocument)
            : undefined
        }
        onDelete={
          contextMenuDocument
            ? list.selectedDocuments.size > 1
              ? requestBulkDelete
              : () => dialogs.deleteDocumentDialog.request(contextMenuDocument.id)
            : undefined
        }
        onAddDocument={dialogs.addDocumentsModal.open}
        disableRename={!userPermissions.canEdit}
        disableToggleEnabled={
          !userPermissions.canEdit ||
          contextMenuDocument?.processingStatus === 'processing' ||
          contextMenuDocument?.processingStatus === 'pending'
        }
        disableDelete={
          !userPermissions.canEdit || contextMenuDocument?.processingStatus === 'processing'
        }
        disableAddDocument={!userPermissions.canEdit}
      />
    </>
  )
}
