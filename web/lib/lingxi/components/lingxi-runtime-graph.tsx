'use client'

import { useMemo, useRef } from 'react'
import ReactFlow, {
  ReactFlowProvider,
  type EdgeProps,
  type Node,
  type NodeProps,
  Position,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { Sparkles } from '@sim/emcn/icons'
import { WorkflowBlockView, WorkflowEdgeView } from '@sim/workflow-renderer'
import type { EdgeRunStatus } from '@sim/workflow-renderer'
import { layoutRuntimeGraph } from '../runtime-graph-layout'

interface RuntimeGraphProps {
  taskId: string
  workflowState?: Record<string, unknown> | null
}

function blockState(data: Record<string, unknown>) {
  return String(data.executionState ?? data.status ?? 'not-executed')
}

function RuntimeNode({ id, data }: NodeProps) {
  const block = (data.block ?? {}) as Record<string, unknown>
  const status = blockState(block)
  return (
    <WorkflowBlockView
      id={id}
      type={String(block.type ?? 'agent')}
      name={String(block.name ?? id)}
      typeLabel={String(block.type ?? 'agent')}
      isEnabled={block.enabled !== false}
      isLocked
      hasRing={status === 'running' || status === 'retrying'}
      isRunning={status === 'running' || status === 'retrying'}
      isWorkflowRunning={Boolean(data.workflowRunning)}
      isExecutionHighlighted={status !== 'not-executed' && status !== 'queued'}
      ringStyles=''
      runPathStatus={status === 'completed' || status === 'cached' ? 'success' : status === 'failed' ? 'error' : undefined}
      Icon={Sparkles}
      iconBgColor='var(--surface-4)'
      horizontalHandles
      shouldShowDefaultHandles
      hasContentBelowHeader={false}
      conditionRows={[]}
      routerRows={[]}
      wouldCreateConnectionCycle={() => false}
      onSelect={() => {}}
      rows={null}
    />
  )
}

function RuntimeEdge(props: EdgeProps) {
  const data = (props.data ?? {}) as { runStatus?: EdgeRunStatus; isTargetActive?: boolean }
  return (
    <WorkflowEdgeView
      {...props}
      diffStatus={null}
      runStatus={data.runStatus}
      isPreviewRun={false}
      isWorkflowRunning={Boolean(data.isWorkflowRunning)}
      isTargetActive={Boolean(data.isTargetActive)}
      isConnectedToSelection={false}
    />
  )
}

export function LingxiRuntimeGraph({ taskId, workflowState }: RuntimeGraphProps) {
  const previousPositions = useRef<Record<string, { x: number; y: number }>>({})
  const graph = workflowState ?? {}
  const blocks = (graph.blocks ?? {}) as Record<string, Record<string, unknown>>
  const rawEdges = (graph.edges ?? []) as Array<Record<string, unknown>>
  const edges = rawEdges
    .map((edge) => ({ id: String(edge.id), source: String(edge.source), target: String(edge.target), data: edge.data as Record<string, unknown> | undefined }))
    .filter((edge) => edge.id && edge.source && edge.target)
  const positions = useMemo(
    () => {
      const next = layoutRuntimeGraph(blocks, edges, previousPositions.current)
      previousPositions.current = next
      return next
    },
    [blocks, edges]
  )
  const metadata = (graph.metadata as Record<string, unknown> | undefined) ?? {}
  const running = !Boolean(graph.terminal ?? metadata.terminal)
  const nodes = useMemo<Node[]>(
    () => Object.entries(blocks).map(([id, block]) => ({
      id,
      type: 'lingxiRuntimeNode',
      position: positions[id] ?? { x: 0, y: 0 },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      data: { block, workflowRunning: running },
      draggable: false,
      selectable: false,
    })),
    [blocks, positions, running]
  )
  const flowEdges = useMemo(
    () => edges.map((edge) => {
      const targetStatus = blockState(blocks[edge.target] ?? {})
      const sourceStatus = blockState(blocks[edge.source] ?? {})
      const runStatus: EdgeRunStatus = targetStatus === 'failed' ? 'error' : sourceStatus === 'completed' || sourceStatus === 'cached' ? 'success' : undefined
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: 'lingxiRuntimeEdge',
        sourceHandle: 'source',
        targetHandle: 'target',
        data: { runStatus, isTargetActive: targetStatus === 'running' || targetStatus === 'retrying', isWorkflowRunning: running },
        selectable: false,
      }
    }),
    [blocks, edges, running]
  )

  if (!taskId) return <div className='p-6 text-sm text-[var(--text-muted)]'>暂无运行任务。</div>
  if (nodes.length === 0) return <div className='flex h-full items-center justify-center text-sm text-[var(--text-muted)]'>等待运行图节点…</div>
  return (
    <div className='h-full w-full bg-[var(--surface-1)]'>
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={flowEdges}
          nodeTypes={{ lingxiRuntimeNode: RuntimeNode }}
          edgeTypes={{ lingxiRuntimeEdge: RuntimeEdge }}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag
          zoomOnScroll
          proOptions={{ hideAttribution: true }}
        />
      </ReactFlowProvider>
    </div>
  )
}
