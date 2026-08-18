'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from '@sim/emcn'
import { createLogger } from '@sim/logger'
import { useRouter } from 'next/navigation'
import type { WorkspaceFileRecord } from '@/lib/uploads/contexts/workspace'
import { folderedResourceListHref } from '@/app/workspace/[workspaceId]/components/folders'
import type { PreviewMode } from '@/app/workspace/[workspaceId]/files/components/file-viewer'
import { isPreviewable } from '@/app/workspace/[workspaceId]/files/components/file-viewer'
import { useFilesRenameMutations } from '@/app/workspace/[workspaceId]/files/hooks/use-files-creation'
import { useFilesDeleteFlow } from '@/app/workspace/[workspaceId]/files/hooks/use-files-delete-flow'
import { useFilesDownloads } from '@/app/workspace/[workspaceId]/files/hooks/use-files-downloads'
import {
  deriveMarkdownFileName,
  isUntitledName,
  uniqueMarkdownName,
} from '@/app/workspace/[workspaceId]/files/untitled-title'
import { useInlineRename } from '@/hooks/use-inline-rename'

const logger = createLogger('Files')

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

export interface UseFileDetailParams {
  workspaceId: string
  /** The routed file; always present when this controller mounts. */
  file: WorkspaceFileRecord
  /** One-shot `?new=1` flag: the freshly created file opens in the editor, compose mode. */
  isNewFile: boolean
  /**
   * The folder the list showed when this file was opened (the `?folderId=` param); deleting
   * the file returns the user there, matching the list's location rather than rederiving it.
   */
  currentFolderId: string | null
  /** Latest workspace files, read through a ref so title derivation never captures a stale list. */
  filesRef: { current: WorkspaceFileRecord[] }
  /** Opens the share dialog via the `shareFileId` URL param, owned by the Files shell. */
  onShareFile: (fileId: string) => void
}

/**
 * The viewer/editor lifecycle controller for the file detail view: preview mode resolution,
 * dirty/save-status tracking, the unsaved-changes navigation guard, Ctrl/Cmd-S, header rename,
 * heading-derived auto-naming, and the detail-scoped download/share/delete commands.
 */
export function useFileDetail({
  workspaceId,
  file,
  isNewFile,
  currentFolderId,
  filesRef,
  onShareFile,
}: UseFileDetailParams) {
  const router = useRouter()
  const { renameFileTo } = useFilesRenameMutations(workspaceId)
  const downloads = useFilesDownloads(workspaceId)
  const deleteFlow = useFilesDeleteFlow(workspaceId)

  const saveRef = useRef<(() => Promise<void>) | null>(null)
  const discardRef = useRef<(() => void) | null>(null)

  const [previewMode, setPreviewMode] = useState<PreviewMode>(() =>
    isNewFile ? 'editor' : isPreviewable(file) ? 'preview' : 'editor'
  )
  const [isDirty, setIsDirty] = useState(false)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [showUnsavedChangesAlert, setShowUnsavedChangesAlert] = useState(false)

  const fileRef = useRef(file)
  fileRef.current = file
  const isDirtyRef = useRef(isDirty)
  isDirtyRef.current = isDirty
  const saveStatusRef = useRef(saveStatus)
  saveStatusRef.current = saveStatus
  const pendingFileNavigationUrlRef = useRef<string | null>(null)

  /**
   * Re-resolves the preview mode when the routed file changes WITHOUT a remount (navigating
   * between two file detail routes keeps this page mounted). The detail view only mounts once
   * its file has resolved, so no deferral is needed — the guard just keeps the initial choice
   * sticky for a given file id.
   */
  const appliedModeFileIdRef = useRef<string | null>(null)
  useEffect(() => {
    if (file.id === appliedModeFileIdRef.current) return
    appliedModeFileIdRef.current = file.id
    const nextMode: PreviewMode = isNewFile ? 'editor' : isPreviewable(file) ? 'preview' : 'editor'
    setPreviewMode((current) => (nextMode === current ? current : nextMode))
  }, [file, isNewFile])

  const handleSave = useCallback(async () => {
    if (!saveRef.current || !isDirtyRef.current || saveStatusRef.current === 'saving') return
    await saveRef.current()
  }, [])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave])

  const handleSaveStatusChange = useCallback((status: SaveStatus, retry?: () => Promise<void>) => {
    setSaveStatus(status)
    if (status === 'error') {
      toast.error(`Failed to save "${fileRef.current?.name ?? 'file'}"`, {
        action: { label: 'Retry', onClick: () => void retry?.() },
      })
    }
  }, [])

  /**
   * Detail breadcrumb/link navigation goes through the router, guarded by the unsaved-changes
   * dialog: a dirty editor stashes the destination and resumes it after a confirmed discard.
   */
  const handleNavigate = useCallback(
    (url: string) => {
      if (isDirtyRef.current) {
        pendingFileNavigationUrlRef.current = url
        setShowUnsavedChangesAlert(true)
        return
      }

      setPreviewMode('editor')
      router.push(url)
    },
    [router]
  )

  const handleDiscardChanges = useCallback(() => {
    discardRef.current?.()
    setShowUnsavedChangesAlert(false)
    setIsDirty(false)
    setSaveStatus('idle')
    setPreviewMode('editor')
    const folderId = fileRef.current?.folderId ?? null
    const targetUrl =
      pendingFileNavigationUrlRef.current ?? folderedResourceListHref('file', workspaceId, folderId)
    pendingFileNavigationUrlRef.current = null
    router.push(targetUrl)
  }, [router, workspaceId])

  const headerRename = useInlineRename({
    onSave: (fileId, name) => renameFileTo(fileId, name),
  })

  const handleStartHeaderRename = useCallback(() => {
    const current = fileRef.current
    if (current) headerRename.startRename(current.id, current.name)
  }, [headerRename.startRename])

  const handleDownloadSelected = useCallback(() => {
    const current = fileRef.current
    if (current) void downloads.downloadFile(current)
  }, [downloads.downloadFile])

  const handleDeleteSelected = useCallback(() => {
    const current = fileRef.current
    if (current) {
      deleteFlow.requestDelete({ fileIds: [current.id], folderIds: [], name: current.name })
    }
  }, [deleteFlow.requestDelete])

  /** Confirmed deletes of the open file return the user to the list they came from. */
  const handleConfirmDelete = useCallback(() => {
    void deleteFlow.confirmDelete(() => {
      setIsDirty(false)
      setSaveStatus('idle')
      router.push(folderedResourceListHref('file', workspaceId, currentFolderId))
    })
  }, [deleteFlow.confirmDelete, router, workspaceId, currentFolderId])

  const handleShareSelected = useCallback(() => {
    const current = fileRef.current
    if (current) onShareFile(current.id)
  }, [onShareFile])

  /**
   * While a file is still untitled, name it after the leading heading the user types in its
   * editor. The editor reports the heading text (debounced); here we re-check the file is still
   * untitled, derive a unique `.md` name among its folder siblings, and rename. A no-op once
   * the file has a real name.
   */
  const handleDeriveTitleFromHeading = useCallback(
    (headingText: string) => {
      const currentFile = fileRef.current
      if (!currentFile || !isUntitledName(currentFile.name)) return
      const derived = deriveMarkdownFileName(headingText)
      if (!derived) return
      const siblingNames = new Set(
        filesRef.current
          .filter(
            (f) =>
              (f.folderId ?? null) === (currentFile.folderId ?? null) && f.id !== currentFile.id
          )
          .map((f) => f.name)
      )
      const name = uniqueMarkdownName(derived, siblingNames)
      if (name === currentFile.name) return
      renameFileTo(currentFile.id, name).catch((err) =>
        logger.error('Failed to auto-name file from heading:', err)
      )
    },
    [filesRef, renameFileTo]
  )

  const handleCyclePreviewMode = useCallback(() => {
    setPreviewMode((prev) => {
      if (prev === 'editor') return 'split'
      if (prev === 'split') return 'preview'
      return 'editor'
    })
  }, [])

  const handleTogglePreview = useCallback(() => {
    setPreviewMode((prev) => (prev === 'preview' ? 'editor' : 'preview'))
  }, [])

  return {
    previewMode,
    saveRef,
    discardRef,
    setIsDirty,
    handleSaveStatusChange,
    handleNavigate,
    showUnsavedChangesAlert,
    setShowUnsavedChangesAlert,
    handleDiscardChanges,
    headerRename,
    handleStartHeaderRename,
    handleDownloadSelected,
    handleDeleteSelected,
    handleConfirmDelete,
    handleShareSelected,
    handleDeriveTitleFromHeading,
    handleCyclePreviewMode,
    handleTogglePreview,
    deleteFlow,
    downloads,
  }
}

export type FileDetailController = ReturnType<typeof useFileDetail>
