import type { KnowledgeBaseData } from '@/lib/knowledge/types'
import type { KnowledgeFolder, KnowledgeListFilters } from './types'

/**
 * Search-folders and search-bases answer different shapes: a folder matches its name only,
 * a base matches its name or description. Both share the trim-and-lowercase convention.
 */
function normalizeSearchQuery(searchQuery: string): string {
  return searchQuery.trim().toLowerCase()
}

/**
 * Filter knowledge bases by search query (name or description).
 */
export function filterKnowledgeBases(
  knowledgeBases: KnowledgeBaseData[],
  searchQuery: string
): KnowledgeBaseData[] {
  const query = normalizeSearchQuery(searchQuery)
  if (!query) {
    return knowledgeBases
  }

  return knowledgeBases.filter(
    (kb) => kb.name.toLowerCase().includes(query) || kb.description?.toLowerCase().includes(query)
  )
}

/**
 * Folders in the open folder, answering only to the search term — the resource filters
 * (connectors/content/owner) describe properties a folder does not have.
 */
export function visibleKnowledgeFolders(
  folders: KnowledgeFolder[],
  currentFolderId: string | null,
  searchQuery: string
): KnowledgeFolder[] {
  const siblings = folders.filter((folder) => (folder.parentId ?? null) === currentFolderId)
  const query = normalizeSearchQuery(searchQuery)
  return query ? siblings.filter((folder) => folder.name.toLowerCase().includes(query)) : siblings
}

export interface KnowledgeBaseFolderPlacementParams {
  currentFolderId: string | null
  folderById: ReadonlyMap<string, KnowledgeFolder>
  foldersResolved: boolean
}

/**
 * The bases whose effective placement is the open folder.
 *
 * A `folderId` that no longer names an active folder — a base restored on its own out of
 * Recently Deleted while its folder stayed archived, or a cascade that failed partway —
 * would otherwise match no level at all and leave the base unreachable from every view.
 * Fall it back to the root instead — but only once `foldersResolved` says the index is the
 * complete set for THIS workspace. Gating on a loading flag instead would treat an errored
 * fetch, a disabled query, or the previous workspace's cached folders as "no such folder"
 * and drag every foldered base to the root.
 */
export function knowledgeBasesInFolder(
  knowledgeBases: KnowledgeBaseData[],
  { currentFolderId, folderById, foldersResolved }: KnowledgeBaseFolderPlacementParams
): KnowledgeBaseData[] {
  return knowledgeBases.filter((kb) => {
    const folderId = kb.folderId ?? null
    const effectiveFolderId =
      !foldersResolved || !folderId || folderById.has(folderId) ? folderId : null
    return effectiveFolderId === currentFolderId
  })
}

/**
 * Applies the connector/content/owner facets to bases already placed in the open folder.
 * Facets combine with OR inside a facet and AND across facets; an empty facet passes
 * everything.
 */
export function applyKnowledgeBaseFilters(
  knowledgeBases: KnowledgeBaseData[],
  filters: KnowledgeListFilters
): KnowledgeBaseData[] {
  let result = knowledgeBases

  if (filters.connector.length > 0) {
    result = result.filter((kb) => {
      const hasConnectors = (kb.connectorTypes?.length ?? 0) > 0
      if (filters.connector.includes('connected') && hasConnectors) return true
      if (filters.connector.includes('unconnected') && !hasConnectors) return true
      return false
    })
  }

  if (filters.content.length > 0) {
    result = result.filter((kb) => {
      const docCount = kb.docCount ?? 0
      if (filters.content.includes('has-docs') && docCount > 0) return true
      if (filters.content.includes('empty') && docCount === 0) return true
      return false
    })
  }

  if (filters.owner.length > 0) {
    result = result.filter((kb) => filters.owner.includes(kb.userId))
  }

  return result
}
