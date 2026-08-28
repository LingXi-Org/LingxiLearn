import { describe, expect, test } from 'vitest'
import {
  projectRuntimeGraph,
  runtimeEdgeStatus,
  runtimeStatusToRunPath,
} from './runtime-graph-adapter'

function graph(overrides: Record<string, unknown> = {}) {
  return {
    schemaVersion: 'lingxilearn.execution.v1',
    executionId: 'exec-1',
    terminal: false,
    metadata: {},
    nodes: {
      tutor: {
        id: 'tutor',
        label: 'Tutor',
        kind: 'agent',
        capability: 'answer_user',
        status: 'pending',
        details: {},
      },
      quiz: {
        id: 'quiz',
        label: 'Quiz Generator',
        kind: 'agent',
        capability: 'assess.generate',
        status: 'completed',
        details: {},
      },
      internal: {
        id: 'internal',
        label: 'Orchestrator',
        kind: 'deterministic',
        capability: 'orchestrate',
        status: 'completed',
        details: {},
      },
    },
    dependencies: [
      { id: 'tutor-internal', sourceNodeId: 'tutor', targetNodeId: 'internal' },
      { id: 'internal-quiz', sourceNodeId: 'internal', targetNodeId: 'quiz' },
    ],
    ...overrides,
  }
}

describe('LingxiLearn execution snapshot projection', () => {
  test('renders the native nodes and dependency contract', () => {
    const projection = projectRuntimeGraph({
      schemaVersion: 'lingxilearn.execution.v1',
      executionId: 'exec-1',
      taskId: 'task-1',
      graphVersion: 'v1',
      status: 'running',
      paused: false,
      terminal: false,
      nodes: {
        tutor: {
          id: 'tutor',
          label: 'Tutor',
          kind: 'agent',
          capability: 'tutor',
          provider: 'answer_user',
          status: 'running',
          details: {},
        },
        quiz: {
          id: 'quiz',
          label: 'Quiz Generator',
          kind: 'agent',
          capability: 'quiz_generator',
          provider: 'quiz_generator',
          status: 'queued',
          details: {},
        },
      },
      dependencies: [
        {
          id: 'tutor->quiz',
          sourceNodeId: 'tutor',
          targetNodeId: 'quiz',
          kind: 'dependency',
        },
      ],
      variables: {},
      groups: {},
      metadata: {},
    })

    expect(projection.nodes.tutor.runtimeStatus).toBe('running')
    expect(projection.nodes.quiz.runtimeStatus).toBe('queued')
    expect(
      projection.connections.some(
        (edge) => edge.source === 'tutor' && edge.target === 'quiz',
      ),
    ).toBe(true)
  })
  test('keeps visible capabilities and collapses hidden runtime nodes', () => {
    const projection = projectRuntimeGraph(graph())

    expect(Object.keys(projection.nodes)).toEqual([
      'runtime-user-input',
      'tutor',
      'quiz',
    ])
    expect(
      projection.connections.some(
        (edge) => edge.source === 'tutor' && edge.target === 'quiz',
      ),
    ).toBe(true)
    expect(projection.connections.some((edge) => edge.source === 'internal')).toBe(
      false,
    )
  })

  test('preserves stable node and edge identities while status changes', () => {
    const first = projectRuntimeGraph(graph())
    const next = projectRuntimeGraph({
      ...graph(),
      nodes: {
        ...graph().nodes,
        tutor: {
          ...graph().nodes.tutor,
          status: 'retrying',
        },
      },
    })

    expect(Object.keys(next.nodes)).toEqual(Object.keys(first.nodes))
    expect(next.connections.map((edge) => edge.id)).toEqual(
      first.connections.map((edge) => edge.id),
    )
    expect(next.nodes.tutor.runtimeStatus).toBe('retrying')
    expect(next.nodes.tutor.name).toBe('辅导老师')
  })

  test('retains every execution state for the read-only canvas projection', () => {
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
      ...graph(),
      nodes: Object.fromEntries(
        statuses.map((status, index) => [
          `step-${index}`,
          {
            id: `step-${index}`,
            label: `Step ${index}`,
            kind: 'agent',
            capability: 'answer_user',
            status,
            details: {},
          },
        ]),
      ),
      dependencies: [],
    })

    expect(
      statuses.map(
        (_, index) => projection.nodes[`step-${index}`].runtimeStatus,
      ),
    ).toEqual(statuses)
    expect(
      runtimeStatusToRunPath(projection.nodes['step-4'].runtimeStatus),
    ).toBe('success')
    expect(
      runtimeStatusToRunPath(projection.nodes['step-5'].runtimeStatus),
    ).toBe('success')
    expect(
      runtimeStatusToRunPath(projection.nodes['step-6'].runtimeStatus),
    ).toBe('error')
    expect(
      runtimeStatusToRunPath(projection.nodes['step-7'].runtimeStatus),
    ).toBeUndefined()
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

    expect(projection.nodes['runtime-user-input'].data.runtimeKind).toBe(
      'input',
    )
    expect(
      projection.nodes['control-learning_plan_decision'].data.runtimeKind,
    ).toBe('control')
    expect(
      projection.connections.some(
        (edge) =>
          edge.source === 'runtime-user-input' &&
          edge.target === 'control-learning_plan_decision',
      ),
    ).toBe(true)
  })

  test('maps execution states to native renderer statuses', () => {
    const projection = projectRuntimeGraph({
      ...graph(),
      nodes: {
        failed: {
          id: 'failed',
          label: 'Tutor',
          kind: 'agent',
          capability: 'answer_user',
          status: 'failed',
          details: {},
        },
        done: {
          id: 'done',
          label: 'Quiz Generator',
          kind: 'agent',
          capability: 'assess.generate',
          status: 'cached',
          details: {},
        },
      },
      dependencies: [
        { id: 'failed-done', sourceNodeId: 'failed', targetNodeId: 'done' },
      ],
    })

    expect(
      runtimeStatusToRunPath(projection.nodes.failed.runtimeStatus),
    ).toBe('error')
    expect(runtimeStatusToRunPath(projection.nodes.done.runtimeStatus)).toBe(
      'success',
    )
    expect(
      runtimeEdgeStatus(projection.nodes.failed, projection.nodes.done),
    ).toBe('error')
    expect(
      runtimeEdgeStatus(
        projection.nodes.done,
        projection.nodes.failed,
        'success',
      ),
    ).toBe('error')
    expect(
      runtimeEdgeStatus(
        projection.nodes.failed,
        projection.nodes.done,
        'success',
      ),
    ).toBe('error')
    expect(
      runtimeEdgeStatus(
        projection.nodes.tutor,
        projection.nodes.done,
        'success',
      ),
    ).toBe('success')
  })

  test('filters malformed and dangling edges', () => {
    const projection = projectRuntimeGraph({
      ...graph(),
      nodes: {
        tutor: {
          id: 'tutor',
          label: 'Tutor',
          kind: 'agent',
          capability: 'answer_user',
          status: 'running',
          details: {},
        },
      },
      dependencies: [
        { id: 'dangling', sourceNodeId: 'missing', targetNodeId: 'tutor' },
        { id: 'self', sourceNodeId: 'tutor', targetNodeId: 'tutor' },
        {
          id: 'duplicate',
          sourceNodeId: 'runtime-user-input',
          targetNodeId: 'tutor',
        },
      ],
    })

    expect(
      projection.connections.every(
        (edge) =>
          projection.nodes[edge.source] && projection.nodes[edge.target],
      ),
    ).toBe(true)
    expect(
      new Set(projection.connections.map((edge) => `${edge.source}->${edge.target}`))
        .size,
    ).toBe(projection.connections.length)
  })

  test('fails closed on snapshots outside the native schema', () => {
    const projection = projectRuntimeGraph({
      blocks: { nullBlock: null, listBlock: [], tutor: {} },
      edges: [null, { source: 'missing', target: 'tutor' }],
    })

    expect(projection.nodes['runtime-user-input']).toBeDefined()
    expect(Object.keys(projection.nodes)).toEqual(['runtime-user-input'])
    expect(
      projection.connections.every(
        (edge) =>
          projection.nodes[edge.source] && projection.nodes[edge.target],
      ),
    ).toBe(true)
  })

  test('uses stable runtime card heights', () => {
    const projection = projectRuntimeGraph(graph())
    expect(projection.nodes.tutor.height).toBe(132)
  })
})
