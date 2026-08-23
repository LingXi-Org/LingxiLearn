'use client'

import { useState } from 'react'
import { ChipConfirmModal } from '@/components/ui-kit'
import type { KnowledgeBaseData } from '@/lib/knowledge/types'
import { BaseTagsModal } from '@/app/workspace/[workspaceId]/knowledge/[id]/components'
import {
  CreateBaseModal,
  DeleteKnowledgeBaseModal,
  EditKnowledgeBaseModal,
} from '@/app/workspace/[workspaceId]/knowledge/components'
import type { KnowledgeDialogs } from '../hooks/use-knowledge-dialogs'
import type { KnowledgeFolder } from '../list/types'

export interface KnowledgeDialogsViewProps {
  /** Dialog open/close state, from `useKnowledgeDialogs`. */
  dialogs: KnowledgeDialogs
  /** The base the row menus acted on; `null` renders no base dialog. */
  activeBase: KnowledgeBaseData | null
  /** Folder the create modal files a new base into. */
  currentFolderId: string | null
  onSaveBase: (id: string, name: string, description: string) => Promise<void>
  /** Deletes the base and clears the selection on success. */
  onDeleteBase: (id: string) => Promise<void>
  /** Extra cleanup when the delete dialog closes without deleting (cancel/escape). */
  onCloseDelete: () => void
  /** Deletes the folder; rejects on failure so the confirmation stays open. */
  onConfirmFolderDelete: (folder: KnowledgeFolder) => Promise<void>
  /** Whether the folder delete mutation is in flight. */
  folderDeletePending: boolean
  /** Clears the folder selection after a successful folder delete. */
  onFolderDeleted: () => void
}

/**
 * Renders the knowledge list's dialogs. All open/close state arrives via `dialogs`; the
 * only state owned here is the delete-base in-flight flag, which exists solely to drive
 * the modal's pending indicator across the await.
 */
export function KnowledgeDialogsView({
  dialogs,
  activeBase,
  currentFolderId,
  onSaveBase,
  onDeleteBase,
  onCloseDelete,
  onConfirmFolderDelete,
  folderDeletePending,
  onFolderDeleted,
}: KnowledgeDialogsViewProps) {
  const [isDeleting, setIsDeleting] = useState(false)

  const handleConfirmDeleteBase = async () => {
    if (!activeBase) return
    setIsDeleting(true)
    try {
      await onDeleteBase(activeBase.id)
      dialogs.setIsDeleteOpen(false)
    } finally {
      setIsDeleting(false)
    }
  }

  const handleCloseDeleteModal = () => {
    dialogs.setIsDeleteOpen(false)
    onCloseDelete()
  }

  const handleConfirmFolderDelete = async () => {
    const folder = dialogs.folderPendingDelete
    if (!folder) return
    try {
      await onConfirmFolderDelete(folder)
    } catch {
      // The command already surfaced the error; keep the confirmation open.
      return
    }
    dialogs.clearFolderDelete()
    onFolderDeleted()
  }

  return (
    <>
      <ChipConfirmModal
        open={dialogs.folderPendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) dialogs.clearFolderDelete()
        }}
        srTitle='Delete folder'
        title='Delete folder'
        text={[
          'Are you sure you want to delete ',
          { text: dialogs.folderPendingDelete?.name ?? 'this folder', bold: true },
          '? This also deletes the knowledge bases and folders inside it. You can restore them from Recently Deleted in Settings.',
        ]}
        confirm={{
          label: 'Delete',
          onClick: handleConfirmFolderDelete,
          pending: folderDeletePending,
          pendingLabel: 'Deleting...',
        }}
      />

      {activeBase && (
        <EditKnowledgeBaseModal
          open={dialogs.isEditOpen}
          onOpenChange={dialogs.setIsEditOpen}
          knowledgeBaseId={activeBase.id}
          initialName={activeBase.name}
          initialDescription={activeBase.description || ''}
          chunkingConfig={activeBase.chunkingConfig}
          onSave={onSaveBase}
        />
      )}

      {activeBase && (
        <DeleteKnowledgeBaseModal
          isOpen={dialogs.isDeleteOpen}
          onClose={handleCloseDeleteModal}
          onConfirm={handleConfirmDeleteBase}
          isDeleting={isDeleting}
          knowledgeBaseName={activeBase.name}
        />
      )}

      {activeBase && (
        <BaseTagsModal
          open={dialogs.isTagsOpen}
          onOpenChange={dialogs.setIsTagsOpen}
          knowledgeBaseId={activeBase.id}
        />
      )}

      <CreateBaseModal
        open={dialogs.isCreateOpen}
        onOpenChange={dialogs.setIsCreateOpen}
        folderId={currentFolderId}
      />
    </>
  )
}
