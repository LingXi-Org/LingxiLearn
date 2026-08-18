'use client'

import { useCallback, useRef, useState } from 'react'
import type { KnowledgeBaseData } from '@/lib/knowledge/types'
import { parseFolderedRowId } from '@/app/workspace/[workspaceId]/components/folders'
import { useContextMenu } from '@/app/workspace/[workspaceId]/components/hooks'
import type { KnowledgeFolder } from '../list/types'

export interface UseKnowledgeListSelectionOptions {
  /** Latest-list lookups, from `useKnowledgeListData`. */
  findKnowledgeBase: (id: string) => KnowledgeBaseData | undefined
  findFolder: (id: string) => KnowledgeFolder | undefined
}

/**
 * Which row the knowledge list is acting on, and the three context menus that hang off it:
 * the empty-area menu (new base / new folder), the knowledge-base row menu, and the folder
 * row menu. Dialog state deliberately lives elsewhere (see `useKnowledgeDialogs`) — a
 * menu's "active row" outlives any single dialog.
 */
export function useKnowledgeListSelection({
  findKnowledgeBase,
  findFolder,
}: UseKnowledgeListSelectionOptions) {
  const [activeBase, setActiveBase] = useState<KnowledgeBaseData | null>(null)
  const [activeFolder, setActiveFolder] = useState<KnowledgeFolder | null>(null)

  const listMenu = useContextMenu()
  const baseMenu = useContextMenu()
  const folderMenu = useContextMenu()

  const baseMenuOpenRef = useRef(baseMenu.isOpen)
  baseMenuOpenRef.current = baseMenu.isOpen
  const folderMenuOpenRef = useRef(folderMenu.isOpen)
  folderMenuOpenRef.current = folderMenu.isOpen

  /**
   * A row click while a row menu is open is the click that dismisses the menu — letting it
   * also navigate reads as a double action.
   */
  const isRowInteractionBlocked = useCallback(
    () => baseMenuOpenRef.current || folderMenuOpenRef.current,
    []
  )

  /** Right-click on the empty list area, ignoring rows and interactive elements. */
  const handleContentContextMenu = useCallback(
    (e: React.MouseEvent) => {
      const target = e.target as HTMLElement
      if (
        target.closest('[data-resource-row]') ||
        target.closest('button, input, a, [role="button"]')
      ) {
        return
      }
      listMenu.handleContextMenu(e)
    },
    [listMenu.handleContextMenu]
  )

  /** Right-click on a row: resolves the multiplexed row id and opens the matching menu. */
  const handleRowContextMenu = useCallback(
    (e: React.MouseEvent, rowId: string) => {
      const parsed = parseFolderedRowId(rowId)
      if (parsed.kind === 'folder') {
        const folder = findFolder(parsed.id)
        if (!folder) return
        setActiveFolder(folder)
        folderMenu.handleContextMenu(e)
        return
      }

      setActiveBase(findKnowledgeBase(parsed.id) ?? null)
      baseMenu.handleContextMenu(e)
    },
    [findFolder, findKnowledgeBase, folderMenu.handleContextMenu, baseMenu.handleContextMenu]
  )

  return {
    activeBase,
    setActiveBase,
    activeFolder,
    setActiveFolder,
    listMenu,
    baseMenu,
    folderMenu,
    isRowInteractionBlocked,
    handleContentContextMenu,
    handleRowContextMenu,
  }
}

export type KnowledgeListSelection = ReturnType<typeof useKnowledgeListSelection>
