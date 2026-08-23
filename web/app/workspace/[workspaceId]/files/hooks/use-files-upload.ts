'use client'

import { type ChangeEvent, type DragEvent, useCallback, useRef, useState } from 'react'
import { toast } from '@/components/ui-kit'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/lib/utils/errors'
import { useLimitUpgradeToast } from '@/lib/billing/client'
import {
  FILES_ACCEPT_ATTR,
  partitionUploadCandidates,
} from '@/app/workspace/[workspaceId]/files/lib/file-upload-policy'
import { useUploadWorkspaceFile } from '@/hooks/queries/workspace-files'

const logger = createLogger('Files')

const hasExternalFiles = (dataTransfer: DataTransfer): boolean =>
  dataTransfer.types.includes('Files')

export interface UseFilesUploadParams {
  workspaceId: string
  /** From the command matrix — a reader gets no upload path at all. */
  canUpload: boolean
  /** Folder an unprompted upload (picker, page drop) lands in. */
  currentFolderId: string | null
}

/**
 * The upload command: picker + sequential uploads with progress, size/extension validation
 * via the pure upload policy, and the page-level external-drop overlay.
 */
export function useFilesUpload({ workspaceId, canUpload, currentFolderId }: UseFilesUploadParams) {
  const uploadFile = useUploadWorkspaceFile()
  const notifyLimit = useLimitUpgradeToast()

  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState({
    completed: 0,
    total: 0,
    currentPercent: 0,
  })
  const [isDraggingOver, setIsDraggingOver] = useState(false)
  const dragCounterRef = useRef(0)

  const uploadFiles = useCallback(
    async (filesToUpload: File[], targetFolderId = currentFolderId) => {
      if (!workspaceId || filesToUpload.length === 0 || !canUpload) return

      const { allowed, oversized, unsupported } = partitionUploadCandidates(filesToUpload)
      if (oversized.length > 0) {
        toast.error(
          oversized.length === 1
            ? `${oversized[0]} exceeds the 5 GiB upload limit`
            : `${oversized.length} files exceed the 5 GiB upload limit`
        )
      }
      if (unsupported.length > 0) {
        logger.warn('Unsupported file types skipped:', unsupported)
      }
      if (allowed.length === 0) return

      try {
        setUploading(true)
        setUploadProgress({ completed: 0, total: allowed.length, currentPercent: 0 })

        for (let i = 0; i < allowed.length; i++) {
          try {
            await uploadFile.mutateAsync({
              workspaceId,
              file: allowed[i],
              folderId: targetFolderId,
              onProgress: ({ percent }) => {
                setUploadProgress((prev) => ({ ...prev, currentPercent: percent }))
              },
            })
            setUploadProgress({
              completed: i + 1,
              total: allowed.length,
              currentPercent: 0,
            })
          } catch (err) {
            logger.error('Error uploading file:', err)
            const message = getErrorMessage(err)
            if (/storage limit/i.test(message)) {
              notifyLimit('storage', message)
            } else {
              toast.error(`Failed to upload "${allowed[i].name}"`)
            }
          }
        }
      } catch (err) {
        logger.error('Error uploading file:', err)
      } finally {
        setUploading(false)
        setUploadProgress({ completed: 0, total: 0, currentPercent: 0 })
      }
    },
    [workspaceId, canUpload, currentFolderId, notifyLimit]
  )

  const openFilePicker = useCallback(() => {
    if (!canUpload || uploading) return false
    fileInputRef.current?.click()
    return true
  }, [canUpload, uploading])

  const handleFileChange = useCallback(
    async (e: ChangeEvent<HTMLInputElement>) => {
      const list = e.target.files
      if (!list || list.length === 0) return
      await uploadFiles(Array.from(list))
      if (fileInputRef.current) fileInputRef.current.value = ''
    },
    [uploadFiles]
  )

  // Page-level external drop: the overlay + counter live here, the upload target is the
  // open folder (row-level drops onto folders are handled by the row drag-drop config).
  const handleDragEnter = useCallback((e: DragEvent) => {
    if (!hasExternalFiles(e.dataTransfer)) return
    e.preventDefault()
    dragCounterRef.current++
    setIsDraggingOver(true)
  }, [])

  const handleDragLeave = useCallback((e: DragEvent) => {
    if (!hasExternalFiles(e.dataTransfer)) return
    dragCounterRef.current--
    if (dragCounterRef.current === 0) setIsDraggingOver(false)
  }, [])

  const handleDragOver = useCallback((e: DragEvent) => {
    if (!hasExternalFiles(e.dataTransfer)) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }, [])

  const handleDrop = useCallback(
    async (e: DragEvent) => {
      if (!hasExternalFiles(e.dataTransfer)) return
      e.preventDefault()
      dragCounterRef.current = 0
      setIsDraggingOver(false)
      const dropped = Array.from(e.dataTransfer.files)
      if (dropped.length > 0) await uploadFiles(dropped)
    },
    [uploadFiles]
  )

  /** Reset the overlay counters when a row-level drop already consumed the external files. */
  const resetExternalDrag = useCallback(() => {
    dragCounterRef.current = 0
    setIsDraggingOver(false)
  }, [])

  const uploadButtonLabel =
    uploading && uploadProgress.total > 0
      ? uploadProgress.currentPercent > 0 && uploadProgress.currentPercent < 100
        ? `${uploadProgress.completed}/${uploadProgress.total} · ${uploadProgress.currentPercent}%`
        : `${uploadProgress.completed}/${uploadProgress.total}`
      : uploading
        ? 'Uploading...'
        : 'Upload'

  return {
    uploading,
    uploadProgress,
    uploadButtonLabel,
    uploadFiles,
    fileInputRef,
    fileInputAccept: FILES_ACCEPT_ATTR,
    openFilePicker,
    handleFileChange,
    isDraggingOver,
    handleDragEnter,
    handleDragLeave,
    handleDragOver,
    handleDrop,
    resetExternalDrag,
  }
}

export type FilesUploadController = ReturnType<typeof useFilesUpload>
