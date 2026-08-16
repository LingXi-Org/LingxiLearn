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

  it('keeps the eight semantic lanes on one execution clock', () => {
    const model = buildTrajectoryModel([], 1_000, {
      version: 'lingxi-trajectory.v1',
      executionId: 'exec-1',
      clock: { startedAt: START, endedAt: '2026-08-15T08:00:01.000Z', durationMs: 1_000 },
      lanes: [
        { id: 'run', label: 'RUN', items: [] },
        {
          id: 'task',
          label: 'CAPABILITY TASK',
          items: [
            {
              id: 'task-1',
              lane: 'task',
              kind: 'capability.task',
              label: 'Search',
              startTime: '2026-08-15T08:00:00.200Z',
              endTime: '2026-08-15T08:00:00.500Z',
              relativeStartMs: 200,
              durationMs: 300,
              precision: 'exact',
            },
          ],
        },
      ],
    } as never)

    expect(model.lanes.map((lane) => lane.id)).toEqual([
      'run',
      'control',
      'task',
      'action',
      'runtime',
      'state',
      'resource',
      'output',
    ])
    expect(model.lanes[2].entries[0]).toMatchObject({ offsetMs: 200, durationMs: 300 })
    expect(model.source).toBe('trajectory')
  })

  it('keeps semantic ids stable and maps parent chains across lanes', () => {
    const model = buildTrajectoryModel([], 0, {
      version: 'lingxi-trajectory.v1',
      executionId: 'exec-parent',
      clock: { startedAt: START, endedAt: '2026-08-15T08:00:01.000Z', durationMs: 1_000 },
      lanes: [
        { id: 'run', label: 'RUN', items: [] },
        {
          id: 'control',
          label: 'CONTROL ROUND',
          items: [
            {
              id: 'round:1',
              lane: 'control',
              kind: 'round',
              label: 'Control round 1',
              roundStep: 1,
              startTime: START,
              relativeStartMs: 0,
              durationMs: 800,
              precision: 'exact',
            },
          ],
        },
        {
          id: 'task',
          label: 'CAPABILITY TASK',
          items: [
            {
              id: 'task:n1',
              lane: 'task',
              kind: 'capability.task',
              label: 'Search',
              parentId: 'round:1',
              roundStep: 1,
              startTime: '2026-08-15T08:00:00.100Z',
              relativeStartMs: 100,
              durationMs: 500,
              precision: 'exact',
            },
          ],
        },
        {
          id: 'action',
          label: 'ACTION',
          items: [
            {
              id: 'action:model',
              lane: 'action',
              kind: 'model',
              label: 'Generate query',
              parentId: 'task:n1',
              startTime: '2026-08-15T08:00:00.200Z',
              relativeStartMs: 200,
              durationMs: 100,
              precision: 'exact',
              metadata: { tokens: { input: 4, output: 6 }, provider: 'test' },
            },
          ],
        },
        { id: 'runtime', label: 'RUNTIME', items: [] },
        { id: 'state', label: 'STATE', items: [] },
        { id: 'resource', label: 'RESOURCE', items: [] },
        { id: 'output', label: 'OUTPUT', items: [] },
      ],
      summary: { tokens: 42 },
    } as never)

    const round = model.entries.find((entry) => entry.sourceId === 'round:1')!
    const task = model.entries.find((entry) => entry.sourceId === 'task:n1')!
    const action = model.entries.find((entry) => entry.sourceId === 'action:model')!
    expect(round.id).toBe('round:1')
    expect(task.parentId).toBe(round.id)
    expect(action.parentIds).toEqual([round.id, task.id])
    expect(summarizeTrajectory(model).tokenCount).toBe(42)

    const matches = getVisibleTrajectoryEntries(model.entries, {
      searchQuery: 'provider',
      type: 'model',
      collapsedIds: new Set(),
    })
    expect(matches.map((entry) => entry.id)).toEqual([round.id, task.id, action.id])
    expect(
      getVisibleTrajectoryEntries(model.entries, {
        searchQuery: 'provider',
        type: 'model',
        collapsedIds: new Set([task.id]),
      }).map((entry) => entry.id)
    ).toEqual([round.id, task.id])
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
