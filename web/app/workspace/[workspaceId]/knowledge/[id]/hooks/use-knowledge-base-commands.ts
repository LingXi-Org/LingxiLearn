'use client'

import { useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { folderedResourceListHref } from '@/app/workspace/[workspaceId]/components/folders'
import { useRegisterGlobalCommands } from '@/app/workspace/[workspaceId]/providers/global-commands-provider'
import { useKnowledgeBasesList } from '@/hooks/kb/use-knowledge'
import { useDeleteKnowledgeBase, useUpdateKnowledgeBase } from '@/hooks/queries/kb/knowledge'
import { useInlineRename } from '@/hooks/use-inline-rename'

interface UseKnowledgeBaseCommandsParams {
  knowledgeBaseId: string
  workspaceId: string
  /** Current display name (drives the rename session and global command). */
  knowledgeBaseName: string
  onOpenAddDocuments: () => void
  onOpenTags: () => void
  onOpenDelete: () => void
}

/**
 * Central command layer for the knowledge base itself: inline rename, delete
 * (leaving the list cache and navigating back to the list), folder navigation,
 * and the page's global command registrations. UI receives plain callbacks.
 */
export function useKnowledgeBaseCommands({
  knowledgeBaseId,
  workspaceId,
  knowledgeBaseName,
  onOpenAddDocuments,
  onOpenTags,
  onOpenDelete,
}: UseKnowledgeBaseCommandsParams) {
  const router = useRouter()
  const { removeKnowledgeBase } = useKnowledgeBasesList(workspaceId, { enabled: false })
  const { mutate: deleteKnowledgeBaseMutation, isPending: isDeleting } =
    useDeleteKnowledgeBase(workspaceId)
  const { mutateAsync: updateKnowledgeBaseMutation } = useUpdateKnowledgeBase(workspaceId)

  const kbRename = useInlineRename({
    onSave: (kbId, name) =>
      updateKnowledgeBaseMutation({ knowledgeBaseId: kbId, updates: { name } }),
  })

  const deleteKnowledgeBase = useCallback(() => {
    deleteKnowledgeBaseMutation(
      { knowledgeBaseId },
      {
        onSuccess: () => {
          removeKnowledgeBase(knowledgeBaseId)
          router.push(`/workspace/${workspaceId}/knowledge`)
        },
      }
    )
  }, [deleteKnowledgeBaseMutation, knowledgeBaseId, removeKnowledgeBase, router, workspaceId])

  const navigateToFolder = useCallback(
    (folderId: string | null) => {
      router.push(folderedResourceListHref('knowledge_base', workspaceId, folderId))
    },
    [router, workspaceId]
  )

  useRegisterGlobalCommands(() => [
    { id: 'knowledge-base-new-documents', handler: onOpenAddDocuments },
    {
      id: 'knowledge-base-rename',
      handler: () => kbRename.startRename(knowledgeBaseId, knowledgeBaseName),
    },
    { id: 'knowledge-base-tags', handler: onOpenTags },
    { id: 'knowledge-base-delete', handler: onOpenDelete },
  ])

  return {
    kbRename,
    deleteKnowledgeBase,
    isDeleting,
    navigateToFolder,
  }
}

export type KnowledgeBaseCommands = ReturnType<typeof useKnowledgeBaseCommands>
