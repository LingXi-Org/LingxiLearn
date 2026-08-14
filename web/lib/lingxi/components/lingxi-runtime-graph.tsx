'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import ReactFlow, {
  EdgeLabelRenderer,
  Handle,
  ReactFlowProvider,
  type EdgeProps,
  type Node,
  type NodeProps,
  Position,
  type ReactFlowInstance,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { AgentIcon, CodeIcon, SlackIcon, StartIcon, TableIcon } from '@/components/icons'
import { StageBlockCard } from '@/app/(landing)/components/hero/components/hero-platform-loop/stage-block-card'
import type { BlockDef } from '@/app/(landing)/components/hero/components/hero-visual/workflow-data'
import type { EdgeRunStatus } from '@sim/workflow-renderer'
import { verticalSmoothStep } from '@/app/(landing)/components/hero/components/hero-platform-loop/stage-data'
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
  const metadata = (block.metadata ?? block.data) as Record<string, unknown> | undefined
  if (metadata) {
    const rows: Array<{ title: string; value: string }> = []
    rows.push({
      title: 'Role',
      value: metadata.nodeKind === 'deterministic' ? 'Deterministic execution' : 'Agent / Provider',
    })
    if (metadata.capability) rows.push({ title: 'Capability', value: String(metadata.capability) })
    if (metadata.provider) rows.push({ title: 'Provider', value: String(metadata.provider) })
    if (metadata.knowledgePointId) rows.push({ title: 'Learning target', value: String(metadata.knowledgePointId) })
    if (metadata.doneWhen) rows.push({ title: 'Done when', value: String(metadata.doneWhen) })
    if (rows.length > 1) return rows.slice(0, 4)
  }
  const rows = block.rows
  if (Array.isArray(rows)) {
    return rows.slice(0, 4).map((row) => {
      const item = (row ?? {}) as Record<string, unknown>
      return { title: String(item.title ?? item.label ?? '详情'), value: String(item.value ?? '-') }
    })
  }
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
  const data = (props.data ?? {}) as { runStatus?: EdgeRunStatus; isTargetActive?: boolean; label?: string }
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const frame = requestAnimationFrame(() => setVisible(true))
    return () => cancelAnimationFrame(frame)
  }, [])
  const runStatus = data.runStatus
  const stroke = runStatus === 'error'
    ? 'var(--text-error)'
    : runStatus === 'success'
      ? 'var(--border-success)'
      : 'var(--workflow-edge)'
  const edgePath = verticalSmoothStep(props.sourceX, props.sourceY, props.targetX, props.targetY)
  const labelX = (props.sourceX + props.targetX) / 2
  const labelY = (props.sourceY + props.targetY) / 2
  return (
    <>
      <path
        d={edgePath}
        pathLength={1}
        fill='none'
        stroke={stroke}
        strokeWidth={2}
        strokeLinecap='round'
        className='transition-[stroke-dashoffset,stroke] duration-500 [stroke-dasharray:1] [transition-timing-function:cubic-bezier(0.22,1,0.36,1)]'
        style={{
          strokeDashoffset: visible ? 0 : 1,
          opacity: data.isTargetActive ? 1 : 0.9,
        }}
      />
      {data.label && (
        <EdgeLabelRenderer>
          <div
            className='pointer-events-none absolute rounded-full border border-[var(--border-1)] bg-[var(--surface-2)] px-2 py-0.5 text-[11px] text-[var(--text-muted)] shadow-sm'
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)` }}
          >
            {data.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

interface CapabilityPresentation {
  label: string
  type: 'agent' | 'function'
  nodeKind: 'agent' | 'deterministic'
}

const CAPABILITY_PRESENTATIONS = new Map<string, CapabilityPresentation>()
const registerCapability = (
  presentation: CapabilityPresentation,
  aliases: string[]
) => aliases.forEach((alias) => CAPABILITY_PRESENTATIONS.set(alias.toLowerCase(), presentation))

registerCapability({ label: 'Tutor', type: 'agent', nodeKind: 'agent' }, [
  'Tutor', 'tutor', 'answer_user', 'dialog.answer', 'teach.explain', 'dialog.negotiate', 'negotiator',
])
registerCapability({ label: 'Adaptive Tutor', type: 'agent', nodeKind: 'agent' }, [
  'Adaptive Tutor', 'adaptive_tutor', 'adaptive_pedagogy', 'teach.strategy',
])
registerCapability({ label: 'Lesson Intro', type: 'agent', nodeKind: 'agent' }, [
  'Lesson Intro', 'lesson_intro', 'content.lesson_intro', 'lecture_hook',
])
registerCapability({ label: 'Lecture Deck', type: 'agent', nodeKind: 'agent' }, [
  'Lecture Deck', 'lecture_deck', 'content.deck', 'interactive_lecture_deck',
])
registerCapability({ label: 'Visual Explainer', type: 'agent', nodeKind: 'agent' }, [
  'Visual Explainer', 'visual_explainer', 'content.visual', 'interactive_visual_explainer',
])
registerCapability({ label: 'Quiz Generator', type: 'agent', nodeKind: 'agent' }, [
  'Quiz Generator', 'quiz_generator', 'assess.generate',
])
registerCapability({ label: 'Formative Assessor', type: 'agent', nodeKind: 'agent' }, [
  'Formative Assessor', 'formative_assessor', 'assess.interpret',
])
registerCapability({ label: 'Retrieval Practice', type: 'agent', nodeKind: 'agent' }, [
  'Retrieval Practice', 'retrieval_practice', 'review_scheduler', 'review.schedule',
])
registerCapability({ label: 'Curriculum Mapper', type: 'agent', nodeKind: 'agent' }, [
  'Curriculum Mapper', 'curriculum_mapper', 'prerequisite_analyzer', 'graph.build', 'graph.prerequisite',
])
registerCapability({ label: 'Learner Reflector', type: 'agent', nodeKind: 'agent' }, [
  'Learner Reflector', 'learner_reflector', 'learner_state_reflector', 'model.reflect',
])
registerCapability({ label: 'Investigator', type: 'agent', nodeKind: 'agent' }, [
  'Investigator', 'investigator', 'pack_investigate', 'tool.investigate', 'web_search', 'web_fetch',
])
registerCapability({ label: 'Learning Reporter', type: 'agent', nodeKind: 'agent' }, [
  'Learning Reporter', 'learning_reporter', 'pack_report', 'meta.report',
])
registerCapability({ label: 'Skill Forge', type: 'agent', nodeKind: 'agent' }, [
  'Skill Forge', 'skill_forge', 'meta.author_skill',
])
registerCapability({ label: 'Knowledge Probe', type: 'function', nodeKind: 'deterministic' }, [
  'Knowledge Probe', 'knowledge_probe', 'pack_probe', 'knowledge.search', 'kb.search',
])
registerCapability({ label: 'Deterministic Grader', type: 'function', nodeKind: 'deterministic' }, [
  'Deterministic Grader', 'deterministic_grader', 'assess.grade', 'quiz_submit',
])

function capabilityPresentation(block: Record<string, unknown>): CapabilityPresentation | null {
  const data = (block.data ?? {}) as Record<string, unknown>
  const candidates = [data.provider, data.primitive, data.capability, block.name]
  for (const candidate of candidates) {
    const presentation = CAPABILITY_PRESENTATIONS.get(String(candidate ?? '').toLowerCase())
    if (presentation) return presentation
  }
  return null
}

function semanticGraph(
  rawBlocks: Record<string, Record<string, unknown>>,
  rawEdges: Array<Record<string, unknown>>
) {
  const blocks = Object.fromEntries(
    Object.entries(rawBlocks).flatMap(([id, block]) => {
      const presentation = capabilityPresentation(block)
      if (!presentation) return []
      const data = (block.data ?? {}) as Record<string, unknown>
      return [[id, {
        ...block,
        name: presentation.label,
        type: presentation.type,
        rows: runtimeRows(block),
        data: { ...data, nodeKind: presentation.nodeKind },
      }]]
    })
  ) as Record<string, Record<string, unknown>>
  const visible = new Set(Object.keys(blocks))
  const parsed = rawEdges
    .map((edge) => ({
      id: String(edge.id ?? ''),
      source: String(edge.source ?? ''),
      target: String(edge.target ?? ''),
      data: (edge.data ?? {}) as Record<string, unknown>,
      label: String(edge.label ?? (edge.data as Record<string, unknown> | undefined)?.label ?? ''),
    }))
    .filter((edge) => edge.source && edge.target)
  const outgoing = new Map<string, typeof parsed>()
  parsed.forEach((edge) => outgoing.set(edge.source, [...(outgoing.get(edge.source) ?? []), edge]))
  const edges: typeof parsed = []
  const seen = new Set<string>()

  for (const source of visible) {
    const queue = (outgoing.get(source) ?? []).map((edge) => ({ edge, collapsed: false }))
    const visitedHidden = new Set<string>()
    while (queue.length > 0) {
      const { edge, collapsed } = queue.shift()!
      if (visible.has(edge.target)) {
        if (edge.target === source) continue
        const key = `${source}->${edge.target}`
        if (seen.has(key)) continue
        seen.add(key)
        edges.push({
          ...edge,
          id: collapsed ? `runtime-collapse-${source}-${edge.target}` : edge.id,
          source,
          label: collapsed ? 'Lingxi Runtime' : edge.label || 'Capability dependency',
          data: {
            ...edge.data,
            label: collapsed ? 'Lingxi Runtime' : edge.label || 'Capability dependency',
          },
        })
        continue
      }
      if (visitedHidden.has(edge.target)) continue
      visitedHidden.add(edge.target)
      for (const next of outgoing.get(edge.target) ?? []) queue.push({ edge: next, collapsed: true })
    }
  }
  return { blocks, edges }
}

export function LingxiRuntimeGraph({ taskId, workflowState }: RuntimeGraphProps) {
  const previousPositions = useRef<Record<string, { x: number; y: number }>>({})
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance | null>(null)
  const graph = workflowState ?? {}
  const rawBlocks = (graph.blocks ?? {}) as Record<string, Record<string, unknown>>
  const rawEdges = (graph.edges ?? []) as Array<Record<string, unknown>>
  const semantic = useMemo(() => semanticGraph(rawBlocks, rawEdges), [rawBlocks, rawEdges])
  const blocks = semantic.blocks
  const explicitEdges = semantic.edges
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
        data: {
          runStatus,
          label: String(edge.data?.label ?? edge.label ?? 'Capability dependency'),
          isTargetActive: targetStatus === 'running' || targetStatus === 'retrying',
          isWorkflowRunning: running,
        },
        selectable: false,
      }
    }),
    [blocks, edges, running]
  )
  const topologySignature = useMemo(
    () => [
      ...Object.keys(blocks).sort(),
      ...edges.map((edge) => `${edge.source}->${edge.target}`).sort(),
    ].join('|'),
    [blocks, edges]
  )
  useEffect(() => {
    if (!flowInstance || nodes.length === 0) return
    const frame = requestAnimationFrame(() => {
      void flowInstance.fitView({ padding: 0.12, minZoom: 0.1, maxZoom: 1.2, duration: 420 })
    })
    return () => cancelAnimationFrame(frame)
  }, [flowInstance, nodes.length, topologySignature])

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
          onInit={setFlowInstance}
          fitView
          fitViewOptions={{ padding: 0.12, minZoom: 0.1, maxZoom: 1.2 }}
          defaultViewport={{ x: 0, y: 0, zoom: 0.71 }}
          minZoom={0.1}
          maxZoom={1.2}
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
