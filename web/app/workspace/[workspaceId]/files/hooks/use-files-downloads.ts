'use client'

import { useCallback, useRef, useState } from 'react'
import { toast } from '@sim/emcn'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/lib/utils/errors'
import { usePostHog } from 'posthog-js/react'
import { captureEvent } from '@/lib/posthog/client'
import { triggerArchiveDownload, triggerFileDownload } from '@/lib/uploads/client/download'
import type { WorkspaceFileRecord } from '@/lib/uploads/contexts/workspace'

const logger = createLogger('Files')

/**
 * The download commands shared by the list and the detail view: a single file download and
 * the selection archive (zip) download, with the archive guarded against concurrent runs —
 * each in-flight archive holds the whole zip in tab memory.
 */
export function useFilesDownloads(workspaceId: string) {
  const posthog = usePostHog()
  const posthogRef = useRef(posthog)
  posthogRef.current = posthog

  const [isDownloadingArchive, setIsDownloadingArchive] = useState(false)
  const archiveDownloadInFlightRef = useRef(false)

  const downloadFile = useCallback(
    async (file: WorkspaceFileRecord) => {
      try {
        await triggerFileDownload(file)
        captureEvent(posthogRef.current, 'file_downloaded', {
          workspace_id: workspaceId,
          is_bulk: false,
          file_count: 1,
        })
      } catch (err) {
        logger.error('Failed to download file:', err)
        toast.error(getErrorMessage(err, `Failed to download "${file.name}"`))
      }
    },
    [workspaceId]
  )

  const downloadArchive = useCallback(
    async (selection: { fileIds?: string[]; folderIds?: string[] }) => {
      if (archiveDownloadInFlightRef.current) return
      archiveDownloadInFlightRef.current = true
      setIsDownloadingArchive(true)
      try {
        await triggerArchiveDownload({ workspaceId, ...selection })
      } catch (err) {
        logger.error('Failed to download selection:', err)
        toast.error(getErrorMessage(err, 'Failed to download the selected files'))
      } finally {
        archiveDownloadInFlightRef.current = false
        setIsDownloadingArchive(false)
      }
    },
    [workspaceId]
  )

  /**
   * Selection download: a single bare file downloads directly; anything else (several
   * files, any folder) becomes one archive.
   */
  const downloadSelection = useCallback(
    async (selectedFiles: WorkspaceFileRecord[], selectedFolderIds: string[]) => {
      if (selectedFiles.length === 1 && selectedFolderIds.length === 0) {
        await downloadFile(selectedFiles[0])
        return
      }
      const fileIds = selectedFiles.map((file) => file.id)
      if (fileIds.length === 0 && selectedFolderIds.length === 0) return
      captureEvent(posthogRef.current, 'file_downloaded', {
        workspace_id: workspaceId,
        is_bulk: true,
        file_count: fileIds.length + selectedFolderIds.length,
      })
      await downloadArchive({ fileIds, folderIds: selectedFolderIds })
    },
    [workspaceId, downloadFile, downloadArchive]
  )

  return { downloadFile, downloadArchive, downloadSelection, isDownloadingArchive }
}

export type FilesDownloadsController = ReturnType<typeof useFilesDownloads>
