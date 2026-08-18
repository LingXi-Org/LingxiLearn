import type { KnowledgeBaseData } from '@/lib/knowledge/types'
import type { SortableResource } from '@/app/workspace/[workspaceId]/components/folders'
import type { KNOWLEDGE_SORT_COLUMNS } from '../search-params'
import type { KnowledgeFolder, KnowledgeListItem } from './types'

export type KnowledgeSortColumn = (typeof KNOWLEDGE_SORT_COLUMNS)[number]

export interface DecorateKnowledgeListItemsParams {
  folders: KnowledgeFolder[]
  bases: KnowledgeBaseData[]
  sortColumn: KnowledgeSortColumn
  pinnedFolderIds: ReadonlySet<string>
  pinnedBaseIds: ReadonlySet<string>
  /** Display name per member id, for the owner column's sort key. */
  memberNameById: ReadonlyMap<string, string>
}

/**
 * Decorates folders and bases into ONE sortable list — a folder never outranks a base it
 * ties with, so a pinned base reaches the top of the list rather than the top of the base
 * section.
 *
 * Each row's key + pinned flag is computed ONCE (O(N)) so the comparator in
 * {@link sortResources} never re-runs Date parsing or member lookups per comparison.
 * Folders carry no document, token, or connector count, so those keys are `null` and land
 * the folders last in both directions — matching the em-dash they show in those cells.
 */
export function decorateKnowledgeListItems({
  folders,
  bases,
  sortColumn,
  pinnedFolderIds,
  pinnedBaseIds,
  memberNameById,
}: DecorateKnowledgeListItemsParams): SortableResource<KnowledgeListItem>[] {
  const entries: SortableResource<KnowledgeListItem>[] = []

  for (const folder of folders) {
    entries.push({
      item: { kind: 'folder', folder },
      pinned: pinnedFolderIds.has(folder.id),
      name: folder.name,
      key:
        sortColumn === 'documents' || sortColumn === 'tokens' || sortColumn === 'connectors'
          ? null
          : sortColumn === 'created'
            ? new Date(folder.createdAt).getTime()
            : sortColumn === 'updated'
              ? new Date(folder.updatedAt).getTime()
              : sortColumn === 'owner'
                ? (memberNameById.get(folder.userId) ?? null)
                : folder.name,
    })
  }

  for (const base of bases) {
    entries.push({
      item: { kind: 'base', base },
      pinned: pinnedBaseIds.has(base.id),
      name: base.name,
      key:
        sortColumn === 'documents'
          ? (base.docCount ?? 0)
          : sortColumn === 'tokens'
            ? (base.tokenCount ?? 0)
            : sortColumn === 'connectors'
              ? (base.connectorTypes?.length ?? 0)
              : sortColumn === 'created'
                ? new Date(base.createdAt).getTime()
                : sortColumn === 'updated'
                  ? new Date(base.updatedAt).getTime()
                  : sortColumn === 'owner'
                    ? (memberNameById.get(base.userId) ?? null)
                    : base.name,
    })
  }

  return entries
}
