/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'
import {
  countSelectedByEnabled,
  isEntirePageSelected,
  resolveBulkTargets,
} from '@/app/workspace/[workspaceId]/knowledge/detail/domain/documents'

interface Row {
  id: string
  enabled: boolean
}

const ROWS: Row[] = [
  { id: 'a', enabled: true },
  { id: 'b', enabled: false },
  { id: 'c', enabled: true },
  { id: 'd', enabled: false },
]

describe('resolveBulkTargets', () => {
  it('enable only targets disabled rows inside the selection', () => {
    const targets = resolveBulkTargets(ROWS, new Set(['a', 'b', 'd']), 'enable')
    expect(targets.map((row) => row.id)).toEqual(['b', 'd'])
  })

  it('disable only targets enabled rows inside the selection', () => {
    const targets = resolveBulkTargets(ROWS, new Set(['a', 'b', 'c']), 'disable')
    expect(targets.map((row) => row.id)).toEqual(['a', 'c'])
  })

  it('delete targets every selected row', () => {
    const targets = resolveBulkTargets(ROWS, new Set(['b', 'c']), 'delete')
    expect(targets.map((row) => row.id)).toEqual(['b', 'c'])
  })

  it('ignores ids that are not on the page and returns empty for an empty selection', () => {
    expect(resolveBulkTargets(ROWS, new Set(['zzz']), 'delete')).toEqual([])
    expect(resolveBulkTargets(ROWS, new Set(), 'enable')).toEqual([])
  })
})

describe('countSelectedByEnabled', () => {
  it('tallies the selection by enabled state', () => {
    expect(countSelectedByEnabled(ROWS, new Set(['a', 'b', 'd']))).toEqual({
      enabled: 1,
      disabled: 2,
    })
    expect(countSelectedByEnabled(ROWS, new Set())).toEqual({ enabled: 0, disabled: 0 })
  })
})

describe('isEntirePageSelected', () => {
  it('is true only when a non-empty page is fully selected', () => {
    expect(isEntirePageSelected(ROWS.length, new Set(['a', 'b', 'c', 'd']))).toBe(true)
    expect(isEntirePageSelected(ROWS.length, new Set(['a', 'b']))).toBe(false)
    expect(isEntirePageSelected(0, new Set())).toBe(false)
  })
})
