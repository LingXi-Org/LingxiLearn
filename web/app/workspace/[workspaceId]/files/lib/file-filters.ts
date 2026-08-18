import type { WorkspaceFileRecord } from '@/lib/uploads/contexts/workspace'
import {
  getFileExtension,
  isAudioFileType,
  isVideoFileType,
  resolveEffectiveMimeType,
} from '@/lib/uploads/utils/file-utils'
import { isSupportedExtension } from '@/lib/uploads/utils/validation'
import type { WorkspaceFileFolderApi } from '@/hooks/queries/workspace-file-folders'

/** The Files list's multi-select URL filters (search travels separately, debounced). */
export interface FilesListFilters {
  type: string[]
  size: string[]
  uploadedBy: string[]
}

/** Normalizes the raw search input once; an empty needle disables name matching. */
export function toSearchNeedle(searchTerm: string): string {
  return searchTerm.trim().toLowerCase()
}

/**
 * Folder siblings of `folderId`, narrowed by the search needle. Folders ignore the
 * type/size/uploader filters — those describe file content, not folders.
 */
export function listFolderSiblings(
  folders: WorkspaceFileFolderApi[],
  folderId: string | null,
  needle: string
): WorkspaceFileFolderApi[] {
  const siblings = folders.filter((folder) => (folder.parentId ?? null) === folderId)
  if (!needle) return siblings
  return siblings.filter((folder) => folder.name.toLowerCase().includes(needle))
}

/** Type/size/uploader predicates for one file, independent of its folder or name. */
export function fileMatchesFilters(file: WorkspaceFileRecord, filters: FilesListFilters): boolean {
  if (filters.type.length > 0) {
    const ext = getFileExtension(file.name)
    // Matching the raw stored type would hide every file the browser uploaded as
    // `application/octet-stream` from the audio/video/image filters.
    const type = resolveEffectiveMimeType(file.type, file.name)
    const matches =
      (filters.type.includes('document') && isSupportedExtension(ext)) ||
      (filters.type.includes('audio') && isAudioFileType(type)) ||
      (filters.type.includes('video') && isVideoFileType(type)) ||
      (filters.type.includes('image') && type.startsWith('image/'))
    if (!matches) return false
  }

  if (filters.size.length > 0) {
    const matches =
      (filters.size.includes('small') && file.size < 1_048_576) ||
      (filters.size.includes('medium') && file.size >= 1_048_576 && file.size <= 10_485_760) ||
      (filters.size.includes('large') && file.size > 10_485_760)
    if (!matches) return false
  }

  if (filters.uploadedBy.length > 0 && !filters.uploadedBy.includes(file.uploadedBy)) {
    return false
  }

  return true
}

/** Files directly inside `folderId`, narrowed by the search needle and the URL filters. */
export function listFolderFiles(
  files: WorkspaceFileRecord[],
  folderId: string | null,
  needle: string,
  filters: FilesListFilters
): WorkspaceFileRecord[] {
  return files.filter(
    (file) =>
      (file.folderId ?? null) === folderId &&
      (!needle || file.name.toLowerCase().includes(needle)) &&
      fileMatchesFilters(file, filters)
  )
}
