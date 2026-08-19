'use client'

import { useCallback, useState } from 'react'
import type { ChunkData } from '@/lib/knowledge/types'

/**
 * Owns the document detail page's dialog lifecycle (tags modal, delete-chunk,
 * delete-document). The unsaved-changes guard belongs to the chunk editor
 * controller, which owns the dirty state it guards. Target-carrying dialogs
 * derive their open state from the target (`null` = closed).
 */
export function useDocumentDetailDialogs() {
  const [tagsModalOpen, setTagsModalOpen] = useState(false)
  const [deleteDocumentDialogOpen, setDeleteDocumentDialogOpen] = useState(false)
  const [chunkToDelete, setChunkToDelete] = useState<ChunkData | null>(null)

  return {
    tagsModal: {
      isOpen: tagsModalOpen,
      open: useCallback(() => setTagsModalOpen(true), []),
      setOpen: setTagsModalOpen,
    },
    deleteDocumentDialog: {
      isOpen: deleteDocumentDialogOpen,
      open: useCallback(() => setDeleteDocumentDialogOpen(true), []),
      setOpen: setDeleteDocumentDialogOpen,
    },
    deleteChunkDialog: {
      target: chunkToDelete,
      request: useCallback((chunk: ChunkData) => setChunkToDelete(chunk), []),
      close: useCallback(() => setChunkToDelete(null), []),
    },
  }
}

export type DocumentDetailDialogs = ReturnType<typeof useDocumentDetailDialogs>
