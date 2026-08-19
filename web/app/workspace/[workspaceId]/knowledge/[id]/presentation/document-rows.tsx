'use client'

import {
  Badge,
  cellIconNodeClass,
  chipContentGap,
  chipContentLabelClass,
  cn,
  FloatingTooltip,
  isTextClipped,
  Loader,
  Tooltip,
  useFloatingTooltip,
} from '@sim/emcn'
import { CircleAlert } from '@sim/emcn/icons'
import { format } from 'date-fns'
import type { DocumentData } from '@/lib/knowledge/types'
import { formatFileSize } from '@/lib/uploads/utils/file-utils'
import type { ResourceCell, ResourceRow } from '@/app/workspace/[workspaceId]/components'
import { FloatingOverflowText } from '@/app/workspace/[workspaceId]/components'
import { SearchHighlight } from '@/app/workspace/[workspaceId]/knowledge/[id]/components'
import { getDocumentIcon } from '@/app/workspace/[workspaceId]/knowledge/components'
import {
  type DocumentTagValue,
  getDocumentTagValues,
  type TagDefinitionShape,
} from '@/app/workspace/[workspaceId]/knowledge/detail/domain/tags'

const AnimatedLoader = ({ className }: { className?: string }) => (
  <Loader className={className} animate />
)

/** Status badge for a document row, including the failed-with-error variant. */
export function getDocumentStatusBadge(doc: DocumentData) {
  switch (doc.processingStatus) {
    case 'pending':
      return (
        <Badge variant='gray' size='sm'>
          Pending
        </Badge>
      )
    case 'processing':
      return (
        <Badge variant='purple' size='sm' icon={AnimatedLoader}>
          Processing
        </Badge>
      )
    case 'failed':
      return doc.processingError ? (
        <Badge variant='red' size='sm' icon={CircleAlert}>
          Failed
        </Badge>
      ) : (
        <Badge variant='red' size='sm'>
          Failed
        </Badge>
      )
    case 'completed':
      return doc.enabled ? (
        <Badge variant='green' size='sm'>
          Enabled
        </Badge>
      ) : (
        <Badge variant='gray' size='sm'>
          Disabled
        </Badge>
      )
    default:
      return (
        <Badge variant='gray' size='sm'>
          Unknown
        </Badge>
      )
  }
}

/**
 * Tags cell for the documents table. Shows the joined tag values inline and
 * reveals the full `name: value` breakdown only when the inline text is
 * actually clipped — an un-truncated cell already says everything the tooltip
 * would.
 */
export function DocumentTagsCell({ tags }: { tags: DocumentTagValue[] }) {
  const { state, handlers } = useFloatingTooltip(isTextClipped)

  return (
    <>
      <span
        role='presentation'
        className='block max-w-full truncate text-[var(--text-secondary)] text-caption'
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
        {...handlers}
      >
        {tags.map((tag) => tag.value).join(', ')}
      </span>
      <FloatingTooltip state={state} className='max-w-[240px]'>
        <div className='flex flex-col gap-0.5'>
          {tags.map((tag) => (
            <div key={tag.slot} className='truncate text-xs'>
              <span className='text-[var(--text-muted)]'>{tag.displayName}:</span> {tag.value}
            </div>
          ))}
        </div>
      </FloatingTooltip>
    </>
  )
}

interface BuildDocumentRowsParams {
  documents: DocumentData[]
  tagDefinitions: readonly TagDefinitionShape[]
  highlightQuery: string
}

/** Project the documents query into `Resource` rows (pure view mapping). */
export function buildDocumentRows({
  documents,
  tagDefinitions,
  highlightQuery,
}: BuildDocumentRowsParams): ResourceRow[] {
  return documents.map((doc) => {
    const DocIcon = getDocumentIcon(doc.mimeType, doc.filename)
    const tags = getDocumentTagValues(doc, tagDefinitions)

    const statusCell: ResourceCell =
      doc.processingStatus === 'failed' && doc.processingError
        ? {
            content: (
              <Tooltip.Root>
                <Tooltip.Trigger asChild>
                  <div className='cursor-help'>{getDocumentStatusBadge(doc)}</div>
                </Tooltip.Trigger>
                <Tooltip.Content side='top' className='max-w-xs'>
                  {doc.processingError}
                </Tooltip.Content>
              </Tooltip.Root>
            ),
          }
        : { content: getDocumentStatusBadge(doc) }

    const tagsCell: ResourceCell =
      tags.length === 0 ? { label: null } : { content: <DocumentTagsCell tags={tags} /> }

    return {
      id: doc.id,
      cells: {
        name: {
          content: (
            <span className={cn('flex min-w-0 items-center', chipContentGap)}>
              <span className={cellIconNodeClass}>
                <DocIcon className='size-[14px]' />
              </span>
              <FloatingOverflowText
                label={doc.filename}
                className={cn('block', chipContentLabelClass)}
              >
                <SearchHighlight text={doc.filename} searchQuery={highlightQuery} />
              </FloatingOverflowText>
            </span>
          ),
        },
        size: { label: formatFileSize(doc.fileSize) },
        tokens: {
          label:
            doc.processingStatus === 'completed'
              ? doc.tokenCount > 1000
                ? `${(doc.tokenCount / 1000).toFixed(1)}k`
                : doc.tokenCount.toLocaleString()
              : null,
        },
        chunks: {
          label: doc.processingStatus === 'completed' ? doc.chunkCount.toLocaleString() : null,
        },
        uploaded: {
          content: (
            <Tooltip.Root>
              <Tooltip.Trigger asChild>
                <span className='text-[var(--text-secondary)] text-sm'>
                  {format(new Date(doc.uploadedAt), 'MMM d')}
                </span>
              </Tooltip.Trigger>
              <Tooltip.Content side='top'>
                {format(new Date(doc.uploadedAt), 'MMM d, yyyy h:mm a')}
              </Tooltip.Content>
            </Tooltip.Root>
          ),
        },
        status: statusCell,
        tags: tagsCell,
      },
    }
  })
}
