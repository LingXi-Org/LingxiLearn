'use client'

import { useCallback } from 'react'
import { toast } from '@sim/emcn'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@sim/utils/errors'
import { useRouter } from 'next/navigation'
import type { KnowledgeBaseData } from '@/lib/knowledge/types'
import { parseMoveOptionValue } from '@/app/workspace/[workspaceId]/components/folders'
import { useDeleteKnowledgeBase, useUpdateKnowledgeBase } from '@/hooks/queries/kb/knowledge'
import type { usePinItem, useUnpinItem } from '@/hooks/queries/pinned-items'

const logger = createLogger('Knowledge')

export interface UseKnowledgeBaseCommandsOptions {
  workspaceId: string
  /** Latest-list lookup, from `useKnowledgeListData`. */
  findKnowledgeBase: (id: string) => KnowledgeBaseData | undefined
  pinnedBaseIds: ReadonlySet<string>
  pinItem: ReturnType<typeof usePinItem>
  unpinItem: ReturnType<typeof useUnpinItem>
  /** Closes the row context menu after a one-shot command. */
  closeMenu: () => void
}

/**
 * Every mutation a knowledge base row can trigger, in one place, each taking the base it
 * acts on as an argument. Permission gating (`canEdit`) is applied where the commands are
 * exposed to the UI rather than repeated inside each handler.
 */
export function useKnowledgeBaseCommands({
  workspaceId,
  findKnowledgeBase,
  pinnedBaseIds,
  pinItem,
  unpinItem,
  closeMenu,
}: UseKnowledgeBaseCommandsOptions) {
  const router = useRouter()
  const { mutateAsync: updateKnowledgeBaseMutation } = useUpdateKnowledgeBase(workspaceId)
  const { mutateAsync: deleteKnowledgeBaseMutation } = useDeleteKnowledgeBase(workspaceId)

  const updateBase = useCallback(
    async (
      knowledgeBaseId: string,
      updates: Partial<Pick<KnowledgeBaseData, 'name' | 'description'>>
    ) => {
      await updateKnowledgeBaseMutation({ knowledgeBaseId, updates })
      logger.info(`Knowledge base updated: ${knowledgeBaseId}`)
    },
    [updateKnowledgeBaseMutation]
  )

  const deleteBase = useCallback(
    async (knowledgeBaseId: string) => {
      await deleteKnowledgeBaseMutation({ knowledgeBaseId })
      logger.info(`Knowledge base deleted: ${knowledgeBaseId}`)
    },
    [deleteKnowledgeBaseMutation]
  )

  /** Shared by the "Move to" submenu and by dropping a base row onto a folder. */
  const moveBaseTo = useCallback(
    async (knowledgeBaseId: string, folderId: string | null) => {
      try {
        await updateKnowledgeBaseMutation({ knowledgeBaseId, updates: { folderId } })
      } catch (moveError) {
        logger.error('Failed to move knowledge base', moveError)
        toast.error(getErrorMessage(moveError, 'Failed to move knowledge base'))
      }
    },
    [updateKnowledgeBaseMutation]
  )

  const moveBaseFromMenu = useCallback(
    async (base: KnowledgeBaseData, optionValue: string) => {
      const folderId = parseMoveOptionValue(optionValue)
      // Re-read placement from the live list: `base` is a snapshot from when the menu
      // opened, and a refetch since then would make the no-op check wrong.
      const current = findKnowledgeBase(base.id) ?? base
      if ((current.folderId ?? null) !== folderId) await moveBaseTo(base.id, folderId)
      closeMenu()
    },
    [findKnowledgeBase, moveBaseTo, closeMenu]
  )

  const toggleBasePin = useCallback(
    (base: KnowledgeBaseData) => {
      const mutation = pinnedBaseIds.has(base.id) ? unpinItem : pinItem
      mutation.mutate({ workspaceId, resourceType: 'knowledge_base', resourceId: base.id })
      closeMenu()
      // eslint-disable-next-line react-hooks/exhaustive-deps -- mutation objects are unstable; mutate is stable in v5
    },
    [workspaceId, pinnedBaseIds, pinItem, unpinItem, closeMenu]
  )

  const openBase = useCallback(
    (base: KnowledgeBaseData) => {
      const urlParams = new URLSearchParams({ kbName: base.name })
      router.push(`/workspace/${workspaceId}/knowledge/${base.id}?${urlParams.toString()}`)
    },
    [router, workspaceId]
  )

  const openBaseInNewTab = useCallback(
    (base: KnowledgeBaseData) => {
      const urlParams = new URLSearchParams({ kbName: base.name })
      window.open(
        `/workspace/${workspaceId}/knowledge/${base.id}?${urlParams.toString()}`,
        '_blank'
      )
    },
    [workspaceId]
  )

  const copyBaseId = useCallback((base: KnowledgeBaseData) => {
    navigator.clipboard.writeText(base.id)
  }, [])

  return {
    updateBase,
    deleteBase,
    moveBaseTo,
    moveBaseFromMenu,
    toggleBasePin,
    openBase,
    openBaseInNewTab,
    copyBaseId,
  }
}

export type KnowledgeBaseCommands = ReturnType<typeof useKnowledgeBaseCommands>
