'use client'

import { useCallback, useState } from 'react'
import type { DocumentData } from '@/lib/knowledge/types'

/**
 * Owns the dialog lifecycle of the knowledge-base detail page. Target-carrying
 * dialogs derive their open state from the target (`null` = closed) so the two
 * can never drift apart; the confirmation flows that must stay open until the
 * mutation settles close via the command's `onSettled`.
 */
export function useBaseDetailDialogs() {
  const [tagsModalOpen, setTagsModalOpen] = useState(false)
  const [deleteBaseDialogOpen, setDeleteBaseDialogOpen] = useState(false)
  const [addDocumentsOpen, setAddDocumentsOpen] = useState(false)
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false)
  const [documentToDeleteId, setDocumentToDeleteId] = useState<string | null>(null)
  const [documentToRename, setDocumentToRename] = useState<DocumentData | null>(null)
  const [documentForTagsId, setDocumentForTagsId] = useState<string | null>(null)

  const requestBulkDelete = useCallback((hasSelection: boolean) => {
    if (!hasSelection) return
    setBulkDeleteOpen(true)
  }, [])

  return {
    tagsModal: {
      isOpen: tagsModalOpen,
      open: useCallback(() => setTagsModalOpen(true), []),
      setOpen: setTagsModalOpen,
    },
    deleteBaseDialog: {
      isOpen: deleteBaseDialogOpen,
      open: useCallback(() => setDeleteBaseDialogOpen(true), []),
      setOpen: setDeleteBaseDialogOpen,
    },
    addDocumentsModal: {
      isOpen: addDocumentsOpen,
      open: useCallback(() => setAddDocumentsOpen(true), []),
      setOpen: setAddDocumentsOpen,
    },
    bulkDeleteDialog: {
      isOpen: bulkDeleteOpen,
      request: requestBulkDelete,
      setOpen: setBulkDeleteOpen,
    },
    deleteDocumentDialog: {
      targetId: documentToDeleteId,
      request: useCallback((docId: string) => setDocumentToDeleteId(docId), []),
      close: useCallback(() => setDocumentToDeleteId(null), []),
    },
    renameDocumentModal: {
      target: documentToRename,
      request: useCallback((doc: DocumentData) => setDocumentToRename(doc), []),
      close: useCallback(() => setDocumentToRename(null), []),
    },
    documentTagsModal: {
      documentId: documentForTagsId,
      request: useCallback((doc: DocumentData) => setDocumentForTagsId(doc.id), []),
      close: useCallback(() => setDocumentForTagsId(null), []),
    },
  }
}

export type BaseDetailDialogs = ReturnType<typeof useBaseDetailDialogs>
