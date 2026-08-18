'use client'

import { toast } from '@sim/emcn'
import { getErrorMessage } from '@sim/utils/errors'
import { parseFolderedRowId } from '@/app/workspace/[workspaceId]/components/folders'
import { useUpdateFolder } from '@/hooks/queries/folders'
import { useUpdateKnowledgeBase } from '@/hooks/queries/kb/knowledge'
import { useInlineRename } from '@/hooks/use-inline-rename'
import { KNOWLEDGE_FOLDER_RESOURCE_TYPE } from '../list/types'

/**
 * The knowledge list's two rename sessions, owning their own save mutations so neither
 * the row commands nor the breadcrumb chrome depend on the other through rename.
 *
 * `listRename` renames both kinds of row through one multiplexed session — the row id
 * already encodes which kind it is, so the table's `editing` cell wiring stays identical
 * for folders and knowledge bases. A duplicate sibling name is a 409 from the folder API;
 * surfacing it keeps the edit session open so the user can pick another name.
 *
 * `breadcrumbRename` renames the open folder from its breadcrumb crumb, where it has no
 * row to edit.
 */
export function useKnowledgeRename(workspaceId: string) {
  const { mutateAsync: updateFolder } = useUpdateFolder()
  const { mutateAsync: updateKnowledgeBase } = useUpdateKnowledgeBase(workspaceId)

  const saveFolderName = (folderId: string, name: string) =>
    updateFolder({
      workspaceId,
      resourceType: KNOWLEDGE_FOLDER_RESOURCE_TYPE,
      id: folderId,
      updates: { name },
    })

  const listRename = useInlineRename({
    onSave: async (rowId, name) => {
      const parsed = parseFolderedRowId(rowId)
      if (parsed.kind === 'folder') {
        try {
          return await saveFolderName(parsed.id, name)
        } catch (renameError) {
          toast.error(getErrorMessage(renameError, 'Failed to rename folder'))
          throw renameError
        }
      }
      return updateKnowledgeBase({ knowledgeBaseId: parsed.id, updates: { name } })
    },
  })

  const breadcrumbRename = useInlineRename({
    onSave: async (folderId, name) => {
      try {
        return await saveFolderName(folderId, name)
      } catch (renameError) {
        toast.error(getErrorMessage(renameError, 'Failed to rename folder'))
        throw renameError
      }
    },
  })

  return { listRename, breadcrumbRename }
}

export type KnowledgeRename = ReturnType<typeof useKnowledgeRename>
