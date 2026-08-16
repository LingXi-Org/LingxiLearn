import { describe, expect, test } from 'bun:test'
import {
  projectRuntimeGraph,
  runtimeEdgeStatus,
  runtimeStatusToRunPath,
} from './runtime-graph-adapter'

function graph(overrides: Record<string, unknown> = {}) {
  return {
    blocks: {
      tutor: {
        name: 'Tutor',
        type: 'agent',
        status: 'pending',
        data: { capability: 'answer_user' },
      },
      quiz: {
        name: 'Quiz Generator',
        type: 'agent',
        status: 'completed',
        data: { capability: 'assess.generate' },
      },
      internal: {
        name: 'Orchestrator',
        type: 'router_v2',
        status: 'completed',
        data: { capability: 'orchestrate' },
      },
    },
    edges: [
      { id: 'tutor-internal', source: 'tutor', target: 'internal' },
      { id: 'internal-quiz', source: 'internal', target: 'quiz' },
    ],
    ...overrides,
  }
}

describe('Runtime Graph Sim projection', () => {
  test('keeps visible capabilities and collapses hidden runtime nodes', () => {
    const projection = projectRuntimeGraph(graph())

    expect(Object.keys(projection.blocks)).toEqual(['runtime-user-input', 'tutor', 'quiz'])
    expect(projection.edges.some((edge) => edge.source === 'tutor' && edge.target === 'quiz')).toBe(
      true
    )
    expect(projection.edges.some((edge) => edge.source === 'internal')).toBe(false)
  })

  test('preserves stable node and edge identities while status changes', () => {
    const first = projectRuntimeGraph(graph())
    const next = projectRuntimeGraph({
      ...graph(),
      blocks: {
        ...graph().blocks,
        tutor: {
          ...graph().blocks.tutor,
          status: 'retrying',
        },
      },
    })

    expect(Object.keys(next.blocks)).toEqual(Object.keys(first.blocks))
    expect(next.edges.map((edge) => edge.id)).toEqual(first.edges.map((edge) => edge.id))
    expect(next.blocks.tutor.executionState).toBe('retrying')
    expect(next.blocks.tutor.name).toBe('辅导老师')
  })

  test('retains every V2 execution state for the native block projection', () => {
    const statuses = [
      'queued',
      'pending',
      'running',
      'retrying',
      'completed',
      'cached',
      'failed',
      'cancelled',
    ] as const
    const projection = projectRuntimeGraph({
      blocks: Object.fromEntries(
        statuses.map((status, index) => [
          `step-${index}`,
          {
            name: `Step ${index}`,
            status,
            data: { capability: 'answer_user' },
          },
        ])
      ),
      edges: [],
    })

    expect(statuses.map((_, index) => projection.blocks[`step-${index}`].executionState)).toEqual(
      statuses
    )
    expect(runtimeStatusToRunPath(projection.blocks['step-4'].executionState)).toBe('success')
    expect(runtimeStatusToRunPath(projection.blocks['step-5'].executionState)).toBe('success')
    expect(runtimeStatusToRunPath(projection.blocks['step-6'].executionState)).toBe('error')
    expect(runtimeStatusToRunPath(projection.blocks['step-7'].executionState)).toBeUndefined()
  })

  test('adds the current user-input and plan-decision chain without changing backend data', () => {
    const projection = projectRuntimeGraph(graph(), [
      {
        sequence: 1,
        kind: 'model.completed',
        agent: 'learning_plan_decision',
        payload: {},
        ts: null,
      },
    ])

    expect(projection.blocks['runtime-user-input'].data.runtimeKind).toBe('input')
    expect(projection.blocks['control-learning_plan_decision'].data.runtimeKind).toBe('control')
    expect(
      projection.edges.some(
        (edge) => edge.source === 'runtime-user-input' && edge.target === 'control-learning_plan_decision'
      )
    ).toBe(true)
  })

  test('maps execution states to native renderer statuses', () => {
    const projection = projectRuntimeGraph({
      blocks: {
        failed: {
          name: 'Tutor',
          type: 'agent',
          status: 'failed',
          data: { capability: 'answer_user' },
        },
        done: {
          name: 'Quiz Generator',
          type: 'agent',
          status: 'cached',
          data: { capability: 'assess.generate' },
        },
      },
      edges: [{ id: 'failed-done', source: 'failed', target: 'done' }],
    })

    expect(runtimeStatusToRunPath(projection.blocks.failed.executionState)).toBe('error')
    expect(runtimeStatusToRunPath(projection.blocks.done.executionState)).toBe('success')
    expect(runtimeEdgeStatus(projection.blocks.failed, projection.blocks.done)).toBe('error')
    expect(runtimeEdgeStatus(projection.blocks.done, projection.blocks.failed, 'success')).toBe('error')
    expect(runtimeEdgeStatus(projection.blocks.failed, projection.blocks.done, 'success')).toBe('error')
    expect(runtimeEdgeStatus(projection.blocks.tutor, projection.blocks.done, 'success')).toBe('success')
  })

  test('filters malformed and dangling edges', () => {
    const projection = projectRuntimeGraph({
      blocks: {
        tutor: {
          name: 'Tutor',
          type: 'agent',
          data: { capability: 'answer_user' },
        },
      },
      edges: [
        { id: 'dangling', source: 'missing', target: 'tutor' },
        { id: 'self', source: 'tutor', target: 'tutor' },
        { id: 'duplicate', source: 'runtime-user-input', target: 'tutor' },
      ],
    })

    expect(projection.edges.every((edge) => projection.blocks[edge.source] && projection.blocks[edge.target])).toBe(
      true
    )
    expect(new Set(projection.edges.map((edge) => `${edge.source}->${edge.target}`)).size).toBe(
      projection.edges.length
    )
  })

  test('tolerates empty and malformed workflow snapshots', () => {
    const projection = projectRuntimeGraph({
      blocks: { nullBlock: null, listBlock: [], tutor: {} },
      edges: [null, { source: 'missing', target: 'tutor' }],
    })

    expect(projection.blocks['runtime-user-input']).toBeDefined()
    expect(Object.keys(projection.blocks)).toEqual(['runtime-user-input'])
    expect(projection.edges.every((edge) => projection.blocks[edge.source] && projection.blocks[edge.target])).toBe(
      true
    )
  })
})
