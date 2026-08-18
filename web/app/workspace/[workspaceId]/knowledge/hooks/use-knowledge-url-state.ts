'use client'

import { useCallback } from 'react'
import { useQueryStates } from 'nuqs'
import { SEARCH_DEBOUNCE_MS } from '@/lib/url-state'
import { useDebounce } from '@/hooks/use-debounce'
import { useDebouncedSearchSetter } from '@/hooks/use-debounced-search-setter'
import { useUrlSort } from '@/hooks/use-url-sort'
import type { KnowledgeListFilters } from '../list/types'
import { knowledgeParsers, knowledgeSortParams, knowledgeUrlKeys } from '../search-params'

/**
 * URL-backed view state of the knowledge list: search, the three structured filters, and
 * the active sort. All of it lives in the URL (replace-in-place, no back-stack churn) so
 * the list's view is shareable and survives a refresh — the page component itself keeps
 * no filter state.
 */
export function useKnowledgeUrlState() {
  const [
    {
      search: urlSearchQuery,
      connector: connectorFilter,
      content: contentFilter,
      owner: ownerFilter,
    },
    setKnowledgeFilters,
  ] = useQueryStates(knowledgeParsers, knowledgeUrlKeys)

  /**
   * The input is controlled directly by the instant nuqs value; only the URL
   * write is debounced. The in-memory filter below still reads a debounced
   * value so it doesn't recompute on every keystroke.
   */
  const setSearchQuery = useDebouncedSearchSetter((value, options) =>
    setKnowledgeFilters({ search: value }, options)
  )
  const debouncedSearchQuery = useDebounce(urlSearchQuery, SEARCH_DEBOUNCE_MS)

  const {
    sort: sortColumn,
    dir: sortDirection,
    activeSort,
    onSort: onSortColumn,
    onClear: onClearSort,
  } = useUrlSort(knowledgeSortParams, knowledgeUrlKeys)

  const setConnectorFilter = useCallback(
    (next: string[]) => setKnowledgeFilters({ connector: next }),
    [setKnowledgeFilters]
  )
  const setContentFilter = useCallback(
    (next: string[]) => setKnowledgeFilters({ content: next }),
    [setKnowledgeFilters]
  )
  const setOwnerFilter = useCallback(
    (next: string[]) => setKnowledgeFilters({ owner: next }),
    [setKnowledgeFilters]
  )

  const filters: KnowledgeListFilters = {
    connector: connectorFilter,
    content: contentFilter,
    owner: ownerFilter,
  }

  return {
    urlSearchQuery,
    debouncedSearchQuery,
    setSearchQuery,
    filters,
    connectorFilter,
    setConnectorFilter,
    contentFilter,
    setContentFilter,
    ownerFilter,
    setOwnerFilter,
    sortColumn,
    sortDirection,
    activeSort,
    onSortColumn,
    onClearSort,
  }
}

export type KnowledgeUrlState = ReturnType<typeof useKnowledgeUrlState>
