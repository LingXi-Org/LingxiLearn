import type { WorkspaceFileRecord } from '@/lib/uploads/contexts/workspace'
import type { WorkspaceFileFolderApi } from '@/hooks/queries/workspace-file-folders'

/**
 * Every folder's total size: its own files plus the roll-up of every descendant folder.
 *
 * Children are indexed once rather than re-scanning `folders` per node — the roll-up visits
 * every folder, so the filter made this quadratic. `visiting` terminates a parent/child cycle:
 * the optimistic folder-move write can produce one in cache, and without the guard this
 * recurses until the stack blows — the same guard the shared folder helpers carry.
 */
export function buildFolderSizeMap(
  files: WorkspaceFileRecord[],
  folders: WorkspaceFileFolderApi[]
): Map<string, number> {
  const directSize = new Map<string, number>()
  for (const file of files) {
    if (file.folderId) {
      directSize.set(file.folderId, (directSize.get(file.folderId) ?? 0) + file.size)
    }
  }

  const childrenByParent = new Map<string, WorkspaceFileFolderApi[]>()
  for (const folder of folders) {
    if (!folder.parentId) continue
    const siblings = childrenByParent.get(folder.parentId)
    if (siblings) siblings.push(folder)
    else childrenByParent.set(folder.parentId, [folder])
  }

  const totalSize = new Map<string, number>()
  const visiting = new Set<string>()
  const getTotal = (folderId: string): number => {
    const cached = totalSize.get(folderId)
    if (cached !== undefined) return cached
    if (visiting.has(folderId)) return 0
    visiting.add(folderId)
    const size =
      (directSize.get(folderId) ?? 0) +
      (childrenByParent.get(folderId) ?? []).reduce((sum, child) => sum + getTotal(child.id), 0)
    visiting.delete(folderId)
    totalSize.set(folderId, size)
    return size
  }
  for (const folder of folders) getTotal(folder.id)
  return totalSize
}
