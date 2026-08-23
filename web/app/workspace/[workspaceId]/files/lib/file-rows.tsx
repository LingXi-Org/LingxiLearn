import { Folder } from '@/components/ui-kit'
import { getDocumentIcon } from '@/components/icons/document-icons'
import { formatFileSize } from '@/lib/uploads/utils/file-utils'
import { EMPTY_CELL_PLACEHOLDER, type ResourceRow } from '@/app/workspace/[workspaceId]/components'
import {
  folderRowId,
  type SortableResource,
} from '@/app/workspace/[workspaceId]/components/folders'
import { ownerCell } from '@/app/workspace/[workspaceId]/components/resource/components/owner-cell'
import { timeCell } from '@/app/workspace/[workspaceId]/components/resource/components/time-cell'
import { fileRowId } from '@/app/workspace/[workspaceId]/files/lib/file-row-ids'
import {
  type FileListEntry,
  FOLDER_TYPE_LABEL,
} from '@/app/workspace/[workspaceId]/files/lib/file-sort'
import { formatFileType } from '@/app/workspace/[workspaceId]/files/lib/file-type-label'
import type { WorkspaceMember } from '@/hooks/queries/workspace'

const FOLDER_ICON = <Folder className='size-[14px]' />

/** Lookups the row mapping needs beyond the entry itself. */
export interface FileRowContext {
  membersById: Map<string, WorkspaceMember>
  folderSizeMap: Map<string, number>
}

/**
 * Maps the sorted, merged folder+file entries to `ResourceRow`s — a pure function of its
 * inputs, so the table rendering stays a presentation concern and this mapping is testable.
 */
export function mapFileEntriesToRows(
  entries: SortableResource<FileListEntry>[],
  ctx: FileRowContext
): ResourceRow[] {
  return entries.map(({ item, pinned }): ResourceRow => {
    if (item.kind === 'folder') {
      const { folder } = item
      const totalSize = ctx.folderSizeMap.get(folder.id) ?? 0
      return {
        id: folderRowId(folder.id),
        cells: {
          name: {
            icon: FOLDER_ICON,
            label: folder.name,
            pinned,
          },
          size: {
            label:
              totalSize > 0
                ? formatFileSize(totalSize, { includeBytes: true })
                : EMPTY_CELL_PLACEHOLDER,
          },
          type: {
            icon: FOLDER_ICON,
            label: FOLDER_TYPE_LABEL,
          },
          created: timeCell(folder.createdAt),
          owner: ownerCell(folder.userId, ctx.membersById),
          updated: timeCell(folder.updatedAt),
        },
      }
    }

    const { file } = item
    const Icon = getDocumentIcon(file.type || '', file.name)
    return {
      id: fileRowId(file.id),
      cells: {
        name: {
          icon: <Icon className='size-[14px]' />,
          label: file.name,
          pinned,
        },
        size: {
          label: formatFileSize(file.size, { includeBytes: true }),
        },
        type: {
          icon: <Icon className='size-[14px]' />,
          label: formatFileType(file.type, file.name),
        },
        created: timeCell(file.uploadedAt),
        owner: ownerCell(file.uploadedBy, ctx.membersById),
        updated: timeCell(file.updatedAt),
      },
    }
  })
}
