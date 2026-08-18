import type { Dispatch, SetStateAction } from 'react'
import { Database } from '@sim/emcn/icons'
import type { ResourceColumn, ResourceRow } from '@/app/workspace/[workspaceId]/components'
import { EMPTY_CELL_PLACEHOLDER } from '@/app/workspace/[workspaceId]/components'
import type { SortableResource } from '@/app/workspace/[workspaceId]/components/folders'
import { folderRow } from '@/app/workspace/[workspaceId]/components/folders'
import { ownerCell } from '@/app/workspace/[workspaceId]/components/resource/components/owner-cell'
import { timeCell } from '@/app/workspace/[workspaceId]/components/resource/components/time-cell'
import type { WorkspaceMember } from '@/hooks/queries/workspace'
import type { KnowledgeListItem } from '../list/types'
import { connectorCell } from './connector-cell'

export const KNOWLEDGE_LIST_COLUMNS: ResourceColumn[] = [
  { id: 'name', header: 'Name' },
  { id: 'documents', header: 'Documents', widthMultiplier: 0.6 },
  { id: 'tokens', header: 'Tokens', widthMultiplier: 0.6 },
  { id: 'connectors', header: 'Connectors', widthMultiplier: 0.7 },
  { id: 'created', header: 'Created' },
  { id: 'owner', header: 'Owner' },
  { id: 'updated', header: 'Last Updated' },
]

const KNOWLEDGE_BASE_ICON = <Database className='size-[14px]' />

/**
 * Projects the sorted list entries into `ResourceRow`s. Folders render em-dashes in the
 * resource-specific columns they have no value for; bases map their document/token counts
 * and connector types into cells. The connector registry is consulted ONLY inside
 * {@link connectorCell} — the row mapper itself stays domain data in, presentation out.
 */
export function buildKnowledgeRows(
  entries: SortableResource<KnowledgeListItem>[],
  membersById: ReadonlyMap<string, WorkspaceMember>
): ResourceRow[] {
  return entries.map(({ item, pinned }): ResourceRow => {
    if (item.kind === 'folder') {
      return folderRow(item.folder, {
        pinned,
        cells: {
          documents: { label: EMPTY_CELL_PLACEHOLDER },
          tokens: { label: EMPTY_CELL_PLACEHOLDER },
          connectors: { label: EMPTY_CELL_PLACEHOLDER },
          created: timeCell(item.folder.createdAt),
          owner: ownerCell(item.folder.userId, membersById),
          updated: timeCell(item.folder.updatedAt),
        },
      })
    }

    const { base } = item
    return {
      id: base.id,
      cells: {
        name: {
          icon: KNOWLEDGE_BASE_ICON,
          label: base.name,
          pinned,
        },
        documents: {
          label: String(base.docCount || 0),
        },
        tokens: {
          label: base.tokenCount ? base.tokenCount.toLocaleString() : '0',
        },
        connectors: connectorCell(base.connectorTypes),
        created: timeCell(base.createdAt),
        owner: ownerCell(base.userId, membersById),
        updated: timeCell(base.updatedAt),
      },
    }
  })
}

/** The subset of an inline-rename session the row overlay reads. */
export interface RenameOverlayState {
  editingId: string | null
  editValue: string
  setEditValue: Dispatch<SetStateAction<string>>
  submitRename: () => void | Promise<void>
  cancelRename: () => void
  isSaving: boolean
}

/**
 * Layers an in-flight rename over the built rows rather than folding it into the builder,
 * so a keystroke in the rename field rebuilds one cell instead of every row's cells.
 */
export function applyRenameOverlay(rows: ResourceRow[], rename: RenameOverlayState): ResourceRow[] {
  if (!rename.editingId) return rows
  return rows.map((row) => {
    if (row.id !== rename.editingId) return row
    return {
      ...row,
      cells: {
        ...row.cells,
        name: {
          ...row.cells.name,
          editing: {
            value: rename.editValue,
            onChange: rename.setEditValue,
            onSubmit: rename.submitRename,
            onCancel: rename.cancelRename,
            disabled: rename.isSaving,
          },
        },
      },
    }
  })
}
