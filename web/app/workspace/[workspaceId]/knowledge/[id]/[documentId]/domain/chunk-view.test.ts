/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'
import {
  getSearchPageResults,
  getSearchPageView,
  truncateContent,
} from '@/app/workspace/[workspaceId]/knowledge/[id]/[documentId]/domain/chunk-view'

describe('getSearchPageView', () => {
  it('clamps a past-the-end page into the result range', () => {
    expect(getSearchPageView(120, 50, 5)).toEqual({ currentPage: 3, totalPages: 3 })
  })

  it('keeps a valid page as-is', () => {
    expect(getSearchPageView(120, 50, 2)).toEqual({ currentPage: 2, totalPages: 3 })
  })

  it('sits on page 1 of 1 for an empty result set', () => {
    expect(getSearchPageView(0, 50, 4)).toEqual({ currentPage: 1, totalPages: 1 })
  })

  it('never goes below page 1', () => {
    expect(getSearchPageView(200, 50, 0)).toEqual({ currentPage: 1, totalPages: 4 })
  })
})

describe('getSearchPageResults', () => {
  it('slices the requested 1-based page', () => {
    const results = Array.from({ length: 120 }, (_, i) => i)
    expect(getSearchPageResults(results, 1, 50)).toHaveLength(50)
    expect(getSearchPageResults(results, 3, 50)).toHaveLength(20)
    expect(getSearchPageResults(results, 3, 50)[0]).toBe(100)
  })
})

describe('truncateContent', () => {
  const longContent = `${'lorem ipsum dolor sit amet '.repeat(20)}target${' tail'.repeat(50)}`

  it('returns short content untouched', () => {
    expect(truncateContent('short', 150, '')).toBe('short')
  })

  it('centers the window on the first search-term match', () => {
    const preview = truncateContent(longContent, 150, 'target')
    expect(preview).toContain('target')
    expect(preview.startsWith('...')).toBe(true)
    expect(preview.endsWith('...')).toBe(true)
    expect(preview.length).toBeLessThanOrEqual(156)
  })

  it('falls back to head truncation without a query match', () => {
    const preview = truncateContent(longContent, 150, 'absent-term')
    expect(preview.startsWith('lorem')).toBe(true)
    expect(preview.length).toBeLessThanOrEqual(150)
  })

  it('matches terms case-insensitively', () => {
    const preview = truncateContent(longContent, 150, 'TARGET')
    expect(preview.toLowerCase()).toContain('target')
  })
})
