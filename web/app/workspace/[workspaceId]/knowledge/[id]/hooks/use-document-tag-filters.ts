'use client'

import { useCallback, useMemo, useState } from 'react'
import type { FilterTag } from '@/app/workspace/[workspaceId]/components'
import {
  getTagFilterLabel,
  projectTagFilters,
  type TagFilterEntry,
} from '@/app/workspace/[workspaceId]/knowledge/detail/domain/tags'

interface UseDocumentTagFiltersParams {
  /**
   * Runs after every effective filter change (entries replaced or a row
   * removed) so the caller can reset pagination and selection.
   */
  onFiltersChange: () => void
}

/**
 * Owns the editable tag-filter rows of the base detail: the entry list, its
 * query projection, and the removable filter chips. The rows stay in local
 * state on purpose (see `search-params.ts` — they are too structured for the
 * URL).
 */
export function useDocumentTagFilters({ onFiltersChange }: UseDocumentTagFiltersParams) {
  const [entries, setEntries] = useState<TagFilterEntry[]>([])

  const activeFilters = useMemo(() => projectTagFilters(entries), [entries])

  const updateEntries = useCallback(
    (next: TagFilterEntry[]) => {
      setEntries(next)
      onFiltersChange()
    },
    [onFiltersChange]
  )

  const removeEntry = useCallback(
    (id: string) => {
      setEntries((prev) => prev.filter((entry) => entry.id !== id))
      onFiltersChange()
    },
    [onFiltersChange]
  )

  /** Removable chips mirroring the active rows (`Tag name: value`). */
  const filterTags: FilterTag[] = useMemo(
    () =>
      entries.reduce<FilterTag[]>((acc, entry) => {
        if (!entry.tagSlot || !entry.value.trim()) return acc
        acc.push({
          label: getTagFilterLabel(entry),
          onRemove: () => removeEntry(entry.id),
        })
        return acc
      }, []),
    [entries, removeEntry]
  )

  return {
    entries,
    activeFilters,
    filterTags,
    updateEntries,
    removeEntry,
  }
}

export type DocumentTagFiltersController = ReturnType<typeof useDocumentTagFilters>
