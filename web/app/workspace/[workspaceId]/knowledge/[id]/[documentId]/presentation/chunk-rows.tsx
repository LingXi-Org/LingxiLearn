'use client'

import { Badge } from '@sim/emcn'
import { FileText } from '@sim/emcn/icons'
import type { ChunkData } from '@/lib/knowledge/types'
import { formatTokenCount } from '@/lib/tokenization'
import type { ResourceRow } from '@/app/workspace/[workspaceId]/components'
import { EMPTY_CELL_PLACEHOLDER } from '@/app/workspace/[workspaceId]/components'
import { truncateContent } from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/domain/chunk-view'
import { SearchHighlight } from '@/app/workspace/[workspaceId]/knowledge/[id]/components'

/**
 * Placeholder row while the document is not yet `completed` — the chunks table
 * has no content to show, so a single explanatory row stands in.
 */
export function buildProcessingPlaceholderRow(processingStatus: string | undefined): ResourceRow[] {
  return [
    {
      id: 'processing-status',
      cells: {
        content: {
          content: (
            <div className='flex items-center gap-2'>
              <FileText className='size-5 flex-shrink-0 text-[var(--text-muted)]' />
              <span className='text-[var(--text-muted)] text-sm italic'>
                {processingStatus === 'pending' && 'Document processing pending...'}
                {processingStatus === 'processing' && 'Document processing in progress...'}
                {processingStatus === 'failed' && 'Document processing failed'}
                {!processingStatus && 'Document not ready'}
              </span>
            </div>
          ),
        },
        index: { label: EMPTY_CELL_PLACEHOLDER },
        tokens: { label: EMPTY_CELL_PLACEHOLDER },
        status: { label: EMPTY_CELL_PLACEHOLDER },
      },
    },
  ]
}

interface BuildChunkRowsParams {
  chunks: ChunkData[]
  searchQuery: string
}

/** Project the current chunk page into `Resource` rows (pure view mapping). */
export function buildChunkRows({ chunks, searchQuery }: BuildChunkRowsParams): ResourceRow[] {
  return chunks.map((chunk) => {
    const previewContent = truncateContent(chunk.content, 150, searchQuery)

    return {
      id: chunk.id,
      cells: {
        content: {
          content: (
            <span className='block truncate text-[var(--text-primary)] text-sm'>
              <SearchHighlight text={previewContent} searchQuery={searchQuery} />
            </span>
          ),
        },
        index: {
          content: (
            <span className='font-mono text-[var(--text-primary)] text-sm'>{chunk.chunkIndex}</span>
          ),
        },
        tokens: {
          label: formatTokenCount(chunk.tokenCount),
        },
        status: {
          content: (
            <Badge variant={chunk.enabled ? 'green' : 'gray'} size='sm'>
              {chunk.enabled ? 'Enabled' : 'Disabled'}
            </Badge>
          ),
        },
      },
    }
  })
}
