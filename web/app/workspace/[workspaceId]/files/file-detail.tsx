'use client'

import { useMemo } from 'react'
import { ChipConfirmModal, Columns2, Eye, Pencil, Trash } from '@/components/ui-kit'
import { Download, Send } from '@/components/ui-kit/icons'
import type { WorkspaceFileRecord } from '@/lib/api/contracts/workspace-files'
import { workspaceCopy } from '@/lib/product-copy'
import type { BreadcrumbItem, ResourceAction } from '@/app/workspace/[workspaceId]/components'
import { Resource } from '@/app/workspace/[workspaceId]/components'
import {
  breadcrumbFolderChain,
  FOLDERED_RESOURCE_HEADERS,
  folderBreadcrumbItems,
  folderedResourceListHref,
} from '@/app/workspace/[workspaceId]/components/folders'
import { DeleteConfirmModal } from '@/app/workspace/[workspaceId]/files/components/delete-confirm-modal'
import {
  FileViewer,
  isCsvStreamOnly,
  isMarkdownFile,
  isPreviewable,
  isTextEditable,
} from '@/app/workspace/[workspaceId]/files/components/file-viewer'
import { FileDocAvatars } from '@/app/workspace/[workspaceId]/files/components/file-viewer/rich-markdown-editor/collaboration/file-doc-avatars'
import { FileDocRoomProvider } from '@/app/workspace/[workspaceId]/files/components/file-viewer/rich-markdown-editor/collaboration/file-doc-room-context'
import { useFileDetail } from '@/app/workspace/[workspaceId]/files/hooks/use-file-detail'
import { useRegisterGlobalCommands } from '@/app/workspace/[workspaceId]/providers/global-commands-provider'
import type { WorkspaceFileFolderApi } from '@/hooks/queries/workspace-file-folders'

const FILES_HEADER = FOLDERED_RESOURCE_HEADERS.file

export interface FileDetailProps {
  workspaceId: string
  file: WorkspaceFileRecord
  /** One-shot `?new=1` flag: a freshly created file opens in the editor, autofocused. */
  isNewFile: boolean
  canEdit: boolean
  /** The folder the list showed when this file was opened; delete returns the user there. */
  currentFolderId: string | null
  /** Latest workspace files, shared with the shell, for heading-derived title suggestions. */
  filesRef: { current: WorkspaceFileRecord[] }
  folderById: Map<string, WorkspaceFileFolderApi>
  onShareFile: (fileId: string) => void
}

/**
 * The file detail view: composes the viewer lifecycle controller with the collaborative
 * editor/preview surface, the header breadcrumb + actions, and the detail-scoped modals and
 * global commands. Mounts only when the routed file has resolved, so none of the list
 * controllers run while a file is open.
 */
export function FileDetail({
  workspaceId,
  file,
  isNewFile,
  canEdit,
  currentFolderId,
  filesRef,
  folderById,
  onShareFile,
}: FileDetailProps) {
  const detail = useFileDetail({
    workspaceId,
    file,
    isNewFile,
    currentFolderId,
    filesRef,
    onShareFile,
  })
  const headerRename = detail.headerRename

  const fileDetailBreadcrumbs = useMemo((): BreadcrumbItem[] => {
    return folderBreadcrumbItems({
      rootLabel: FILES_HEADER.rootLabel,
      rootIcon: FILES_HEADER.rootIcon,
      breadcrumbs: breadcrumbFolderChain(file.folderId, folderById),
      onNavigate: (folderId) =>
        detail.handleNavigate(folderedResourceListHref('file', workspaceId, folderId)),
      trailing: [
        {
          label: file.name,
          editing: headerRename.editingId
            ? {
                isEditing: true,
                value: headerRename.editValue,
                onChange: headerRename.setEditValue,
                onSubmit: headerRename.submitRename,
                onCancel: headerRename.cancelRename,
              }
            : undefined,
          dropdownItems: [
            {
              label: workspaceCopy.common.actions.download,
              icon: Download,
              onClick: detail.handleDownloadSelected,
            },
            ...(canEdit
              ? [
                  {
                    label: workspaceCopy.resources.actions.rename,
                    icon: Pencil,
                    onClick: detail.handleStartHeaderRename,
                  },
                  {
                    label: workspaceCopy.resources.actions.share,
                    icon: Send,
                    onClick: detail.handleShareSelected,
                  },
                  {
                    label: workspaceCopy.common.actions.delete,
                    icon: Trash,
                    onClick: detail.handleDeleteSelected,
                  },
                ]
              : []),
          ],
        },
      ],
    })
  }, [
    file,
    folderById,
    detail.handleNavigate,
    workspaceId,
    canEdit,
    headerRename.editingId,
    headerRename.editValue,
    detail.handleStartHeaderRename,
    detail.handleDownloadSelected,
    detail.handleShareSelected,
    detail.handleDeleteSelected,
  ])

  const fileActions = useMemo<ResourceAction[]>(() => {
    // A large CSV renders as a read-only streamed preview (no editor), so it gets neither the
    // edit/split/preview toggle nor autosave — just like a non-editable file.
    const streamOnly = isCsvStreamOnly(file)
    const canEditText = isTextEditable(file) && !streamOnly
    const canPreview = isPreviewable(file) && !streamOnly
    // Markdown renders in the single-surface inline editor, which has no raw/split/preview modes.
    const isInlineMarkdown = isMarkdownFile(file)
    const hasSplitView = canEditText && canPreview && !isInlineMarkdown
    const showPreviewToggle = canPreview && !isInlineMarkdown

    const nextModeLabel =
      detail.previewMode === 'editor'
        ? 'Split'
        : detail.previewMode === 'split'
          ? 'Preview'
          : 'Edit'
    const nextModeIcon =
      detail.previewMode === 'editor' ? Columns2 : detail.previewMode === 'split' ? Eye : Pencil

    return [
      ...(hasSplitView
        ? [
            {
              text: nextModeLabel,
              icon: nextModeIcon,
              onSelect: detail.handleCyclePreviewMode,
            },
          ]
        : showPreviewToggle
          ? [
              {
                text:
                  detail.previewMode === 'preview'
                    ? workspaceCopy.resources.actions.edit
                    : workspaceCopy.resources.actions.preview,
                icon: detail.previewMode === 'preview' ? Pencil : Eye,
                onSelect: detail.handleTogglePreview,
              },
            ]
          : []),
      {
        text: workspaceCopy.common.actions.download,
        icon: Download,
        onSelect: detail.handleDownloadSelected,
      },
      ...(canEdit
        ? [
            {
              text: workspaceCopy.resources.actions.share,
              icon: Send,
              onSelect: detail.handleShareSelected,
            },
            {
              id: 'delete',
              text: workspaceCopy.common.actions.delete,
              icon: Trash,
              onSelect: detail.handleDeleteSelected,
            },
          ]
        : []),
    ]
  }, [
    file,
    canEdit,
    detail.previewMode,
    detail.handleCyclePreviewMode,
    detail.handleTogglePreview,
    detail.handleDownloadSelected,
    detail.handleShareSelected,
    detail.handleDeleteSelected,
  ])

  useRegisterGlobalCommands(() => [
    { id: 'file-download', handler: () => detail.handleDownloadSelected() },
    { id: 'file-rename', handler: () => detail.handleStartHeaderRename() },
    { id: 'file-share', handler: () => detail.handleShareSelected() },
    { id: 'file-delete', handler: () => detail.handleDeleteSelected() },
  ])

  return (
    <>
      {/* The room provider scopes "who's in this file" presence to the open document: the
          editor (inside FileViewer) publishes the server-authenticated roster and the
          header's FileDocAvatars reads it — both must be descendants. */}
      <FileDocRoomProvider>
        <Resource>
          <Resource.Header
            icon={FILES_HEADER.rootIcon}
            breadcrumbs={fileDetailBreadcrumbs}
            actions={fileActions}
            aside={<FileDocAvatars />}
          />
          <FileViewer
            key={file.id}
            file={file}
            workspaceId={workspaceId}
            canEdit={canEdit}
            previewMode={detail.previewMode}
            autoFocus={isNewFile}
            onDirtyChange={detail.setIsDirty}
            onSaveStatusChange={detail.handleSaveStatusChange}
            saveRef={detail.saveRef}
            discardRef={detail.discardRef}
            collaborative
            onDeriveTitleFromHeading={detail.handleDeriveTitleFromHeading}
          />

          <ChipConfirmModal
            open={detail.showUnsavedChangesAlert}
            onOpenChange={detail.setShowUnsavedChangesAlert}
            srTitle='有未保存的更改'
            title='有未保存的更改'
            text='当前更改尚未保存，确定要放弃吗？'
            dismissLabel='Keep editing'
            confirm={{
              label: workspaceCopy.resources.actions.discardChanges,
              onClick: detail.handleDiscardChanges,
            }}
          />
        </Resource>
      </FileDocRoomProvider>

      <DeleteConfirmModal
        open={detail.deleteFlow.showDeleteConfirm}
        onOpenChange={detail.deleteFlow.setShowDeleteConfirm}
        fileName={detail.deleteFlow.deleteTarget?.name}
        fileCount={detail.deleteFlow.deleteTarget?.fileIds.length ?? 0}
        folderCount={detail.deleteFlow.deleteTarget?.folderIds.length ?? 0}
        onDelete={detail.handleConfirmDelete}
        isPending={detail.deleteFlow.isDeleting}
      />
    </>
  )
}
