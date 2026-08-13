'use client'

import { useMemo } from 'react'
import type { Edge } from 'reactflow'
import Workflow from '@/app/workspace/[workspaceId]/w/[workflowId]/workflow'
import { useAgentTask } from '@/lib/lingxi/hooks/use-agent-task'
import { agentTaskToCanvasGraph } from '@/lib/lingxi/lingxi-projection'
import type { AgentTaskSnapshot } from '@/lib/lingxi/types'
import { prepareBlockState } from '@/stores/workflows/utils'
import type { BlockState, WorkflowState } from '@/stores/workflows/workflow/types'
import type { WorkflowMetadata } from '@/stores/workflows/registry/types'

export function lingxiWorkflowId(taskId: string): string {
  return `lingxi-task-${taskId}`
}

export function lingxiTaskId(workflowId: string): string {
  return workflowId.startsWith('lingxi-task-') ? workflowId.slice('lingxi-task-'.length) : ''
}

function toWorkflowState(task: AgentTaskSnapshot, events: Parameters<typeof agentTaskToCanvasGraph>[1]): WorkflowState {
  const graph = agentTaskToCanvasGraph(task, events)
  const blocks: Record<string, BlockState> = {}

  graph.nodes.forEach((node, index) => {
    const block = prepareBlockState({
      id: node.id,
      type: node.kind === 'agent' ? 'agent' : 'note',
      name: node.label,
      position: { x: (index % 3) * 360, y: Math.floor(index / 3) * 220 },
    })
    block.locked = true
    if (node.kind === 'agent') {
      const messages = block.subBlocks.messages
      if (messages) {
        messages.value = [{ role: 'user', content: `${node.detail}\n\n状态：${node.status}` }]
      }
    } else {
      block.subBlocks.content.value = `${node.detail}\n\n状态：${node.status}`
    }
    blocks[node.id] = block
  })

  const edges: Edge[] = graph.edges.map((edge, index) => ({
    id: `lingxi-edge-${index}-${edge.from}-${edge.to}`,
    source: edge.from,
    target: edge.to,
    sourceHandle: 'source',
    targetHandle: 'target',
    type: 'workflowEdge',
    data: { label: edge.label },
  }))

  return {
    currentWorkflowId: lingxiWorkflowId(task.id),
    blocks,
    edges,
    loops: {},
    parallels: {},
    lastSaved: Date.now(),
  }
}

export function LingxiWorkflow({ taskId, embedded = true }: { taskId: string; embedded?: boolean }) {
  const { task, events, loading, error } = useAgentTask(taskId)
  const workflowState = useMemo(
    () => (task ? toWorkflowState(task, events) : null),
    [events, task]
  )
  const metadata = useMemo<WorkflowMetadata>(
    () => ({
      id: lingxiWorkflowId(taskId),
      name: 'Lingxi 智能体编排图',
      workspaceId: 'lingxi',
      lastModified: new Date(),
      createdAt: new Date(),
      sortOrder: 0,
      locked: true,
    }),
    [taskId]
  )

  if (loading && !task) return <div className='flex h-full items-center justify-center text-sm text-[var(--text-secondary)]'>正在加载智能体编排图…</div>
  if (error && !task) return <div className='flex h-full items-center justify-center text-sm text-[var(--text-error)]'>{error}</div>
  if (!workflowState) return null

  return (
    <Workflow
      workspaceId='lingxi'
      workflowId={lingxiWorkflowId(taskId)}
      embedded={embedded}
      initialWorkflowState={workflowState}
      initialWorkflowMetadata={metadata}
    />
  )
}
