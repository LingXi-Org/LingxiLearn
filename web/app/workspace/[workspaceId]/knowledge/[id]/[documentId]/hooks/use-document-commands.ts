'use client'

import { useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useDeleteDocument, useUpdateDocument } from '@/hooks/queries/kb/knowledge'
import { useInlineRename } from '@/hooks/use-inline-rename'

interface UseDocumentCommandsParams {
  knowledgeBaseId: string
  documentId: string
  workspaceId: string
  /** Current display name (drives the rename session). */
  documentName: string
}

/**
 * Central command layer for the document itself (not its chunks): breadcrumb
 * inline rename and delete-and-navigate-back. Content/chunk reads live in the
 * list controller; chunk mutations live in `useChunkCommands`.
 */
export function useDocumentCommands({
  knowledgeBaseId,
  documentId,
  workspaceId,
  documentName,
}: UseDocumentCommandsParams) {
  const router = useRouter()
  const { mutate: deleteDocumentMutation, isPending: isDeletingDocument } = useDeleteDocument()
  const { mutateAsync: updateDocumentMutation } = useUpdateDocument()

  const docRename = useInlineRename({
    onSave: (docId, filename) =>
      updateDocumentMutation({ knowledgeBaseId, documentId: docId, updates: { filename } }),
  })

  const startRename = useCallback(() => {
    docRename.startRename(documentId, documentName)
  }, [docRename.startRename, documentId, documentName])

  const deleteDocument = useCallback(() => {
    deleteDocumentMutation(
      { knowledgeBaseId, documentId },
      {
        onSuccess: () => {
          router.push(`/workspace/${workspaceId}/knowledge/${knowledgeBaseId}`)
        },
      }
    )
  }, [deleteDocumentMutation, knowledgeBaseId, documentId, router, workspaceId])

  return {
    docRename,
    startRename,
    deleteDocument,
    isDeletingDocument,
  }
}

export type DocumentDetailCommands = ReturnType<typeof useDocumentCommands>
