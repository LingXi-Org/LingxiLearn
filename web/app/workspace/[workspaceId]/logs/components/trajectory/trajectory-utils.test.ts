import { describe, expect, it } from 'vitest'
import type { LogTraceSpan } from '@/lib/api/contracts/logs'
import {
  buildTrajectoryModel,
  getVisibleTrajectoryEntries,
  summarizeTrajectory,
} from './trajectory-utils'

const START = '2026-08-15T08:00:00.000Z'

function nestedTrace(): LogTraceSpan[] {
  return [
    {
      id: 'workflow',
      name: 'Research workflow',
      type: 'workflow',
      startTime: START,
      durationMs: 1_000,
      status: 'error',
      tokens: { total: 100 },
      children: [
        {
          id: 'agent',
          name: 'Research agent',
          type: 'agent',
          relativeStartMs: 100,
          durationMs: 800,
          status: 'error',
          tokens: { total: 100 },
          children: [
            {
              id: 'model',
              name: 'Generate query',
              type: 'model',
              relativeStartMs: 120,
              durationMs: 100,
              status: 'success',
              tokens: { total: 40 },
            },
            {
              id: 'search',
              name: 'Search web',
              type: 'tool',
              relativeStartMs: 300,
              durationMs: 200,
              status: 'error',
              errorMessage: 'Provider unavailable',
              tokens: { total: 60 },
            },
          ],
        },
      ],
    },
  ]
}

describe('buildTrajectoryModel', () => {
  it('flattens nested spans onto a shared run clock', () => {
    const model = buildTrajectoryModel(nestedTrace())

    expect(model.entries.map((entry) => entry.path.join('.'))).toEqual([
      '1',
      '1.1',
      '1.1.1',
      '1.1.2',
    ])
    expect(model.entries.map((entry) => entry.offsetMs)).toEqual([0, 100, 120, 300])
    expect(model.maxDepth).toBe(3)
    expect(model.totalDurationMs).toBe(1_000)
  })

  it('projects legacy tool calls as nested tool spans', () => {
    const model = buildTrajectoryModel([
      {
        id: 'agent',
        name: 'Agent',
        type: 'agent',
        startTime: START,
        durationMs: 500,
        toolCalls: [
          {
            id: 'call-1',
            name: 'fetch',
            duration: 120,
            startTime: '2026-08-15T08:00:00.100Z',
            endTime: '2026-08-15T08:00:00.220Z',
            result: { ok: true },
          },
        ],
      },
    ])

    expect(model.entries).toHaveLength(2)
    expect(model.entries[1]).toMatchObject({ depth: 1, offsetMs: 100, durationMs: 120 })
    expect(model.entries[1].span).toMatchObject({ type: 'tool', name: 'fetch' })
  })
})

describe('trajectory summaries and filtering', () => {
  it('does not double-count propagated parent tokens or failures', () => {
    const summary = summarizeTrajectory(buildTrajectoryModel(nestedTrace()))

    expect(summary).toEqual({
      spanCount: 4,
      maxDepth: 3,
      toolCount: 1,
      failureCount: 1,
      tokenCount: 100,
    })
  })

  it('keeps ancestors of matching nested spans and honors collapsed branches', () => {
    const model = buildTrajectoryModel(nestedTrace())
    const expanded = getVisibleTrajectoryEntries(model.entries, {
      searchQuery: 'provider unavailable',
      type: 'tool',
      collapsedIds: new Set(),
    })

    expect(expanded.map((entry) => entry.span.name)).toEqual([
      'Research workflow',
      'Research agent',
      'Search web',
    ])

    const collapsed = getVisibleTrajectoryEntries(model.entries, {
      searchQuery: 'provider unavailable',
      type: 'tool',
      collapsedIds: new Set([expanded[0].id]),
    })
    expect(collapsed.map((entry) => entry.span.name)).toEqual(['Research workflow'])
  })
})
