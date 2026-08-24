'use client'

import { type ChangeEvent, type RefObject, useCallback, useRef, useState } from 'react'
import { toast } from '@/components/ui-kit'
import { createLogger } from '@/lib/logger'
import { userFacingError } from '@/lib/product-copy'
import { pickCsvFiles } from '@/app/workspace/[workspaceId]/tables/csv'
import { useImportCsv } from '@/hooks/queries/tables'
import { useImportTrayStore } from '@/stores/table/import-tray/store'

const logger = createLogger('TablesCsvImport')

export interface UseCsvImportOptions {
  workspaceId: string
  /**
   * Canonical path of the folder the import should land in, resolved AT CALL TIME — imports
   * run sequentially, and the open folder may change between files.
   */
  getFolderPath: () => string
}

export interface CsvImportController {
  /** Ref for the page's hidden `<input type="file">`. */
  csvInputRef: RefObject<HTMLInputElement | null>
  /** `onChange` for that hidden input: picks, validates, and imports. */
  handleCsvChange: (event: ChangeEvent<HTMLInputElement>) => Promise<void>
  /** Opens the native file picker (header action, context menu, command palette). */
  openFilePicker: () => void
  /** Imports the given files sequentially; drives the tray uploads while they fly. */
  importFiles: (files: File[]) => Promise<void>
  uploading: boolean
  uploadProgress: { completed: number; total: number }
  /** `n/m` while a batch is in flight, otherwise the static action label. */
  uploadButtonLabel: string
}

/**
 * CSV import controller for the Tables list. Owns the upload batch state and the import-tray
 * optimistic uploads; deliberately knows nothing about the resource list it sits next to, so
 * it can be tested (and reused) without the list mounted. Import progress lives here and in
 * the tray store — never in the table domain state.
 */
export function useCsvImport({
  workspaceId,
  getFolderPath,
}: UseCsvImportOptions): CsvImportController {
  const importCsv = useImportCsv()
  const [uploadProgress, setUploadProgress] = useState({ completed: 0, total: 0 })
  const csvInputRef = useRef<HTMLInputElement>(null)

  const uploading = uploadProgress.total > 0

  const importCsvAsync = importCsv.mutateAsync
  const importFiles = useCallback(
    async (csvFiles: File[]) => {
      if (csvFiles.length === 0 || !workspaceId) return
      try {
        setUploadProgress({ completed: 0, total: csvFiles.length })
        for (let index = 0; index < csvFiles.length; index++) {
          const file = csvFiles[index]
          let importId: string | null = null
          toast.success(`Importing "${file.name}" in the background`)
          try {
            await importCsvAsync({
              workspaceId,
              folderPath: getFolderPath(),
              file,
              onCreated: (createdImportId) => {
                importId = createdImportId
                useImportTrayStore.getState().startUpload({
                  uploadId: createdImportId,
                  workspaceId,
                  title: file.name,
                })
              },
              onProgress: (percent) => {
                if (importId) useImportTrayStore.getState().setUploadPercent(importId, percent)
              },
            })
            if (importId) {
              useImportTrayStore.getState().endUpload(importId)
              useImportTrayStore.getState().consumeCanceled(importId)
            }
          } catch {
            if (importId) useImportTrayStore.getState().endUpload(importId)
          } finally {
            setUploadProgress({ completed: index + 1, total: csvFiles.length })
          }
        }
      } catch (err) {
        logger.error('Error uploading CSV:', err)
        toast.error(userFacingError(err, 'uploadFailed'))
      } finally {
        setUploadProgress({ completed: 0, total: 0 })
        if (csvInputRef.current) {
          csvInputRef.current.value = ''
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mutation objects are unstable; mutateAsync is stable in v5
    [workspaceId, getFolderPath, importCsvAsync]
  )

  const handleCsvChange = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const list = event.target.files
      // A canceled picker never fires `change`, but an emptied selection reports an empty
      // list — not an error, so return silently rather than toast.
      if (!list || list.length === 0) return
      const csvFiles = pickCsvFiles(list)
      if (csvFiles.length === 0) {
        toast.error('请选择 CSV 或 TSV 文件')
        if (csvInputRef.current) csvInputRef.current.value = ''
        return
      }
      await importFiles(csvFiles)
    },
    [importFiles]
  )

  const openFilePicker = useCallback(() => {
    csvInputRef.current?.click()
  }, [])

  const uploadButtonLabel = uploading
    ? `${uploadProgress.completed}/${uploadProgress.total}`
    : 'Import CSV'

  return {
    csvInputRef,
    handleCsvChange,
    openFilePicker,
    importFiles,
    uploading,
    uploadProgress,
    uploadButtonLabel,
  }
}
