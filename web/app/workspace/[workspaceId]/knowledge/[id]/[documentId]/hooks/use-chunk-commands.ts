'use client'

import { useCallback } from 'react'
import { createLogger } from '@/lib/logger'
import type { ChunkData } from '@/lib/knowledge/types'
import { resolveBulkTargets } from '@/app/workspace/[workspaceId]/knowledge/detail/domain/documents'
import { useBulkChunkOperation, useUpdateChunk } from '@/hooks/queries/kb/knowledge'

const logger = createLogger('ChunkCommands')

interface UseChunkCommandsParams {
  knowledgeBaseId: string
  documentId: string
  /** Chunks of the current view, for bulk target resolution. */
  displayChunks: ChunkData[]
  /** Cache update from the list controller (a no-op in search mode). */
  updateChunk: (chunkId: string, updates: Record<string, unknown>) => void
  selectedChunks: ReadonlySet<string>
  clearSelection: () => void
}

/**
 * Central command layer for chunks: toggle-enabled and the bulk
 * enable/disable/delete operations with their optimistic updates, error
 * handling, and selection cleanup. Single-chunk deletion flows through
 * `DeleteChunkModal` (it owns its confirm dialog and mutation).
 */
export function useChunkCommands({
  knowledgeBaseId,
  documentId,
  displayChunks,
  updateChunk,
  selectedChunks,
  clearSelection,
}: UseChunkCommandsParams) {
  const { mutate: updateChunkMutation } = useUpdateChunk()
  const { mutate: bulkChunkMutation, isPending: isBulkOperating } = useBulkChunkOperation()

  const toggleEnabled = useCallback(
    (chunkId: string) => {
      const chunk = displayChunks.find((c) => c.id === chunkId)
      if (!chunk) return

      const newEnabled = !chunk.enabled
      updateChunk(chunkId, { enabled: newEnabled })
      updateChunkMutation(
        { knowledgeBaseId, documentId, chunkId, enabled: newEnabled },
        { onError: () => updateChunk(chunkId, { enabled: chunk.enabled }) }
      )
    },
    [displayChunks, knowledgeBaseId, documentId, updateChunk, updateChunkMutation]
  )

  const performBulkOperation = useCallback(
    (operation: 'enable' | 'disable' | 'delete') => {
      const targets = resolveBulkTargets(displayChunks, selectedChunks, operation)
      if (targets.length === 0) return

      bulkChunkMutation(
        {
          knowledgeBaseId,
          documentId,
          operation,
          chunkIds: targets.map((chunk) => chunk.id),
        },
        {
          onSuccess: (result) => {
            if (operation !== 'delete' && result.errorCount === 0) {
              for (const chunk of targets) {
                updateChunk(chunk.id, { enabled: operation === 'enable' })
              }
            }
            logger.info(`Successfully ${operation}d ${result.successCount} chunks`)
            clearSelection()
          },
        }
      )
    },
    [
      displayChunks,
      selectedChunks,
      bulkChunkMutation,
      knowledgeBaseId,
      documentId,
      updateChunk,
      clearSelection,
    ]
  )

  const bulkEnable = useCallback(() => performBulkOperation('enable'), [performBulkOperation])
  const bulkDisable = useCallback(() => performBulkOperation('disable'), [performBulkOperation])
  const bulkDelete = useCallback(() => performBulkOperation('delete'), [performBulkOperation])

  return {
    toggleEnabled,
    bulkEnable,
    bulkDisable,
    bulkDelete,
    isBulkOperating,
  }
}

export type ChunkCommands = ReturnType<typeof useChunkCommands>
