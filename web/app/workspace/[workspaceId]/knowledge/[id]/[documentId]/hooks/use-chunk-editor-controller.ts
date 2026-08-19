'use client'

import { useCallback, useEffect, useEffectEvent, useMemo, useRef, useState } from 'react'
import { useQueryStates } from 'nuqs'
import type { ChunkData } from '@/lib/knowledge/types'
import {
  documentParsers,
  documentUrlKeys,
} from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/search-params'

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

interface UseChunkEditorControllerParams {
  /** Chunks of the current view (search page or browse page). */
  displayChunks: ChunkData[]
  currentPage: number
  totalPages: number
  goToPage: (page: number) => Promise<unknown>
}

/**
 * Owns the inline chunk editor: the URL-driven open chunk, the create session,
 * dirty/save lifecycle with its guards (route change, back, keyboard shortcut,
 * tab close), and cross-page prev/next navigation. Chunk mutations themselves
 * live in `useChunkCommands`.
 */
export function useChunkEditorController({
  displayChunks,
  currentPage,
  totalPages,
  goToPage,
}: UseChunkEditorControllerParams) {
  const [{ chunk: chunkFromURL }, setDocumentParams] = useQueryStates(
    documentParsers,
    documentUrlKeys
  )

  /**
   * The open chunk is sourced directly from the URL `chunk` param (single
   * source of truth) so back/forward, deep links, and external navigation
   * drive the editor; opening/closing a chunk writes the param.
   */
  const selectedChunkId = chunkFromURL
  /** Opening a chunk is a destination (back closes it); clearing replaces. */
  const setSelectedChunkId = useCallback(
    (chunkId: string | null) => {
      void setDocumentParams({ chunk: chunkId }, chunkId !== null ? { history: 'push' } : undefined)
    },
    [setDocumentParams]
  )

  const [isCreatingNewChunk, setIsCreatingNewChunk] = useState(false)
  const [isDirty, setIsDirty] = useState(false)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [showUnsavedChangesAlert, setShowUnsavedChangesAlert] = useState(false)
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null)
  const saveRef = useRef<(() => Promise<void>) | null>(null)
  const saveStatusRef = useRef<SaveStatus>('idle')
  saveStatusRef.current = saveStatus

  // Keep refs so polling callbacks can read fresh data after a page change.
  const displayChunksRef = useRef(displayChunks)
  displayChunksRef.current = displayChunks
  const totalPagesRef = useRef(totalPages)
  totalPagesRef.current = totalPages

  const isInEditorView = selectedChunkId !== null || isCreatingNewChunk

  const selectedChunk = useMemo(
    () => (selectedChunkId ? (displayChunks.find((c) => c.id === selectedChunkId) ?? null) : null),
    [selectedChunkId, displayChunks]
  )

  const currentChunkIndex = useMemo(
    () => (selectedChunk ? displayChunks.findIndex((c) => c.id === selectedChunk.id) : -1),
    [selectedChunk, displayChunks]
  )
  const canNavigatePrev = currentChunkIndex > 0 || currentPage > 1
  const canNavigateNext = currentChunkIndex < displayChunks.length - 1 || currentPage < totalPages

  const closeEditor = useCallback(() => {
    setSelectedChunkId(null)
    setIsCreatingNewChunk(false)
    setIsDirty(false)
    setSaveStatus('idle')
  }, [setSelectedChunkId])

  const guardDirtyAction = useCallback(
    (action: () => void) => {
      if (isDirty) {
        setPendingAction(() => action)
        setShowUnsavedChangesAlert(true)
      } else {
        action()
      }
    },
    [isDirty]
  )

  const handleBackAttempt = useCallback(() => {
    guardDirtyAction(closeEditor)
  }, [guardDirtyAction, closeEditor])

  const handleSave = useCallback(async () => {
    if (!saveRef.current || !isDirty || saveStatusRef.current === 'saving') return
    if (isCreatingNewChunk) {
      setSaveStatus('saving')
      try {
        await saveRef.current()
        setSaveStatus('saved')
      } catch {
        setSaveStatus('error')
        setTimeout(() => setSaveStatus('idle'), 2000)
      }
    } else {
      await saveRef.current()
    }
  }, [isDirty, isCreatingNewChunk])

  const handleUnsavedChangesOpenChange = useCallback((open: boolean) => {
    if (!open) {
      setShowUnsavedChangesAlert(false)
      setPendingAction(null)
    }
  }, [])

  const handleDiscardChanges = useCallback(() => {
    setShowUnsavedChangesAlert(false)
    const action = pendingAction
    setPendingAction(null)
    if (action) {
      setIsDirty(false)
      action()
    } else {
      closeEditor()
    }
  }, [pendingAction, closeEditor])

  const handleSaveEvent = useEffectEvent(handleSave)

  useEffect(() => {
    if (!isInEditorView) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        handleSaveEvent()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isInEditorView, handleSaveEvent])

  useEffect(() => {
    if (!isDirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  const navigateToChunk = useCallback(
    async (direction: 'prev' | 'next') => {
      if (!selectedChunk) return

      if (direction === 'prev') {
        if (currentChunkIndex > 0) {
          setSelectedChunkId(displayChunks[currentChunkIndex - 1].id)
        } else if (currentPage > 1) {
          await goToPage(currentPage - 1)
          // Read fresh displayChunks via ref after the page change lands.
          let retries = 0
          const checkAndSelect = () => {
            const chunks = displayChunksRef.current
            if (chunks.length > 0 && chunks !== displayChunks) {
              setSelectedChunkId(chunks[chunks.length - 1].id)
            } else if (retries < 50) {
              retries++
              setTimeout(checkAndSelect, 100)
            }
          }
          setTimeout(checkAndSelect, 0)
        }
      } else {
        if (currentChunkIndex < displayChunks.length - 1) {
          setSelectedChunkId(displayChunks[currentChunkIndex + 1].id)
        } else if (currentPage < totalPages) {
          await goToPage(currentPage + 1)
          let retries = 0
          const checkAndSelect = () => {
            const chunks = displayChunksRef.current
            if (chunks.length > 0 && chunks !== displayChunks) {
              setSelectedChunkId(chunks[0].id)
            } else if (retries < 50) {
              retries++
              setTimeout(checkAndSelect, 100)
            }
          }
          setTimeout(checkAndSelect, 0)
        }
      }
    },
    [
      selectedChunk,
      currentChunkIndex,
      displayChunks,
      currentPage,
      totalPages,
      goToPage,
      setSelectedChunkId,
    ]
  )

  const handleNavigateChunk = useCallback(
    (direction: 'prev' | 'next') => {
      guardDirtyAction(() => void navigateToChunk(direction))
    },
    [guardDirtyAction, navigateToChunk]
  )

  /**
   * Confirms before a crumb navigates away from an unsaved chunk — a route change unmounts the
   * editor, so the edit is gone with no way back.
   *
   * Gated on the editor being open rather than on `isDirty` alone: `UnsavedChangesModal` mounts
   * only alongside the editor, but `isDirty` outlives a URL-driven unmount (browser Back off an
   * edited chunk), where guarding would raise a modal nothing renders and deaden the crumb.
   */
  const guardRouteChange = useCallback(
    (navigate: () => void) => {
      if (isCreatingNewChunk || selectedChunkId) guardDirtyAction(navigate)
      else navigate()
    },
    [isCreatingNewChunk, selectedChunkId, guardDirtyAction]
  )

  const handleNewChunk = useCallback(() => {
    guardDirtyAction(() => {
      setIsCreatingNewChunk(true)
      setSelectedChunkId(null)
      setIsDirty(false)
      setSaveStatus('idle')
    })
  }, [guardDirtyAction, setSelectedChunkId])

  const handleChunkCreated = useCallback(
    async (chunkId: string) => {
      setIsCreatingNewChunk(false)
      setIsDirty(false)
      setSaveStatus('idle')

      // New chunks append at the end — navigate to last page so the chunk is visible.
      // totalPages in the closure may be stale if the new chunk creates a new page,
      // so we start at the current last page, then poll displayChunksRef. If the chunk
      // isn't found, totalPagesRef will have the updated count after React Query refetches,
      // so we navigate to the new last page and keep polling.
      await goToPage(totalPages)
      let retries = 0
      let navigatedToNewPage = false
      const checkAndSelect = () => {
        const found = displayChunksRef.current.some((c) => c.id === chunkId)
        if (found) {
          setSelectedChunkId(chunkId)
        } else if (!navigatedToNewPage && totalPagesRef.current > totalPages) {
          // A new page was created — navigate to it
          navigatedToNewPage = true
          retries = 0
          void goToPage(totalPagesRef.current)
          setTimeout(checkAndSelect, 100)
        } else if (retries < 50) {
          retries++
          setTimeout(checkAndSelect, 100)
        }
      }
      setTimeout(checkAndSelect, 0)
    },
    [goToPage, totalPages, setSelectedChunkId]
  )

  const saveLabel =
    saveStatus === 'saving'
      ? isCreatingNewChunk
        ? 'Creating...'
        : 'Saving...'
      : saveStatus === 'saved'
        ? isCreatingNewChunk
          ? 'Created'
          : 'Saved'
        : saveStatus === 'error'
          ? isCreatingNewChunk
            ? 'Create failed'
            : 'Save failed'
          : isCreatingNewChunk
            ? 'Create Chunk'
            : 'Save'

  return {
    // Editor state
    selectedChunkId,
    setSelectedChunkId,
    selectedChunk,
    isCreatingNewChunk,
    isInEditorView,
    isDirty,
    setIsDirty,
    saveStatus,
    setSaveStatus,
    saveLabel,
    saveRef,
    // Guards and lifecycle
    guardDirtyAction,
    guardRouteChange,
    handleBackAttempt,
    handleSave,
    showUnsavedChangesAlert,
    handleUnsavedChangesOpenChange,
    handleDiscardChanges,
    closeEditor,
    // Navigation
    currentChunkIndex,
    canNavigatePrev,
    canNavigateNext,
    handleNavigateChunk,
    handleNewChunk,
    handleChunkCreated,
  }
}

export type ChunkEditorController = ReturnType<typeof useChunkEditorController>
