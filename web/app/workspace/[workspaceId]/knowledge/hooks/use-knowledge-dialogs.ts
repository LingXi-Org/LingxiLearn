'use client'

import { useCallback, useState } from 'react'
import type { KnowledgeFolder } from '../list/types'

/**
 * Open/close lifecycle of every knowledge list dialog, isolated from the list controller:
 * the Create/Edit/Delete/Tags modals for a knowledge base, and the folder delete
 * confirmation. The entity a dialog acts on comes from the selection (`activeBase`) or is
 * carried here (`folderPendingDelete`), never duplicated.
 */
export function useKnowledgeDialogs() {
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [isTagsOpen, setIsTagsOpen] = useState(false)
  const [folderPendingDelete, setFolderPendingDelete] = useState<KnowledgeFolder | null>(null)

  const openCreate = useCallback(() => setIsCreateOpen(true), [])
  const openEdit = useCallback(() => setIsEditOpen(true), [])
  const openDelete = useCallback(() => setIsDeleteOpen(true), [])
  const openTags = useCallback(() => setIsTagsOpen(true), [])

  const requestFolderDelete = useCallback(
    (folder: KnowledgeFolder) => setFolderPendingDelete(folder),
    []
  )
  const clearFolderDelete = useCallback(() => setFolderPendingDelete(null), [])

  return {
    isCreateOpen,
    setIsCreateOpen,
    openCreate,
    isEditOpen,
    setIsEditOpen,
    openEdit,
    isDeleteOpen,
    setIsDeleteOpen,
    openDelete,
    isTagsOpen,
    setIsTagsOpen,
    openTags,
    folderPendingDelete,
    requestFolderDelete,
    clearFolderDelete,
  }
}

export type KnowledgeDialogs = ReturnType<typeof useKnowledgeDialogs>
