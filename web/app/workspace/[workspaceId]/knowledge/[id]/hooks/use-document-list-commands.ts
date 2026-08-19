'use client'

import { useCallback } from 'react'
import { createLogger } from '@sim/logger'
import { getErrorMessage } from '@sim/utils/errors'
import type { DocumentData } from '@/lib/knowledge/types'
import type { DocumentEnabledFilter } from '@/app/workspace/[workspaceId]/knowledge/[id]/hooks/use-document-list-controller'
import { resolveBulkTargets } from '@/app/workspace/[workspaceId]/knowledge/detail/domain/documents'
import {
  useBulkDocumentOperation,
  useDeleteDocument,
  useUpdateDocument,
} from '@/hooks/queries/kb/knowledge'

const logger = createLogger('KnowledgeDocumentCommands')

interface UseDocumentCommandsParams {
  knowledgeBaseId: string
  /** Current page of documents, for bulk target resolution. */
  documents: DocumentData[]
  /** Optimistic cache update from the list controller. */
  updateDocument: (documentId: string, updates: Partial<DocumentData>) => void
  selectedDocuments: ReadonlySet<string>
  isSelectAllMode: boolean
  /** Current status filter — the select-all operations stay inside it. */
  enabledFilter: DocumentEnabledFilter
  clearSelection: () => void
  removeFromSelection: (docId: string) => void
}

/**
 * Central command layer for the documents of a knowledge base. Owns every
 * document mutation (toggle/retry/rename/delete and the bulk operations) with
 * its optimistic update, error handling, and selection cleanup, so neither the
 * row presentation nor the dialogs talk to the mutation hooks directly.
 */
export function useDocumentCommands({
  knowledgeBaseId,
  documents,
  updateDocument,
  selectedDocuments,
  isSelectAllMode,
  enabledFilter,
  clearSelection,
  removeFromSelection,
}: UseDocumentCommandsParams) {
  const { mutate: updateDocumentMutation, mutateAsync: updateDocumentAsync } = useUpdateDocument()
  const { mutate: deleteDocumentMutation } = useDeleteDocument()
  const { mutate: bulkDocumentMutation, isPending: isBulkOperating } = useBulkDocumentOperation()

  const toggleEnabled = useCallback(
    (docId: string) => {
      const document = documents.find((doc) => doc.id === docId)
      if (!document) return

      const newEnabled = !document.enabled
      updateDocument(docId, { enabled: newEnabled })
      updateDocumentMutation(
        { knowledgeBaseId, documentId: docId, updates: { enabled: newEnabled } },
        { onError: () => updateDocument(docId, { enabled: !newEnabled }) }
      )
    },
    [documents, knowledgeBaseId, updateDocument, updateDocumentMutation]
  )

  const retryDocument = useCallback(
    (docId: string) => {
      updateDocument(docId, {
        processingStatus: 'pending',
        processingError: null,
        processingStartedAt: null,
        processingCompletedAt: null,
      })
      updateDocumentMutation(
        { knowledgeBaseId, documentId: docId, updates: { retryProcessing: true } },
        {
          onSuccess: () => {
            logger.info(`Document retry initiated successfully for: ${docId}`)
          },
          onError: (err) => {
            logger.error('Error retrying document:', err)
            updateDocument(docId, {
              processingStatus: 'failed',
              processingError: getErrorMessage(err, 'Failed to retry document processing'),
            })
          },
        }
      )
    },
    [knowledgeBaseId, updateDocument, updateDocumentMutation]
  )

  /**
   * Rename with optimistic cache write; rethrows so the rename modal keeps its
   * error path, and rolls the cache back on failure.
   */
  const saveRename = useCallback(
    async (documentId: string, newName: string) => {
      const currentDoc = documents.find((doc) => doc.id === documentId)
      const previousName = currentDoc?.filename

      updateDocument(documentId, { filename: newName })
      try {
        await updateDocumentAsync({
          knowledgeBaseId,
          documentId,
          updates: { filename: newName },
        })
        logger.info(`Document renamed: ${documentId}`)
      } catch (err) {
        if (previousName !== undefined) {
          updateDocument(documentId, { filename: previousName })
        }
        logger.error('Error renaming document:', err)
        throw err
      }
    },
    [documents, knowledgeBaseId, updateDocument, updateDocumentAsync]
  )

  /**
   * Delete a single document; the caller owns the confirmation dialog and gets
   * its `onSettled` mirrored so the dialog closes once the request completes.
   */
  const deleteDocument = useCallback(
    (documentId: string, options?: { onSettled?: () => void }) => {
      deleteDocumentMutation(
        { knowledgeBaseId, documentId },
        {
          onSuccess: () => removeFromSelection(documentId),
          onSettled: options?.onSettled,
        }
      )
    },
    [knowledgeBaseId, deleteDocumentMutation, removeFromSelection]
  )

  const bulkEnable = useCallback(() => {
    if (isSelectAllMode) {
      bulkDocumentMutation(
        { knowledgeBaseId, operation: 'enable', selectAll: true, enabledFilter },
        {
          onSuccess: (result) => {
            logger.info(`Successfully enabled ${result.successCount} documents`)
            clearSelection()
          },
        }
      )
      return
    }

    const targets = resolveBulkTargets(documents, selectedDocuments, 'enable')
    if (targets.length === 0) return

    bulkDocumentMutation(
      { knowledgeBaseId, operation: 'enable', documentIds: targets.map((doc) => doc.id) },
      {
        onSuccess: (result) => {
          result.updatedDocuments?.forEach((updatedDoc) => {
            updateDocument(updatedDoc.id, { enabled: updatedDoc.enabled })
          })
          logger.info(`Successfully enabled ${result.successCount} documents`)
          clearSelection()
        },
      }
    )
  }, [
    isSelectAllMode,
    bulkDocumentMutation,
    knowledgeBaseId,
    enabledFilter,
    documents,
    selectedDocuments,
    updateDocument,
    clearSelection,
  ])

  const bulkDisable = useCallback(() => {
    if (isSelectAllMode) {
      bulkDocumentMutation(
        { knowledgeBaseId, operation: 'disable', selectAll: true, enabledFilter },
        {
          onSuccess: (result) => {
            logger.info(`Successfully disabled ${result.successCount} documents`)
            clearSelection()
          },
        }
      )
      return
    }

    const targets = resolveBulkTargets(documents, selectedDocuments, 'disable')
    if (targets.length === 0) return

    bulkDocumentMutation(
      { knowledgeBaseId, operation: 'disable', documentIds: targets.map((doc) => doc.id) },
      {
        onSuccess: (result) => {
          result.updatedDocuments?.forEach((updatedDoc) => {
            updateDocument(updatedDoc.id, { enabled: updatedDoc.enabled })
          })
          logger.info(`Successfully disabled ${result.successCount} documents`)
          clearSelection()
        },
      }
    )
  }, [
    isSelectAllMode,
    bulkDocumentMutation,
    knowledgeBaseId,
    enabledFilter,
    documents,
    selectedDocuments,
    updateDocument,
    clearSelection,
  ])

  /**
   * Execute the confirmed bulk delete; the caller owns the confirmation dialog
   * and gets its `onSettled` mirrored so the dialog closes once complete.
   */
  const bulkDelete = useCallback(
    (options?: { onSettled?: () => void }) => {
      if (isSelectAllMode) {
        bulkDocumentMutation(
          { knowledgeBaseId, operation: 'delete', selectAll: true, enabledFilter },
          {
            onSuccess: (result) => {
              logger.info(`Successfully deleted ${result.successCount} documents`)
              clearSelection()
            },
            onSettled: options?.onSettled,
          }
        )
        return
      }

      const targets = resolveBulkTargets(documents, selectedDocuments, 'delete')
      if (targets.length === 0) return

      bulkDocumentMutation(
        { knowledgeBaseId, operation: 'delete', documentIds: targets.map((doc) => doc.id) },
        {
          onSuccess: (result) => {
            logger.info(`Successfully deleted ${result.successCount} documents`)
            clearSelection()
          },
          onSettled: options?.onSettled,
        }
      )
    },
    [
      isSelectAllMode,
      bulkDocumentMutation,
      knowledgeBaseId,
      enabledFilter,
      documents,
      selectedDocuments,
      clearSelection,
    ]
  )

  return {
    toggleEnabled,
    retryDocument,
    saveRename,
    deleteDocument,
    bulkEnable,
    bulkDisable,
    bulkDelete,
    isBulkOperating,
  }
}

export type DocumentListCommands = ReturnType<typeof useDocumentCommands>
