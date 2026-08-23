'use client'

import { ChipConfirmModal, type ChipConfirmTextSegment } from '@/components/ui-kit'
import type { DocumentData, KnowledgeBaseData } from '@/lib/knowledge/types'
import { DocumentTagsModal } from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/components'
import {
  AddDocumentsModal,
  BaseTagsModal,
  RenameDocumentModal,
} from '@/app/workspace/[workspaceId]/knowledge/[id]/components'
import type { BaseDetailDialogs } from '@/app/workspace/[workspaceId]/knowledge/[id]/hooks/use-base-detail-dialogs'
import type { DocumentListCommands } from '@/app/workspace/[workspaceId]/knowledge/[id]/hooks/use-document-list-commands'

interface BaseDetailDialogsViewProps {
  knowledgeBaseId: string
  knowledgeBaseName: string
  /** Total documents in the base (for the delete-base warning copy). */
  documentTotal: number
  /** Current page of documents, for delete/tags target lookup. */
  documents: DocumentData[]
  chunkingConfig?: KnowledgeBaseData['chunkingConfig']
  dialogs: BaseDetailDialogs
  commands: DocumentListCommands
  isDeletingBase: boolean
  onDeleteBase: () => void
  updateDocument: (documentId: string, updates: Partial<DocumentData>) => void
  /** Current selection size, for the bulk-delete confirmation copy. */
  selectedCount: number
}

/**
 * The knowledge-base detail's dialog layer. Every modal renders here, wired to
 * the dialogs controller for open state and to the command layer for the
 * mutations — no dialog owns either.
 */
export function BaseDetailDialogsView({
  knowledgeBaseId,
  knowledgeBaseName,
  documentTotal,
  documents,
  chunkingConfig,
  dialogs,
  commands,
  isDeletingBase,
  onDeleteBase,
  updateDocument,
  selectedCount,
}: BaseDetailDialogsViewProps) {
  const documentToDelete = dialogs.deleteDocumentDialog.targetId
    ? documents.find((doc) => doc.id === dialogs.deleteDocumentDialog.targetId)
    : undefined

  const deleteDocumentText: ChipConfirmTextSegment[] = [
    'Are you sure you want to delete ',
    { text: documentToDelete?.filename ?? 'this document', bold: true },
    '? ',
    { text: 'This will permanently delete the document.', error: true },
    ' This action cannot be undone.',
  ]

  return (
    <>
      <BaseTagsModal
        open={dialogs.tagsModal.isOpen}
        onOpenChange={dialogs.tagsModal.setOpen}
        knowledgeBaseId={knowledgeBaseId}
      />

      <ChipConfirmModal
        open={dialogs.deleteBaseDialog.isOpen}
        onOpenChange={dialogs.deleteBaseDialog.setOpen}
        srTitle='Delete Knowledge Base'
        title='Delete Knowledge Base'
        text={[
          'Are you sure you want to delete ',
          { text: knowledgeBaseName, bold: true },
          '? ',
          {
            text: `The knowledge base and all ${documentTotal} document${documentTotal === 1 ? '' : 's'} within it will be removed.`,
            error: true,
          },
          ' You can restore it from Recently Deleted in Settings.',
        ]}
        confirm={{
          label: 'Delete Knowledge Base',
          onClick: onDeleteBase,
          pending: isDeletingBase,
          pendingLabel: 'Deleting...',
        }}
      />

      <ChipConfirmModal
        open={dialogs.deleteDocumentDialog.targetId !== null}
        onOpenChange={(open) => {
          if (!open) dialogs.deleteDocumentDialog.close()
        }}
        srTitle='Delete Document'
        title='Delete Document'
        text={deleteDocumentText}
        confirm={{
          label: 'Delete Document',
          onClick: () => {
            const targetId = dialogs.deleteDocumentDialog.targetId
            if (!targetId) return
            commands.deleteDocument(targetId, { onSettled: dialogs.deleteDocumentDialog.close })
          },
        }}
      />

      <ChipConfirmModal
        open={dialogs.bulkDeleteDialog.isOpen}
        onOpenChange={dialogs.bulkDeleteDialog.setOpen}
        srTitle='Delete Documents'
        title='Delete Documents'
        text={[
          `Are you sure you want to delete ${selectedCount} document${selectedCount === 1 ? '' : 's'}? `,
          {
            text: `This will permanently delete the selected document${selectedCount === 1 ? '' : 's'}.`,
            error: true,
          },
          ' This action cannot be undone.',
        ]}
        confirm={{
          label: `Delete ${selectedCount} Document${selectedCount === 1 ? '' : 's'}`,
          onClick: () =>
            commands.bulkDelete({ onSettled: () => dialogs.bulkDeleteDialog.setOpen(false) }),
          pending: commands.isBulkOperating,
          pendingLabel: 'Deleting...',
        }}
      />

      <AddDocumentsModal
        open={dialogs.addDocumentsModal.isOpen}
        onOpenChange={dialogs.addDocumentsModal.setOpen}
        knowledgeBaseId={knowledgeBaseId}
        chunkingConfig={chunkingConfig}
      />

      {dialogs.renameDocumentModal.target && (
        <RenameDocumentModal
          open
          onOpenChange={(open) => {
            if (!open) dialogs.renameDocumentModal.close()
          }}
          documentId={dialogs.renameDocumentModal.target.id}
          initialName={dialogs.renameDocumentModal.target.filename}
          onSave={commands.saveRename}
        />
      )}

      {dialogs.documentTagsModal.documentId && (
        <DocumentTagsModal
          open
          onOpenChange={(open) => {
            if (!open) dialogs.documentTagsModal.close()
          }}
          knowledgeBaseId={knowledgeBaseId}
          documentId={dialogs.documentTagsModal.documentId}
          documentData={
            documents.find((doc) => doc.id === dialogs.documentTagsModal.documentId) ?? null
          }
          onDocumentUpdate={(updates) => {
            const targetId = dialogs.documentTagsModal.documentId
            if (targetId) updateDocument(targetId, updates)
          }}
        />
      )}
    </>
  )
}
