'use client'

import { useMemo, useRef } from 'react'
import ReactFlow, {
  Handle,
  ReactFlowProvider,
  type EdgeProps,
  type Node,
  type NodeProps,
  Position,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { AgentIcon, CodeIcon, SlackIcon, StartIcon, TableIcon } from '@/components/icons'
import { StageBlockCard } from '@/app/(landing)/components/hero/components/hero-platform-loop/stage-block-card'
import type { BlockDef } from '@/app/(landing)/components/hero/components/hero-visual/workflow-data'
import { WorkflowEdgeView } from '@sim/workflow-renderer'
import type { EdgeRunStatus } from '@sim/workflow-renderer'
import { layoutRuntimeGraph } from '../runtime-graph-layout'

interface RuntimeGraphProps {
  taskId: string
  workflowState?: Record<string, unknown> | null
}

function blockState(data: Record<string, unknown>) {
  return String(data.executionState ?? data.status ?? 'not-executed')
}

function runtimeIcon(type: string) {
  if (type.includes('start') || type === 'trigger') return StartIcon
  if (type.includes('table')) return TableIcon
  if (type.includes('slack')) return SlackIcon
  if (type.includes('code') || type.includes('function')) return CodeIcon
  return AgentIcon
}

function runtimeRows(block: Record<string, unknown>) {
  const rows = block.rows
  if (Array.isArray(rows)) {
    return rows.slice(0, 4).map((row) => {
      const item = (row ?? {}) as Record<string, unknown>
      return { title: String(item.title ?? item.label ?? '详情'), value: String(item.value ?? '-') }
    })
  }
  const metadata = (block.metadata ?? block.data) as Record<string, unknown> | undefined
  return Object.entries(metadata ?? {})
    .filter(([key]) => !['step', 'planTaskId', 'namespace', 'primitive'].includes(key))
    .slice(0, 3)
    .map(([title, value]) => ({ title, value: typeof value === 'string' ? value : '-' }))
}

function RuntimeNode({ id, data }: NodeProps) {
  const block = (data.block ?? {}) as Record<string, unknown>
  const status = blockState(block)
  const type = String(block.type ?? block.primitive ?? 'agent')
  const presentation: BlockDef = {
    id,
    name: String(block.name ?? block.step ?? id),
    icon: runtimeIcon(type),
    bgColor: type.includes('slack') ? '#611F69' : type.includes('table') ? 'var(--text-body)' : 'var(--text-primary)',
    isTrigger: Boolean(data.isTrigger),
    isTerminal: Boolean(data.isTerminal),
    rows: runtimeRows(block),
    x: 0,
    y: 0,
  }
  const active = status === 'running' || status === 'retrying'
  const terminal = status === 'completed' || status === 'cached' || status === 'failed' || status === 'cancelled'
  return (
    <div className='relative' data-runtime-node-state={status}>
      <Handle type='target' position={Position.Top} id='target' className='!h-2 !w-5 !-top-1 !border-0 !bg-transparent !opacity-0' />
      <StageBlockCard block={presentation} />
      <Handle type='source' position={Position.Bottom} id='source' className='!h-2 !w-5 !-bottom-1 !border-0 !bg-transparent !opacity-0' />
      <span aria-hidden className={`pointer-events-none absolute inset-0 rounded-[13px] ring-[1.75px] ring-[var(--text-secondary)] transition-opacity duration-300 ${active || terminal ? 'opacity-100' : 'opacity-0'}`} />
    </div>
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
  const explicitEdges = rawEdges
    .map((edge) => ({ id: String(edge.id), source: String(edge.source), target: String(edge.target), data: edge.data as Record<string, unknown> | undefined }))
    .filter((edge) => edge.id && edge.source && edge.target)
  const edges = useMemo(() => {
    const next = [...explicitEdges]
    const known = new Set(next.map((edge) => `${edge.source}->${edge.target}`))
    for (const [target, block] of Object.entries(blocks)) {
      const dependencies = block.depends_on ?? block.dependsOn ?? (block.data as Record<string, unknown> | undefined)?.depends_on
      if (!Array.isArray(dependencies)) continue
      for (const dependency of dependencies) {
        const source = String(dependency)
        const key = `${source}->${target}`
        if (!blocks[source] || known.has(key)) continue
        known.add(key)
        next.push({ id: `runtime-dependency-${source}-${target}`, source, target, data: { kind: 'dependency' } })
      }
    }
    return next
  }, [blocks, explicitEdges])
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
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      data: {
        block,
        workflowRunning: running,
        isTrigger: !edges.some((edge) => edge.target === id),
        isTerminal: !edges.some((edge) => edge.source === id),
      },
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
    <div className='h-full w-full overflow-auto bg-[var(--surface-1)]'>
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={flowEdges}
          nodeTypes={{ lingxiRuntimeNode: RuntimeNode }}
          edgeTypes={{ lingxiRuntimeEdge: RuntimeEdge }}
          fitView
          fitViewOptions={{ padding: 0.08, maxZoom: 0.71 }}
          defaultViewport={{ x: 0, y: 0, zoom: 0.71 }}
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
