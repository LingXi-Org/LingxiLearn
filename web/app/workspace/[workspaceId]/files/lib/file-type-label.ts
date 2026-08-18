import { getFileExtension, resolveEffectiveMimeType } from '@/lib/uploads/utils/file-utils'

/** Human labels for the file types the Files list can display, keyed by effective MIME type. */
export const MIME_TYPE_LABELS: Record<string, string> = {
  'application/pdf': 'PDF',
  'application/msword': 'Word',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word',
  'application/vnd.ms-excel': 'Excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel',
  'application/vnd.ms-powerpoint': 'PowerPoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PowerPoint',
  'application/json': 'JSON',
  'application/x-yaml': 'YAML',
  'text/csv': 'CSV',
  'text/plain': 'Text',
  'text/html': 'HTML',
  'text/markdown': 'Markdown',
}

/**
 * The display label of a file's `type` column (and its sort key when that column is active).
 * Resolves the effective MIME type first, so a browser upload stored as
 * `application/octet-stream` still reads as Audio/Video/Image from its extension.
 */
export function formatFileType(storedType: string | null, filename: string): string {
  const mimeType = resolveEffectiveMimeType(storedType, filename)

  if (MIME_TYPE_LABELS[mimeType]) {
    return MIME_TYPE_LABELS[mimeType]
  }

  if (mimeType.startsWith('audio/')) return 'Audio'
  if (mimeType.startsWith('video/')) return 'Video'
  if (mimeType.startsWith('image/')) return 'Image'

  const ext = getFileExtension(filename)
  if (ext) return ext.toUpperCase()

  return storedType ?? 'File'
}
