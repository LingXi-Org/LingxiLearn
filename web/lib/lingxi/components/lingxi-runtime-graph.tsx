'use client'

import { type ComponentType, type ReactNode, useEffect, useMemo, useRef, useState } from 'react'
import ReactFlow, {
  type EdgeProps,
  type Node,
  type NodeProps,
  Position,
  type ReactFlowInstance,
  ReactFlowProvider,
} from 'reactflow'
import 'reactflow/dist/style.css'
import {
  type EdgeRunStatus,
  SubBlockRowView,
  WorkflowBlockView,
  WorkflowEdgeView,
} from '@sim/workflow-renderer'
import { AgentIcon, CodeIcon, SlackIcon, StartIcon, TableIcon } from '@/components/icons'
import { applyAutoLayout } from '@/lib/workflows/autolayout'
import {
  projectRuntimeGraph,
  type RuntimeBlockState,
  runtimeDisplayName,
  runtimeEdgeStatus,
  runtimeIconType,
  runtimeStatusToRunPath,
  runtimeTypeLabel,
} from '../runtime-graph-adapter'
import type { AgentTaskEvent } from '../types'

interface RuntimeGraphProps {
  taskId: string
  workflowState?: Record<string, unknown> | null
  events?: AgentTaskEvent[]
}

interface RuntimeNodeData {
  block: RuntimeBlockState
  workflowRunning: boolean
}

interface RuntimeEdgeData {
  runStatus?: EdgeRunStatus
  isTargetActive?: boolean
  isWorkflowRunning?: boolean
}

const runtimeNodeTypes = { lingxiRuntimeNode: RuntimeNode }
const runtimeEdgeTypes = { lingxiRuntimeEdge: RuntimeEdge }
const nativeCanvasClassName = [
  '[&_.react-flow__handle]:!z-[30]',
  '[&_.react-flow__handle]:!pointer-events-none',
  '[&_.react-flow__handle]:!invisible',
  '[&_.react-flow__handle]:!hidden',
  '[&_.workflow-drag-handle>svg]:!hidden',
  '[&_.react-flow__pane]:select-none',
  '[&_.react-flow__selectionpane]:select-none',
  String.raw`[&_.react-flow\_\_selection]:!border-[var(--text-secondary)]`,
  String.raw`[&_.react-flow\_\_selection]:!bg-[color-mix(in_oklch,var(--text-secondary)_8%,transparent)]`,
  '[&_.react-flow__background]:hidden',
].join(' ')

function runtimeIcon(block: RuntimeBlockState): ComponentType<{ className?: string }> {
  const type = runtimeIconType(block).toLowerCase()
  if (type.includes('start') || type.includes('trigger') || type.includes('input')) return StartIcon
  if (type.includes('table')) return TableIcon
  if (type.includes('slack')) return SlackIcon
  if (type.includes('code') || type.includes('function')) return CodeIcon
  return AgentIcon
}

function runtimeRows(block: RuntimeBlockState): ReactNode {
  if (block.runtimeRows.length === 0) return null
  return block.runtimeRows.map((row) => (
    <SubBlockRowView key={`${row.title}:${row.value}`} title={row.title} displayValue={row.value} />
  ))
}

function RuntimeNode({ id, data }: NodeProps<RuntimeNodeData>) {
  const { block, workflowRunning } = data
  const active = block.executionState === 'running' || block.executionState === 'retrying'
  const pending = block.executionState === 'queued' || block.executionState === 'pending'
  // Router V2 is a real Sim block type, but its native view reserves source
  // ports for configured route rows.  The runtime control node has one
  // collapsed output, so render it through the ordinary native card topology
  // while retaining the control type in the projected BlockState metadata.
  const nativeType = block.data.runtimeKind === 'control' ? 'agent' : runtimeIconType(block)
  return (
    <WorkflowBlockView
      id={id}
      type={nativeType}
      name={runtimeDisplayName(block)}
      isPending={pending}
      isEnabled={block.enabled}
      isLocked={false}
      hasRing={false}
      ringStyles=''
      runPathStatus={runtimeStatusToRunPath(block.executionState)}
      isRunning={active}
      isWorkflowRunning={workflowRunning}
      isExecutionHighlighted={active}
      Icon={runtimeIcon(block)}
      iconBgColor='var(--text-primary)'
      horizontalHandles
      shouldShowDefaultHandles
      blockHeight={block.height}
      hasContentBelowHeader={block.runtimeRows.length > 0}
      conditionRows={[]}
      routerRows={[]}
      wouldCreateConnectionCycle={() => false}
      onSelect={() => {}}
      rows={runtimeRows(block)}
      typeLabel={runtimeTypeLabel(block)}
      hasErrorConnection={false}
      errorOutputEnabled={false}
    />
  )
}

function RuntimeEdge(props: EdgeProps) {
  const data = (props.data ?? {}) as RuntimeEdgeData
  return (
    <WorkflowEdgeView
      {...props}
      diffStatus={null}
      runStatus={data.runStatus ?? 'not-executed'}
      isPreviewRun={false}
      isWorkflowRunning={Boolean(data.isWorkflowRunning)}
      isTargetActive={Boolean(data.isTargetActive)}
      isConnectedToSelection={false}
    />
  )
}

export function LingxiRuntimeGraph({ taskId, workflowState, events = [] }: RuntimeGraphProps) {
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance | null>(null)
  const projection = useMemo(
    () => projectRuntimeGraph(workflowState, events),
    [events, workflowState]
  )
  const layoutSignature = useMemo(
    () =>
      [
        ...Object.values(projection.blocks)
          .map(
            (block) =>
              `${block.id}:${block.type}:${block.height ?? ''}:${block.data.parentId ?? ''}`
          )
          .sort(),
        ...projection.edges
          .map(
            (edge) =>
              `${edge.id}:${edge.source}:${edge.sourceHandle ?? ''}->${edge.target}:${edge.targetHandle ?? ''}`
          )
          .sort(),
      ].join('|'),
    [projection.blocks, projection.edges]
  )
  const layout = useMemo(
    () => applyAutoLayout(projection.blocks, projection.edges),
    // Execution status changes must not recalculate or write positions.  The
    // native layout is recomputed only when the projected topology changes.
    [layoutSignature]
  )
  const laidOutBlocks = useMemo(() => {
    const positioned = (layout.success ? layout.blocks : projection.blocks) as Record<
      string,
      RuntimeBlockState
    >
    return Object.fromEntries(
      Object.entries(projection.blocks).map(([id, block]) => [
        id,
        {
          ...block,
          position: positioned[id]?.position ?? block.position,
        },
      ])
    ) as Record<string, RuntimeBlockState>
  }, [layout.blocks, layout.success, projection.blocks])
  const nodes = useMemo<Node<RuntimeNodeData>[]>(
    () =>
      Object.values(laidOutBlocks).map((block) => ({
        id: block.id,
        type: 'lingxiRuntimeNode',
        position: block.position,
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        data: { block, workflowRunning: projection.running },
        draggable: false,
        selectable: false,
      })),
    [laidOutBlocks, projection.running]
  )
  const edges = useMemo(
    () =>
      projection.edges.map((edge) => {
        const source = laidOutBlocks[edge.source]
        const target = laidOutBlocks[edge.target]
        return {
          ...edge,
          type: 'lingxiRuntimeEdge',
          data: {
            ...(edge.data ?? {}),
            runStatus: runtimeEdgeStatus(source, target, edge.data?.status),
            isTargetActive:
              target?.executionState === 'running' || target?.executionState === 'retrying',
            isWorkflowRunning: projection.running,
          } satisfies RuntimeEdgeData,
          selectable: false,
        }
      }),
    [laidOutBlocks, projection.edges, projection.running]
  )

  const hasFittedView = useRef(false)
  useEffect(() => {
    if (!flowInstance || nodes.length === 0) return
    if (hasFittedView.current) return
    hasFittedView.current = true
    const frame = requestAnimationFrame(() => {
      void flowInstance.fitView({ padding: 0.15, minZoom: 0.1, maxZoom: 0.85, duration: 180 })
    })
    return () => cancelAnimationFrame(frame)
  }, [flowInstance, nodes.length])

  if (!taskId) return <div className='p-6 text-sm text-[var(--text-muted)]'>暂无运行任务。</div>
  if (nodes.length === 0) {
    return (
      <div className='flex h-full items-center justify-center text-sm text-[var(--text-muted)]'>
        等待运行图节点…
      </div>
    )
  }

  return (
    <div className='relative h-full w-full overflow-hidden bg-[var(--surface-1)]'>
      {projection.latestStatusText && (
        <div className='pointer-events-none absolute left-4 right-4 top-3 z-10 rounded-lg border border-[var(--border-1)] bg-[var(--surface-2)]/95 px-3 py-2 text-xs text-[var(--text-body)] shadow-sm'>
          {projection.latestStatusText}
        </div>
      )}
      <ReactFlowProvider>
        <ReactFlow
          className={nativeCanvasClassName}
          nodes={nodes}
          edges={edges}
          nodeTypes={runtimeNodeTypes}
          edgeTypes={runtimeEdgeTypes}
          onInit={setFlowInstance}
          defaultEdgeOptions={{ type: 'lingxiRuntimeEdge' }}
          fitViewOptions={{ padding: 0.15, minZoom: 0.1, maxZoom: 0.85 }}
          defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
          minZoom={0.1}
          maxZoom={0.85}
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
