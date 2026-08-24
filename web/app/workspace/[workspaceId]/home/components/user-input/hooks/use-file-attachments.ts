'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from '@/components/ui-kit'
import { getMothershipAttachmentPreviewUrl } from '@/lib/copilot/chat/attachment-preview'
import { createLogger } from '@/lib/logger'
import { userFacingError } from '@/lib/product-copy'
import { assertMultiFileUploadAdmission } from '@/lib/uploads/client/admission'
import { uploadInternalFileSession } from '@/lib/uploads/client/session-upload'
import { MAX_WORKSPACE_FILE_SIZE } from '@/lib/uploads/shared/types'
import { generateId } from '@/lib/utils/id'

const logger = createLogger('LingxiHomeFileAttachments')

export interface AttachedFile {
  id: string
  name: string
  size: number
  type: string
  path: string
  key?: string
  uploading: boolean
  previewUrl?: string
}

interface UseFileAttachmentsProps {
  userId?: string
  workspaceId?: string
  disabled?: boolean
  isLoading?: boolean
}

function revokePreviewUrl(url?: string) {
  if (url?.startsWith('blob:')) URL.revokeObjectURL(url)
}

/**
 * Workspace chat attachments are deliberately local to the native Home
 * surface.  The old editor hook lived below the removed `/w` route and also
 * carried workflow-only upload purposes; this adapter only creates the
 * `mothership_attachment` session understood by LingxiLearn.
 */
export function useFileAttachments({ userId, workspaceId, disabled }: UseFileAttachmentsProps) {
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([])
  const [dragCounter, setDragCounter] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const filesRef = useRef<AttachedFile[]>([])

  const update = useCallback((fn: (files: AttachedFile[]) => AttachedFile[]) => {
    const next = fn(filesRef.current)
    filesRef.current = next
    setAttachedFiles(next)
  }, [])

  useEffect(
    () => () => {
      for (const file of filesRef.current) revokePreviewUrl(file.previewUrl)
    },
    []
  )

  const processFiles = useCallback(
    async (fileList: FileList) => {
      if (!userId || !workspaceId || fileList.length === 0) return
      try {
        assertMultiFileUploadAdmission(fileList, {
          existingFiles: filesRef.current,
          maxFileBytes: MAX_WORKSPACE_FILE_SIZE,
        })
      } catch (error) {
        toast.error('无法添加文件', {
          description: userFacingError(error, 'uploadFailed'),
        })
        return
      }

      const files = Array.from(fileList)
      const placeholders = files.map<AttachedFile>((file) => ({
        id: generateId(),
        name: file.name,
        size: file.size,
        type: file.type || 'application/octet-stream',
        path: '',
        uploading: true,
        previewUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
      }))
      update((current) => [...current, ...placeholders])

      await Promise.all(
        files.map(async (file, index) => {
          const placeholder = placeholders[index]
          try {
            const result = await uploadInternalFileSession({
              purpose: 'mothership_attachment',
              file,
              workspaceId,
            })
            update((current) =>
              current.map((item) =>
                item.id === placeholder.id
                  ? {
                      ...item,
                      path: result.path,
                      key: result.key,
                      uploading: false,
                      previewUrl:
                        item.previewUrl ??
                        getMothershipAttachmentPreviewUrl({
                          key: result.key,
                          media_type: item.type,
                        }),
                    }
                  : item
              )
            )
          } catch (error) {
            logger.error('Attachment upload failed', error)
            revokePreviewUrl(placeholder.previewUrl)
            update((current) => current.filter((item) => item.id !== placeholder.id))
            toast.error(`无法上传“${file.name}”`, {
              description: userFacingError(error, 'uploadFailed'),
            })
          }
        })
      )
    },
    [userId, workspaceId, update]
  )

  const handleFileSelect = useCallback(() => {
    if (!disabled) fileInputRef.current?.click()
  }, [disabled])

  const handleFileChange = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      if (event.target.files) await processFiles(event.target.files)
      event.target.value = ''
    },
    [processFiles]
  )

  const handleFileClick = useCallback((file: AttachedFile) => {
    if (file.previewUrl) window.open(file.previewUrl, '_blank', 'noopener,noreferrer')
  }, [])

  const handleDragEnter = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    setDragCounter((value) => value + 1)
  }, [])
  const handleDragLeave = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    setDragCounter((value) => Math.max(0, value - 1))
  }, [])
  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
  }, [])
  const handleDrop = useCallback(
    async (event: React.DragEvent) => {
      event.preventDefault()
      setDragCounter(0)
      if (event.dataTransfer.files) await processFiles(event.dataTransfer.files)
    },
    [processFiles]
  )

  const removeFile = useCallback(
    (id: string) => {
      const file = filesRef.current.find((item) => item.id === id)
      revokePreviewUrl(file?.previewUrl)
      update((current) => current.filter((item) => item.id !== id))
    },
    [update]
  )

  const clearAttachedFiles = useCallback(() => {
    for (const file of filesRef.current) revokePreviewUrl(file.previewUrl)
    filesRef.current = []
    setAttachedFiles([])
  }, [])

  const restoreAttachedFiles = useCallback((files: AttachedFile[]) => {
    filesRef.current = files
    setAttachedFiles(files)
  }, [])

  return {
    attachedFiles,
    fileInputRef,
    isDragging: dragCounter > 0,
    processFiles,
    handleFileSelect,
    handleFileChange,
    handleFileClick,
    handleDragEnter,
    handleDragLeave,
    handleDragOver,
    handleDrop,
    removeFile,
    clearAttachedFiles,
    restoreAttachedFiles,
  }
}
