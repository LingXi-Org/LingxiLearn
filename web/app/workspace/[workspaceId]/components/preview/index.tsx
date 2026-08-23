'use client'

import type { ReactNode } from 'react'
import { useMemo } from 'react'
import ReactFlow, { type Node, type NodeProps, ReactFlowProvider } from 'reactflow'
import 'reactflow/dist/style.css'
import { Sparkles } from '@/components/ui-kit/icons'
import { WorkflowBlockView } from '@/components/workflow'
import type { WorkflowState } from '@/stores/workflows/workflow/types'

/** Read-only compatibility surface for log/table consumers. The editable
 * workflow preview was intentionally removed; logs expose an audit summary. */
export function Preview({
  className,
  height,
  width,
  children,
  workflowState,
}: {
  className?: string
  height?: string | number
  width?: string | number
  children?: ReactNode
  workflowState?: WorkflowState
  [key: string]: unknown
}) {
  if (workflowState?.blocks) {
    return (
      <ReadOnlyFlow
        workflowState={workflowState}
        className={className}
        height={height}
        width={width}
      />
    )
  }
  return (
    <div className={className} style={{ height, width }}>
      {children ?? <div className='p-4 text-sm text-[var(--text-muted)]'>只读执行快照</div>}
    </div>
  )
}

function ReadOnlyBlock({ id, data }: NodeProps) {
  const block = data.block as Record<string, unknown>
  const status = String(block.status ?? 'not-executed')
  return (
    <WorkflowBlockView
      id={id}
      type={String(block.type ?? 'agent')}
      name={String(block.name ?? id)}
      isEnabled={block.enabled !== false}
      isLocked
      hasRing={status === 'running' || status === 'retrying'}
      ringStyles=''
      runPathStatus={status === 'completed' ? 'success' : status === 'failed' ? 'error' : undefined}
      isExecutionHighlighted={status !== 'not-executed'}
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
      typeLabel={String(block.type ?? 'agent')}
    />
  )
}

function ReadOnlyFlow({
  workflowState,
  className,
  height,
  width,
}: {
  workflowState: WorkflowState
  className?: string
  height?: string | number
  width?: string | number
}) {
  const nodes = useMemo<Node[]>(
    () =>
      Object.entries(workflowState.blocks ?? {}).map(([id, block]) => ({
        id,
        type: 'lingxiReadOnlyBlock',
        position: block.position ?? { x: 0, y: 0 },
        data: { block },
        draggable: false,
        selectable: false,
      })),
    [workflowState.blocks]
  )
  const edges = useMemo(
    () =>
      (workflowState.edges ?? []).map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        animated: false,
        selectable: false,
      })),
    [workflowState.edges]
  )
  return (
    <div className={className} style={{ height, width }}>
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={{ lingxiReadOnlyBlock: ReadOnlyBlock }}
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

export function PreviewWorkflow(props: Record<string, unknown>) {
  const workflowState = props.workflowState as WorkflowState | undefined
  if (!workflowState?.blocks) return <Preview {...props} />
  return (
    <ReadOnlyFlow
      workflowState={workflowState}
      className={props.className as string}
      height={props.height as string | number}
      width={props.width as string | number}
    />
  )
}
