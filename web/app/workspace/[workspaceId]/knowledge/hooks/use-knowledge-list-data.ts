'use client'

import { useCallback, useEffect, useMemo, useRef } from 'react'
import { createLogger } from '@/lib/logger'
import type { KnowledgeBaseData } from '@/lib/knowledge/types'
import {
  buildDescendantIndex,
  useFolderNavigation,
} from '@/app/workspace/[workspaceId]/components/folders'
import { useKnowledgeBasesList } from '@/hooks/kb/use-knowledge'
import { usePinItem, usePinnedIds, useUnpinItem } from '@/hooks/queries/pinned-items'
import { useWorkspaceMembersQuery, type WorkspaceMember } from '@/hooks/queries/workspace'
import type { KnowledgeFolder } from '../list/types'
import { KNOWLEDGE_FOLDER_RESOURCE_TYPE } from '../list/types'

const logger = createLogger('Knowledge')

/**
 * The knowledge list's domain query layer: knowledge bases, the `knowledge_base` folder
 * tree, workspace members, and pin state — plus the derived indexes and ref-backed
 * lookups the event handlers (row click, context menus, drag-drop) need to resolve
 * against the LATEST list without re-binding on every render.
 */
export function useKnowledgeListData(workspaceId: string) {
  const { knowledgeBases, error } = useKnowledgeBasesList(workspaceId)

  useEffect(() => {
    if (error) logger.error('Failed to load knowledge bases:', error)
  }, [error])

  const { data: members } = useWorkspaceMembersQuery(workspaceId)
  /**
   * Indexed once: `ownerCell` resolves a member per row, so passing the raw array makes the
   * owner column O(rows x members) on every rebuild. Tables already does this.
   */
  const membersById = useMemo(() => {
    const byId = new Map<string, WorkspaceMember>()
    for (const member of members ?? []) byId.set(member.userId, member)
    return byId
  }, [members])
  /** Owner-column sort keys read display names only. */
  const memberNameById = useMemo(() => {
    const byId = new Map<string, string>()
    for (const member of members ?? []) byId.set(member.userId, member.name)
    return byId
  }, [members])

  /**
   * Two pin lookups: a folder pins under `resourceType: 'folder'`, which is a different pin
   * namespace from the knowledge bases it contains, so one set cannot answer for both.
   */
  const pinnedBaseIds = usePinnedIds(workspaceId, 'knowledge_base')
  const pinnedFolderIds = usePinnedIds(workspaceId, 'folder')
  const pinItem = usePinItem()
  const unpinItem = useUnpinItem()

  const folderNavigation = useFolderNavigation({
    resourceType: KNOWLEDGE_FOLDER_RESOURCE_TYPE,
    workspaceId,
  })
  const { folders } = folderNavigation

  const descendantsByFolderId = useMemo(() => buildDescendantIndex(folders), [folders])

  const knowledgeBasesRef = useRef(knowledgeBases)
  knowledgeBasesRef.current = knowledgeBases
  const foldersRef = useRef(folders)
  foldersRef.current = folders
  const currentFolderIdRef = useRef(folderNavigation.currentFolderId)
  currentFolderIdRef.current = folderNavigation.currentFolderId

  /** Latest-list lookup for handlers that fire between renders. */
  const findKnowledgeBase = useCallback(
    (id: string): KnowledgeBaseData | undefined =>
      knowledgeBasesRef.current.find((kb) => kb.id === id),
    []
  )
  const findFolder = useCallback(
    (id: string): KnowledgeFolder | undefined =>
      foldersRef.current.find((folder) => folder.id === id),
    []
  )

  return {
    knowledgeBases,
    findKnowledgeBase,
    findFolder,
    members,
    membersById,
    memberNameById,
    pinnedBaseIds,
    pinnedFolderIds,
    pinItem,
    unpinItem,
    folderNavigation,
    folders,
    foldersRef,
    currentFolderIdRef,
    descendantsByFolderId,
  }
}

export type KnowledgeListData = ReturnType<typeof useKnowledgeListData>
