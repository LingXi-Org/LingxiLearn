'use client'

import { useCallback, useMemo, useState } from 'react'
import { useQueryStates } from 'nuqs'
import type { ChunkData } from '@/lib/knowledge/types'
import {
  getSearchPageResults,
  getSearchPageView,
} from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/domain/chunk-view'
import {
  documentChunkSortParams,
  documentParsers,
  documentUrlKeys,
} from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/search-params'
import {
  countSelectedByEnabled,
  isEntirePageSelected,
} from '@/app/workspace/[workspaceId]/knowledge/detail/domain/documents'
import { useDocumentChunks } from '@/hooks/kb/use-knowledge'
import { useDocumentChunkSearchQuery } from '@/hooks/queries/kb/knowledge'
import { useDebounce } from '@/hooks/use-debounce'
import { useDebouncedSearchSetter } from '@/hooks/use-debounced-search-setter'
import { useUrlSort } from '@/hooks/use-url-sort'

/**
 * Debounce window for chunk-search URL writes and the query feed; the input
 * itself stays instant. Intentionally shorter than the shared
 * `SEARCH_DEBOUNCE_MS` (300) to match the chunk search's snappier feel.
 */
const CHUNK_SEARCH_DEBOUNCE_MS = 200 as const

/** Client-side page size for the chunk search result set. */
const SEARCH_PAGE_SIZE = 50

export type ChunkSortColumn = 'chunkIndex' | 'tokenCount' | 'enabled'

/** Map the sort-menu column id to the chunk query's sort field. */
function resolveChunkSortField(column: string | undefined): ChunkSortColumn | undefined {
  switch (column) {
    case 'tokens':
      return 'tokenCount'
    case 'status':
      return 'enabled'
    case 'index':
      return 'chunkIndex'
    default:
      return undefined
  }
}

interface UseChunkListControllerParams {
  knowledgeBaseId: string
  documentId: string
}

/**
 * Owns the document detail's chunk list: URL view state (page, search,
 * enabled filter, sort), the browse query plus the separate chunk-search
 * query, the search/browse view projection, and the row selection. The inline
 * chunk editor's state lives in `useChunkEditorController`.
 */
export function useChunkListController({
  knowledgeBaseId,
  documentId,
}: UseChunkListControllerParams) {
  const [
    {
      page: currentPageFromURL,
      chunk: chunkFromURL,
      search: searchQuery,
      enabled: enabledFilterParam,
    },
    setDocumentParams,
  ] = useQueryStates(documentParsers, documentUrlKeys)

  /**
   * The input is controlled directly by the instant nuqs value; only the URL
   * write is debounced. The chunk search query below reads a debounced value so
   * it doesn't refetch on every keystroke. Changing the search resets `page` in
   * the same write — a search started from a later page must land on the first
   * page of matches, and a shared search link must open there too.
   */
  const handleSearchChange = useDebouncedSearchSetter(
    (value, options) => void setDocumentParams({ search: value, page: null }, options),
    { debounceMs: CHUNK_SEARCH_DEBOUNCE_MS }
  )
  /** Raw URL value drives the input; the chunk search query always sees it trimmed. */
  const debouncedSearchQuery = useDebounce(searchQuery, CHUNK_SEARCH_DEBOUNCE_MS).trim()

  const {
    activeSort,
    onSort: onSortColumn,
    onClear: onClearSort,
  } = useUrlSort(documentChunkSortParams, documentUrlKeys)

  /** Multi-select UI view of the scalar `enabled` param (`all` ↔ nothing selected). */
  const enabledFilter = useMemo<string[]>(
    () => (enabledFilterParam === 'all' ? [] : [enabledFilterParam]),
    [enabledFilterParam]
  )

  const [selectedChunks, setSelectedChunks] = useState<Set<string>>(() => new Set())

  const clearSelection = useCallback(() => {
    setSelectedChunks(new Set())
  }, [])

  /**
   * Collapses the dropdown's multi-select values to the scalar param (one value
   * filters; none or both mean `all`) and resets `page` in the same write so a
   * filter change always lands on the first page.
   */
  const setEnabledFilter = useCallback(
    (values: string[]) => {
      void setDocumentParams({
        enabled: values.length === 1 ? (values[0] as 'enabled' | 'disabled') : null,
        page: null,
      })
      clearSelection()
    },
    [setDocumentParams, clearSelection]
  )

  const {
    chunks: initialChunks,
    currentPage: initialPage,
    totalPages: initialTotalPages,
    goToPage: initialGoToPage,
    error: initialError,
    updateChunk: initialUpdateChunk,
  } = useDocumentChunks(
    knowledgeBaseId,
    documentId,
    currentPageFromURL,
    '',
    enabledFilterParam,
    resolveChunkSortField(activeSort?.column),
    activeSort?.direction
  )

  const { data: searchResults = [], error: searchQueryError } = useDocumentChunkSearchQuery(
    {
      knowledgeBaseId,
      documentId,
      search: debouncedSearchQuery,
    },
    {
      enabled: Boolean(debouncedSearchQuery),
    }
  )

  const searchError = searchQueryError instanceof Error ? searchQueryError.message : null

  const isSearching = debouncedSearchQuery.length > 0
  const showingSearch = isSearching && searchQuery.trim().length > 0 && searchResults.length > 0

  const searchView = getSearchPageView(searchResults.length, SEARCH_PAGE_SIZE, currentPageFromURL)

  /**
   * Stable chunk list for the current view. Memoized so the many downstream
   * `useMemo`/`useCallback` hooks that depend on it don't recompute every render
   * (search pagination `.slice()` otherwise yields a fresh array each time).
   */
  const displayChunks = useMemo<ChunkData[]>(() => {
    if (showingSearch) {
      return getSearchPageResults(searchResults, searchView.currentPage, SEARCH_PAGE_SIZE)
    }
    return initialChunks ?? []
  }, [showingSearch, searchResults, searchView.currentPage, initialChunks])

  const currentPage = showingSearch ? searchView.currentPage : initialPage
  const totalPages = showingSearch ? searchView.totalPages : initialTotalPages

  const goToPage = useCallback(
    async (page: number) => {
      await setDocumentParams({ page })

      if (showingSearch) {
        return
      }
      return initialGoToPage(page)
    },
    [showingSearch, initialGoToPage, setDocumentParams]
  )

  /** Chunk cache updates only apply in browse mode; search results are read-only. */
  const updateChunk = showingSearch
    ? (_id: string, _updates: Record<string, unknown>) => {}
    : initialUpdateChunk

  const handleSelectChunk = useCallback((chunkId: string, checked: boolean) => {
    setSelectedChunks((prev) => {
      const next = new Set(prev)
      if (checked) {
        next.add(chunkId)
      } else {
        next.delete(chunkId)
      }
      return next
    })
  }, [])

  const handleSelectAll = useCallback(
    (checked: boolean) => {
      if (checked) {
        setSelectedChunks(new Set(displayChunks.map((chunk) => chunk.id)))
      } else {
        clearSelection()
      }
    },
    [displayChunks, clearSelection]
  )

  /** Right-clicking an unselected row re-targets the selection at that row. */
  const selectOnly = useCallback((chunkId: string) => {
    setSelectedChunks(new Set([chunkId]))
  }, [])

  const removeFromSelection = useCallback((chunkId: string) => {
    setSelectedChunks((prev) => {
      if (!prev.has(chunkId)) return prev
      const next = new Set(prev)
      next.delete(chunkId)
      return next
    })
  }, [])

  const selectedCounts = useMemo(
    () => countSelectedByEnabled(displayChunks, selectedChunks),
    [displayChunks, selectedChunks]
  )

  const isAllSelected = isEntirePageSelected(displayChunks.length, selectedChunks)

  return {
    // Query results and view projection
    displayChunks,
    currentPage,
    totalPages,
    goToPage,
    updateChunk,
    showingSearch,
    searchResults,
    chunksError: initialError,
    searchError,
    // URL view state
    chunkFromURL,
    searchQuery,
    handleSearchChange,
    enabledFilter,
    setEnabledFilter,
    activeSort,
    onSortColumn,
    onClearSort,
    setDocumentParams,
    // Selection
    selectedChunks,
    clearSelection,
    handleSelectChunk,
    handleSelectAll,
    selectOnly,
    removeFromSelection,
    selectedCounts,
    isAllSelected,
  }
}

export type ChunkListController = ReturnType<typeof useChunkListController>
