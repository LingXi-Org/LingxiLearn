import type { WorkspaceFileRecord } from '@/lib/uploads/contexts/workspace'
import type { SortableResource } from '@/app/workspace/[workspaceId]/components/folders'
import { formatFileType } from '@/app/workspace/[workspaceId]/files/lib/file-type-label'
import type { FILE_SORT_COLUMNS } from '@/app/workspace/[workspaceId]/files/search-params'
import type { WorkspaceMember } from '@/hooks/queries/workspace'
import type { WorkspaceFileFolderApi } from '@/hooks/queries/workspace-file-folders'

export type FileSortColumn = (typeof FILE_SORT_COLUMNS)[number]

/** Folders' value in the `type` column — also their sort key when that column is active. */
export const FOLDER_TYPE_LABEL = 'Folder' as const

/** One row of the merged folder+file list, before it becomes a `ResourceRow`. */
export type FileListEntry =
  | { kind: 'folder'; folder: WorkspaceFileFolderApi }
  | { kind: 'file'; file: WorkspaceFileRecord }

/** Lookups a sort key may need beyond the entry itself. */
export interface FileSortContext {
  membersById: Map<string, WorkspaceMember>
  folderSizeMap: Map<string, number>
}

export function sortKeyForFolder(
  folder: WorkspaceFileFolderApi,
  column: FileSortColumn,
  ctx: FileSortContext
): string | number | null {
  switch (column) {
    case 'size':
      return ctx.folderSizeMap.get(folder.id) ?? 0
    case 'type':
      return FOLDER_TYPE_LABEL
    case 'created':
      return new Date(folder.createdAt).getTime()
    case 'updated':
      return new Date(folder.updatedAt).getTime()
    case 'owner':
      return ctx.membersById.get(folder.userId)?.name ?? null
    default:
      return folder.name
  }
}

export function sortKeyForFile(
  file: WorkspaceFileRecord,
  column: FileSortColumn,
  ctx: FileSortContext
): string | number | null {
  switch (column) {
    case 'size':
      return file.size
    case 'type':
      return formatFileType(file.type, file.name)
    case 'created':
      return new Date(file.uploadedAt).getTime()
    case 'updated':
      return new Date(file.updatedAt).getTime()
    case 'owner':
      return ctx.membersById.get(file.uploadedBy)?.name ?? null
    default:
      return file.name
  }
}

export interface BuildSortableFileEntriesParams {
  visibleFolders: WorkspaceFileFolderApi[]
  filteredFiles: WorkspaceFileRecord[]
  sortColumn: FileSortColumn
  pinnedFolderIds: ReadonlySet<string>
  pinnedFileIds: ReadonlySet<string>
  ctx: FileSortContext
}

/**
 * Decorates folders and files into ONE sortable list — a folder never outranks a file it ties
 * with, so a pinned file reaches the top of the list rather than the top of the file section.
 *
 * Each row's key + pinned flag is computed ONCE (O(N)) so the comparator never re-runs Date
 * parsing, `formatFileType`, or member lookups per comparison. Every Files column has a folder
 * equivalent (folders carry a size roll-up and sort as type "Folder"), so no entry needs a
 * null key here.
 */
export function buildSortableFileEntries({
  visibleFolders,
  filteredFiles,
  sortColumn,
  pinnedFolderIds,
  pinnedFileIds,
  ctx,
}: BuildSortableFileEntriesParams): SortableResource<FileListEntry>[] {
  const entries: SortableResource<FileListEntry>[] = []

  for (const folder of visibleFolders) {
    entries.push({
      item: { kind: 'folder', folder },
      pinned: pinnedFolderIds.has(folder.id),
      name: folder.name,
      key: sortKeyForFolder(folder, sortColumn, ctx),
    })
  }

  for (const file of filteredFiles) {
    entries.push({
      item: { kind: 'file', file },
      pinned: pinnedFileIds.has(file.id),
      name: file.name,
      key: sortKeyForFile(file, sortColumn, ctx),
    })
  }

  return entries
}
