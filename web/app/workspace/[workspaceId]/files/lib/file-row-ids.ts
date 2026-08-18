import { parseFolderedRowId } from '@/app/workspace/[workspaceId]/components/folders'

/**
 * Files rows follow the shared foldered-row id scheme — folder rows carry the shared `folder:`
 * prefix (see `folderRowId`) — and add a `file:` prefix for file rows so one selection `Set`
 * and one drop-target predicate can cover both kinds.
 */
const FILE_ROW_PREFIX = 'file:'

export type FilesRowKind = 'file' | 'folder'

export interface ParsedFilesRowId {
  kind: FilesRowKind
  id: string
}

export function fileRowId(fileId: string): string {
  return `${FILE_ROW_PREFIX}${fileId}`
}

/**
 * Folder rows delegate to the shared parser; anything that is not a folder row resolves as a
 * file, tolerating the bare-id form so ids predating the prefix keep resolving.
 */
export function parseFilesRowId(rowId: string): ParsedFilesRowId {
  const parsed = parseFolderedRowId(rowId)
  if (parsed.kind === 'folder') return { kind: 'folder', id: parsed.id }
  if (rowId.startsWith(FILE_ROW_PREFIX)) {
    return { kind: 'file', id: rowId.slice(FILE_ROW_PREFIX.length) }
  }
  return { kind: 'file', id: rowId }
}
