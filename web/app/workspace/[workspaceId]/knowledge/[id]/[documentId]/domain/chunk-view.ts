/**
 * Document detail chunk-view domain primitives.
 *
 * Pure projections behind the chunk list's search mode (client-side paging of
 * the search result set) and row previews. No React, no URL state.
 */
import { truncate } from '@sim/utils/string'

/**
 * Page projection for the search view. The raw URL page can point past the end
 * once a fresh search returns fewer results, so it clamps into the result
 * set's page range; with no results the view sits on page 1 of 1.
 */
export function getSearchPageView(
  resultCount: number,
  pageSize: number,
  requestedPage: number
): { currentPage: number; totalPages: number } {
  const maxPages = Math.ceil(resultCount / pageSize)
  const totalPages = Math.max(1, maxPages)
  const currentPage = maxPages > 0 ? Math.max(1, Math.min(requestedPage, maxPages)) : 1
  return { currentPage, totalPages }
}

/** Slice the search result set down to one page (1-based). */
export function getSearchPageResults<T>(
  results: readonly T[],
  page: number,
  pageSize: number
): T[] {
  const start = (page - 1) * pageSize
  return results.slice(start, start + pageSize)
}

/**
 * Truncate a chunk's content for its row preview. With a search query the
 * window centers on the first matching term so the preview shows why the row
 * matched; otherwise it is a plain head truncation.
 */
export function truncateContent(content: string, maxLength = 150, searchQuery = ''): string {
  if (content.length <= maxLength) return content

  if (searchQuery.trim()) {
    const searchTerms = searchQuery
      .trim()
      .split(/\s+/)
      .filter((term) => term.length > 0)
      .map((term) => term.toLowerCase())

    for (const term of searchTerms) {
      const matchIndex = content.toLowerCase().indexOf(term)
      if (matchIndex !== -1) {
        const contextBefore = 30
        const start = Math.max(0, matchIndex - contextBefore)
        const end = Math.min(content.length, start + maxLength)

        let result = content.substring(start, end)
        if (start > 0) result = `...${result}`
        if (end < content.length) result = `${result}...`
        return result
      }
    }
  }

  return truncate(content, Math.max(0, maxLength - 3))
}
