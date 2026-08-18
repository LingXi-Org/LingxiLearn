'use client'

import { useCallback, useMemo } from 'react'
import { useQueryStates } from 'nuqs'
import type { FilesListFilters } from '@/app/workspace/[workspaceId]/files/lib/file-filters'
import {
  filesFilterParsers,
  filesFilterUrlKeys,
  filesSortParams,
} from '@/app/workspace/[workspaceId]/files/search-params'
import { useDebounce } from '@/hooks/use-debounce'
import { useDebouncedSearchSetter } from '@/hooks/use-debounced-search-setter'
import { useUrlSort } from '@/hooks/use-url-sort'

/**
 * Debounce window for `search` URL writes and filtering; the input itself stays
 * instant. Intentionally shorter than the shared `SEARCH_DEBOUNCE_MS` (300).
 */
export const FILES_SEARCH_DEBOUNCE_MS = 200 as const

/**
 * The Files list's URL-backed view state: debounced search, the type/size/uploader filters,
 * and the column sort. All writes stay out of the browser history (see `filesFilterUrlKeys`).
 */
export function useFilesFilters() {
  const [
    { search: urlSearchTerm, type: typeFilter, size: sizeFilter, uploadedBy: uploadedByFilter },
    setFileFilters,
  ] = useQueryStates(filesFilterParsers, filesFilterUrlKeys)

  /**
   * The input is controlled directly by the instant nuqs value; only the URL
   * write is debounced. The in-memory filter below still reads a debounced value
   * so it doesn't recompute on every keystroke.
   */
  const setSearchTerm = useDebouncedSearchSetter(
    (value, options) => setFileFilters({ search: value }, options),
    { debounceMs: FILES_SEARCH_DEBOUNCE_MS }
  )
  const debouncedSearchTerm = useDebounce(urlSearchTerm, FILES_SEARCH_DEBOUNCE_MS)

  const {
    sort: sortColumn,
    dir: sortDirection,
    activeSort,
    onSort,
    onClear,
  } = useUrlSort(filesSortParams, filesFilterUrlKeys)

  const setTypeFilter = useCallback(
    (next: string[]) => setFileFilters({ type: next }),
    [setFileFilters]
  )
  const setSizeFilter = useCallback(
    (next: string[]) => setFileFilters({ size: next }),
    [setFileFilters]
  )
  const setUploadedByFilter = useCallback(
    (next: string[]) => setFileFilters({ uploadedBy: next }),
    [setFileFilters]
  )
  const clearFilters = useCallback(() => {
    setFileFilters({ type: [], size: [], uploadedBy: [] })
  }, [setFileFilters])

  /** Stable identity while the URL values hold, so downstream row memos don't churn. */
  const filters: FilesListFilters = useMemo(
    () => ({
      type: typeFilter,
      size: sizeFilter,
      uploadedBy: uploadedByFilter,
    }),
    [typeFilter, sizeFilter, uploadedByFilter]
  )
  const hasActiveFilters =
    typeFilter.length > 0 || sizeFilter.length > 0 || uploadedByFilter.length > 0

  return {
    searchTerm: urlSearchTerm,
    setSearchTerm,
    debouncedSearchTerm,
    filters,
    typeFilter,
    sizeFilter,
    uploadedByFilter,
    hasActiveFilters,
    setTypeFilter,
    setSizeFilter,
    setUploadedByFilter,
    clearFilters,
    sortColumn,
    sortDirection,
    activeSort,
    onSort,
    onClear,
  }
}

export type FilesFiltersController = ReturnType<typeof useFilesFilters>
