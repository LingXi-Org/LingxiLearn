import { MAX_WORKSPACE_FILE_SIZE } from '@/lib/uploads/shared/types'
import { getFileExtension } from '@/lib/uploads/utils/file-utils'
import {
  SUPPORTED_AUDIO_EXTENSIONS,
  SUPPORTED_CODE_EXTENSIONS,
  SUPPORTED_DOCUMENT_EXTENSIONS,
  SUPPORTED_IMAGE_EXTENSIONS,
  SUPPORTED_VIDEO_EXTENSIONS,
} from '@/lib/uploads/utils/validation'

/** Every extension the Files upload accepts, across all file categories. */
export const SUPPORTED_EXTENSIONS = [
  ...SUPPORTED_DOCUMENT_EXTENSIONS,
  ...SUPPORTED_CODE_EXTENSIONS,
  ...SUPPORTED_AUDIO_EXTENSIONS,
  ...SUPPORTED_VIDEO_EXTENSIONS,
  ...SUPPORTED_IMAGE_EXTENSIONS,
] as const

/** The file input's `accept` attribute, derived from {@link SUPPORTED_EXTENSIONS}. */
export const FILES_ACCEPT_ATTR = SUPPORTED_EXTENSIONS.map((ext) => `.${ext}`).join(',')

export interface UploadPartition {
  /** Files that pass both the size cap and the extension allowlist, in original order. */
  allowed: File[]
  /** Names rejected for exceeding {@link MAX_WORKSPACE_FILE_SIZE}. */
  oversized: string[]
  /** Names rejected for an unsupported extension. */
  unsupported: string[]
}

/**
 * Splits a drop/picker batch into what gets uploaded and what gets reported — pure, so the
 * upload command hook stays orchestration only.
 */
export function partitionUploadCandidates(filesToUpload: File[]): UploadPartition {
  const oversized: string[] = []
  const unsupported: string[] = []
  const allowed: File[] = []

  for (const file of filesToUpload) {
    if (file.size > MAX_WORKSPACE_FILE_SIZE) {
      oversized.push(file.name)
      continue
    }
    const ext = getFileExtension(file.name)
    if (!SUPPORTED_EXTENSIONS.includes(ext as (typeof SUPPORTED_EXTENSIONS)[number])) {
      unsupported.push(file.name)
      continue
    }
    allowed.push(file)
  }

  return { allowed, oversized, unsupported }
}
