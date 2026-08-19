'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { createLogger } from '@sim/logger'
import { useQueryState, useQueryStates } from 'nuqs'
import type { DocumentSortField, SortOrder } from '@/lib/knowledge/documents/types'
import { SEARCH_DEBOUNCE_MS } from '@/lib/url-state'
import {
  documentFiltersParsers,
  documentFiltersUrlKeys,
  kbDocumentSortParams,
  pageParam,
  pageUrlKeys,
} from '@/app/workspace/[workspaceId]/knowledge/[id]/search-params'
import {
  countSelectedByEnabled,
  isEntirePageSelected,
} from '@/app/workspace/[workspaceId]/knowledge/detail/domain/documents'
import type { ProjectedTagFilter } from '@/app/workspace/[workspaceId]/knowledge/detail/domain/tags'
import { useKnowledgeBaseDocuments } from '@/hooks/kb/use-knowledge'
import { useUpdateDocument } from '@/hooks/queries/kb/knowledge'
import { useDebounce } from '@/hooks/use-debounce'
import { useDebouncedSearchSetter } from '@/hooks/use-debounced-search-setter'
import { useUrlSort } from '@/hooks/use-url-sort'

const logger = createLogger('KnowledgeBaseDocumentList')

export const DOCUMENTS_PER_PAGE = 50

/** A document is abandoned as failed after processing for this long. */
const DEAD_PROCESS_THRESHOLD_MS = 600 * 1000

export type DocumentEnabledFilter = 'all' | 'enabled' | 'disabled'

interface UseDocumentListControllerParams {
  knowledgeBaseId: string
  /** Projected tag filters from the tag-filter controller. */
  tagFilters?: ProjectedTagFilter[]
  /** Suspend polling while the knowledge base itself is being deleted. */
  suspendPolling?: boolean
}

/**
 * Owns the document list of a knowledge base: URL view state (page, search,
 * sort, enabled filter), the paged documents query with its polling policy,
 * the row selection, and the dead-process reconciler. Owns nothing about
 * tags-as-data, mutations, or dialog lifecycle.
 */
export function useDocumentListController({
  knowledgeBaseId,
  tagFilters,
  suspendPolling = false,
}: UseDocumentListControllerParams) {
  const [currentPage, setCurrentPage] = useQueryState(pageParam.key, {
    ...pageParam.parser,
    ...pageUrlKeys,
  })

  const [{ q: searchQuery, enabled: enabledFilter }, setDocumentFilters] = useQueryStates(
    documentFiltersParsers,
    documentFiltersUrlKeys
  )

  /**
   * The input is controlled directly by the instant nuqs value; only the URL
   * write is debounced. The document query below reads a debounced value so it
   * doesn't refetch on every keystroke. Changing the search resets pagination.
   */
  const handleSearchChange = useDebouncedSearchSetter((value, options) => {
    setDocumentFilters({ q: value }, options)
    setCurrentPage(1)
  })
  const debouncedSearchQuery = useDebounce(searchQuery, SEARCH_DEBOUNCE_MS)
  /** Raw URL value drives the input; matching/highlighting always sees it trimmed. */
  const highlightQuery = searchQuery.trim()

  const {
    sort: sortColumn,
    dir: sortDirection,
    activeSort,
    onSort: onSortColumn,
    onClear: onClearSort,
  } = useUrlSort(kbDocumentSortParams, documentFiltersUrlKeys)

  const [selectedDocuments, setSelectedDocuments] = useState<Set<string>>(() => new Set())
  const [isSelectAllMode, setIsSelectAllMode] = useState(false)

  const clearSelection = useCallback(() => {
    setSelectedDocuments(new Set())
    setIsSelectAllMode(false)
  }, [])

  const setEnabledFilter = useCallback(
    (value: DocumentEnabledFilter) => {
      setDocumentFilters({ enabled: value })
      setCurrentPage(1)
      clearSelection()
    },
    [setDocumentFilters, setCurrentPage, clearSelection]
  )

  const {
    documents,
    pagination,
    isPlaceholderData: isPlaceholderDocuments,
    error: documentsError,
    hasProcessingDocuments,
    updateDocument,
    refreshDocuments,
  } = useKnowledgeBaseDocuments(knowledgeBaseId, {
    search: debouncedSearchQuery.trim() || undefined,
    limit: DOCUMENTS_PER_PAGE,
    offset: (currentPage - 1) * DOCUMENTS_PER_PAGE,
    sortBy: sortColumn as DocumentSortField,
    sortOrder: sortDirection as SortOrder,
    refetchInterval: (data) => {
      if (suspendPolling) return false
      const hasPending = data?.documents?.some(
        (doc) => doc.processingStatus === 'pending' || doc.processingStatus === 'processing'
      )
      return hasPending ? 3000 : false
    },
    enabledFilter,
    tagFilters: tagFilters && tagFilters.length > 0 ? tagFilters : undefined,
  })

  const { mutate: updateDocumentMutation } = useUpdateDocument()

  /**
   * Reconciles documents whose processing run died without reporting back:
   * anything still `processing` past the threshold is marked failed so the row
   * stops polling forever.
   */
  useEffect(() => {
    if (!hasProcessingDocuments) return

    const now = Date.now()
    const staleDocuments = documents.filter((doc) => {
      if (doc.processingStatus !== 'processing' || !doc.processingStartedAt) return false
      return now - new Date(doc.processingStartedAt).getTime() > DEAD_PROCESS_THRESHOLD_MS
    })

    if (staleDocuments.length === 0) return
    logger.warn(`Found ${staleDocuments.length} documents with dead processes`)

    for (const doc of staleDocuments) {
      updateDocumentMutation(
        {
          knowledgeBaseId,
          documentId: doc.id,
          updates: { markFailedDueToTimeout: true },
        },
        {
          onSuccess: () => {
            logger.info(`Successfully marked dead process as failed for document: ${doc.filename}`)
          },
        }
      )
    }
  }, [hasProcessingDocuments, documents, knowledgeBaseId, updateDocumentMutation])

  const handleSelectDocument = useCallback((docId: string, checked: boolean) => {
    setSelectedDocuments((prev) => {
      const next = new Set(prev)
      if (checked) {
        next.add(docId)
      } else {
        next.delete(docId)
      }
      return next
    })
  }, [])

  const handleSelectAll = useCallback(
    (checked: boolean) => {
      if (checked) {
        setSelectedDocuments(new Set(documents.map((doc) => doc.id)))
      } else {
        clearSelection()
      }
    },
    [documents, clearSelection]
  )

  /** Right-clicking an unselected row re-targets the selection at that row. */
  const selectOnly = useCallback((docId: string) => {
    setSelectedDocuments(new Set([docId]))
  }, [])

  const removeFromSelection = useCallback((docId: string) => {
    setSelectedDocuments((prev) => {
      if (!prev.has(docId)) return prev
      const next = new Set(prev)
      next.delete(docId)
      return next
    })
  }, [])

  const isAllSelected = isEntirePageSelected(documents.length, selectedDocuments)

  const selectedCounts = useMemo(() => {
    const withinPage = countSelectedByEnabled(documents, selectedDocuments)
    if (!isSelectAllMode) return withinPage
    return {
      enabled: enabledFilter === 'disabled' ? 0 : pagination.total,
      disabled: enabledFilter === 'enabled' ? 0 : pagination.total,
    }
  }, [documents, selectedDocuments, isSelectAllMode, enabledFilter, pagination.total])

  const totalPages = Math.ceil(pagination.total / pagination.limit)

  return {
    // Query results
    documents,
    pagination,
    totalPages,
    isPlaceholderDocuments,
    documentsError,
    updateDocument,
    refreshDocuments,
    // URL view state
    currentPage,
    setCurrentPage,
    searchQuery,
    handleSearchChange,
    highlightQuery,
    enabledFilter,
    setEnabledFilter,
    sortColumn,
    sortDirection,
    activeSort,
    onSortColumn,
    onClearSort,
    // Selection
    selectedDocuments,
    isSelectAllMode,
    setIsSelectAllMode,
    clearSelection,
    handleSelectDocument,
    handleSelectAll,
    selectOnly,
    removeFromSelection,
    isAllSelected,
    selectedCounts,
  }
}

export type DocumentListController = ReturnType<typeof useDocumentListController>
