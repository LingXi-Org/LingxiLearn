/**
 * @vitest-environment jsdom
 */
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ExecutionCanvasNode } from '../runtime-graph-adapter'
import { LingxiRuntimeGraph } from './lingxi-runtime-graph'

interface CapturedFlowProps {
  nodes: Array<{ id: string; position: { x: number; y: number }; data: { block: ExecutionCanvasNode } }>
  edges: Array<{
    source: string
    target: string
    data: { runStatus: string; isTargetActive: boolean }
  }>
}

const flowCapture = vi.hoisted(() => ({ props: undefined as CapturedFlowProps | undefined }))

vi.mock('reactflow', async () => {
  const React = await import('react')
  return {
    default: (props: CapturedFlowProps) => {
      flowCapture.props = props
      return React.createElement('div', { 'data-testid': 'execution-flow' })
    },
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Position: { Top: 'top', Right: 'right', Bottom: 'bottom', Left: 'left' },
  }
})

vi.mock('reactflow/dist/style.css', () => ({}))
vi.mock('@/components/workflow', () => ({
  SubBlockRowView: () => null,
  WorkflowBlockView: () => null,
  WorkflowEdgeView: () => null,
}))

let root: Root | undefined
let host: HTMLDivElement | undefined

afterEach(() => {
  if (root) {
    act(() => root?.unmount())
  }
  host?.remove()
  root = undefined
  host = undefined
  flowCapture.props = undefined
})

function executionSnapshot(status: 'running' | 'completed' | 'failed') {
  return {
    schemaVersion: 'lingxilearn.execution.v1',
    executionId: 'execution-1',
    nodes: {
      source: {
        id: 'source',
        label: 'Tutor',
        kind: 'agent',
        capability: 'answer_user',
        status: 'completed',
        details: {},
      },
      target: {
        id: 'target',
        label: 'Quiz Generator',
        kind: 'agent',
        capability: 'assess.generate',
        status,
        details: { phase: status },
      },
    },
    dependencies: [
      { id: 'source-target', sourceNodeId: 'source', targetNodeId: 'target' },
    ],
    terminal: status !== 'running',
    metadata: {},
  }
}

function capturedNode(id: string) {
  const node = flowCapture.props?.nodes.find((candidate) => candidate.id === id)
  expect(node).toBeDefined()
  return node!
}

function capturedDependency() {
  const edge = flowCapture.props?.edges.find(
    (candidate) => candidate.source === 'source' && candidate.target === 'target'
  )
  expect(edge).toBeDefined()
  return edge!
}

describe('LingxiRuntimeGraph live execution state', () => {
  it('refreshes node and edge state without recalculating an unchanged topology', () => {
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)

    act(() => root?.render(<LingxiRuntimeGraph taskId='task-1' executionSnapshot={executionSnapshot('running')} />))
    const runningPosition = { ...capturedNode('target').position }
    expect(capturedNode('target').data.block.runtimeStatus).toBe('running')
    expect(capturedNode('target').data.block.data.phase).toBe('running')
    expect(capturedDependency().data).toMatchObject({
      runStatus: 'success',
      isTargetActive: true,
    })

    act(() =>
      root?.render(
        <LingxiRuntimeGraph
          taskId='task-1'
          executionSnapshot={executionSnapshot('completed')}
        />
      )
    )
    expect(capturedNode('target').position).toEqual(runningPosition)
    expect(capturedNode('target').data.block.runtimeStatus).toBe('completed')
    expect(capturedNode('target').data.block.data.phase).toBe('completed')
    expect(capturedDependency().data).toMatchObject({
      runStatus: 'success',
      isTargetActive: false,
    })

    act(() => root?.render(<LingxiRuntimeGraph taskId='task-1' executionSnapshot={executionSnapshot('failed')} />))
    expect(capturedNode('target').position).toEqual(runningPosition)
    expect(capturedNode('target').data.block.runtimeStatus).toBe('failed')
    expect(capturedNode('target').data.block.data.phase).toBe('failed')
    expect(capturedDependency().data).toMatchObject({
      runStatus: 'error',
      isTargetActive: false,
    })
  })
})
