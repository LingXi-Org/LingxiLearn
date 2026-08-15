'use client'

import { useEffect, useMemo, useRef, useState, type SVGProps } from 'react'
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
import type { AgentTaskEvent } from '../types'
import { layoutRuntimeGraph } from '../runtime-graph-layout'

interface RuntimeGraphProps {
  taskId: string
  workflowState?: Record<string, unknown> | null
  events?: AgentTaskEvent[]
}

const DICEBEAR_SKILL_ICON = 'https://api.dicebear.com/10.x/rings/svg?seed=pbqpdi5z'

function DiceBearSkillIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" {...props}>
      <image
        href={DICEBEAR_SKILL_ICON}
        width="24"
        height="24"
        preserveAspectRatio="xMidYMid slice"
      />
    </svg>
  )
}

function blockState(data: Record<string, unknown>) {
  return String(data.executionState ?? data.status ?? 'not-executed')
}

function runtimeIcon(type: string) {
  if (type.includes('start') || type === 'trigger' || type === 'input' || type === 'intent') return StartIcon
  if (type.includes('table')) return TableIcon
  if (type.includes('slack')) return SlackIcon
  if (type.includes('code') || type.includes('function')) return CodeIcon
  return AgentIcon
}

/**
 * Orthogonal path for bottom-to-top handles. Forward edges use a midpoint;
 * back-edges (possible when a runtime cycle is collapsed) detour below both
 * cards so the quadratic corners never receive a negative radius direction.
 */
function verticalSmoothStep(sx: number, sy: number, tx: number, ty: number, radius = 10): string {
  const horizontalDistance = Math.abs(tx - sx)
  if (horizontalDistance < 1 && ty >= sy) return `M ${sx} ${sy} L ${tx} ${ty}`
  const safeRadius = Math.min(
    radius,
    Math.max(4, Math.abs(ty - sy) / 4),
    Math.max(4, horizontalDistance / 4 || radius)
  )
  const direction = tx >= sx ? 1 : -1
  const routeY = ty > sy ? (sy + ty) / 2 : Math.max(sy, ty) + Math.max(34, safeRadius * 3)
  return [
    `M ${sx} ${sy}`,
    `L ${sx} ${routeY - safeRadius}`,
    `Q ${sx} ${routeY} ${sx + direction * safeRadius} ${routeY}`,
    `L ${tx - direction * safeRadius} ${routeY}`,
    `Q ${tx} ${routeY} ${tx} ${routeY + safeRadius}`,
    `L ${tx} ${ty}`,
  ].join(' ')
}

function runtimeRows(block: Record<string, unknown>) {
  const metadata = (block.metadata ?? block.data) as Record<string, unknown> | undefined
  if (metadata) {
    const rows: Array<{ title: string; value: string }> = []
    rows.push({
      title: '节点类型',
      value: metadata.controlPlane
        ? '大模型控制面'
        : metadata.nodeKind === 'deterministic'
          ? '确定性执行'
          : metadata.nodeKind === 'input'
            ? '用户输入'
            : '智能体 / 服务提供方',
    })
    if (metadata.capability)
      rows.push({
        title: '能力',
        value: runtimeLabel(metadata.capability),
        valueIcon: DiceBearSkillIcon,
      })
    if (metadata.provider)
      rows.push({ title: '服务提供方', value: runtimeLabel(metadata.provider) })
    if (metadata.knowledgePointId)
      rows.push({ title: '学习目标', value: String(metadata.knowledgePointId) })
    if (metadata.doneWhen) rows.push({ title: '完成条件', value: runtimeLabel(metadata.doneWhen) })
    if (rows.length > 1) return rows.slice(0, 4)
  }
  const rows = block.rows
  if (Array.isArray(rows)) {
    return rows.slice(0, 4).map((row) => {
      const item = (row ?? {}) as Record<string, unknown>
      return {
        title: runtimeLabel(item.title ?? item.label ?? '详情'),
        value: runtimeLabel(item.value ?? '-'),
        ...(String(item.title ?? item.label ?? '')
          .toLowerCase()
          .includes('skill')
          ? { valueIcon: DiceBearSkillIcon }
          : {}),
      }
    })
  }
  return Object.entries(metadata ?? {})
    .filter(([key]) => !['step', 'planTaskId', 'namespace', 'primitive'].includes(key))
    .slice(0, 3)
    .map(([title, value]) => ({ title: runtimeLabel(title), value: runtimeLabel(value) }))
}

const RUNTIME_LABELS: Record<string, string> = {
  Role: '节点类型',
  Capability: '能力',
  Provider: '服务提供方',
  'Learning target': '学习目标',
  'Done when': '完成条件',
  'Agent / Provider': '智能体 / 服务提供方',
  'Deterministic execution': '确定性执行',
  'Capability dependency': '能力依赖',
  'Lingxi Runtime': '灵析运行时',
  running: '运行中',
  retrying: '重试中',
  completed: '已完成',
  cached: '已缓存',
  failed: '失败',
  cancelled: '已取消',
  pending: '等待中',
}

const CAPABILITY_LABELS: Record<string, string> = {
  Tutor: '辅导老师',
  tutor: '辅导老师',
  answer_user: '回答用户',
  'dialog.answer': '回答对话',
  'dialog.converse': '实时陪聊',
  'dialog.probe': '苏格拉底追问',
  'teach.explain': '讲解知识',
  'dialog.negotiate': '协商目标',
  'Adaptive Tutor': '自适应辅导',
  adaptive_tutor: '自适应辅导',
  adaptive_pedagogy: '自适应教学',
  'teach.strategy': '教学策略',
  'Lesson Intro': '课程导入',
  lesson_intro: '课程导入',
  'content.lesson_intro': '课程导入',
  lecture_hook: '课程引入',
  'Lecture Deck': '讲解课件',
  lecture_deck: '讲解课件',
  'content.deck': '讲解课件',
  interactive_lecture_deck: '交互式课件',
  'Visual Explainer': '可视化讲解',
  visual_explainer: '可视化讲解',
  'content.visual': '可视化内容',
  interactive_visual_explainer: '交互式可视化讲解',
  'Quiz Generator': '测验生成',
  quiz_generator: '测验生成',
  'assess.generate': '生成测验',
  'Formative Assessor': '形成性评估',
  formative_assessor: '形成性评估',
  'assess.interpret': '解读评估',
  'Retrieval Practice': '检索练习',
  retrieval_practice: '检索练习',
  review_scheduler: '复习调度',
  'review.schedule': '安排复习',
  'Curriculum Mapper': '课程图谱',
  curriculum_mapper: '课程图谱',
  prerequisite_analyzer: '前置知识分析',
  'graph.build': '构建课程图谱',
  'graph.prerequisite': '分析前置知识',
  'Learner Reflector': '学习者反思',
  learner_reflector: '学习者反思',
  learner_state_reflector: '学习状态反思',
  'model.reflect': '反思学习模型',
  Investigator: '资料调查',
  investigator: '资料调查',
  pack_investigate: '调查资料',
  'tool.investigate': '调用调查工具',
  web_search: '搜索资料',
  web_fetch: '获取资料',
  'Learning Reporter': '学习报告',
  learning_reporter: '学习报告',
  pack_report: '生成报告',
  'meta.report': '汇总报告',
  'Skill Forge': '技能工坊',
  skill_forge: '技能工坊',
  'meta.author_skill': '编写技能',
  'Knowledge Probe': '知识探查',
  knowledge_probe: '知识探查',
  pack_probe: '探查知识',
  'knowledge.search': '检索知识',
  'kb.search': '搜索知识库',
  'Deterministic Grader': '确定性评分',
  deterministic_grader: '确定性评分',
  'assess.grade': '评定答案',
  quiz_submit: '提交测验',
}

function runtimeLabel(value: unknown): string {
  const text = String(value ?? '-')
  if (CAPABILITY_LABELS[text]) return CAPABILITY_LABELS[text]
  if (RUNTIME_LABELS[text]) return RUNTIME_LABELS[text]
  const normalized = text
    .replace(/[-_.]+/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .trim()
  return RUNTIME_LABELS[normalized] ?? text
}

function RuntimeNode({ id, data }: NodeProps) {
  const block = (data.block ?? {}) as Record<string, unknown>
  const status = blockState(block)
  const type = String(block.type ?? block.primitive ?? 'agent')
  const presentation: BlockDef = {
    id,
    name: String(block.name ?? block.step ?? id),
    icon: runtimeIcon(type),
    bgColor: type.includes('slack')
      ? '#611F69'
      : type.includes('table')
        ? 'var(--text-body)'
        : 'var(--text-primary)',
    isTrigger: Boolean(data.isTrigger),
    isTerminal: Boolean(data.isTerminal),
    rows: runtimeRows(block),
    x: 0,
    y: 0,
  }
  const active = status === 'running' || status === 'retrying'
  const terminal =
    status === 'completed' || status === 'cached' || status === 'failed' || status === 'cancelled'
  return (
    <div className="relative w-[360px]" data-runtime-node-state={status}>
      <Handle
        type="target"
        position={Position.Top}
        id="target"
        className="!h-2 !w-5 !-top-1 !border-0 !bg-transparent !opacity-0"
      />
      <StageBlockCard block={presentation} />
      <Handle
        type="source"
        position={Position.Bottom}
        id="source"
        className="!h-2 !w-5 !-bottom-1 !border-0 !bg-transparent !opacity-0"
      />
      <span
        aria-hidden
        className={`pointer-events-none absolute inset-[-4px] rounded-[17px] transition-[opacity,box-shadow] duration-300 ${
          active
            ? 'animate-pulse border-2 border-blue-500 opacity-100 shadow-[0_0_0_3px_rgba(59,130,246,0.18),0_0_22px_rgba(59,130,246,0.32)]'
            : terminal
              ? 'border border-[var(--text-secondary)] opacity-70'
              : 'border border-transparent opacity-0'
        }`}
      />
    </div>
  )
}

const revealedRuntimeEdges = new Set<string>()

function RuntimeEdge(props: EdgeProps) {
  const data = (props.data ?? {}) as {
    runStatus?: EdgeRunStatus
    isTargetActive?: boolean
    label?: string
  }
  const [visible, setVisible] = useState(revealedRuntimeEdges.has(props.id))
  useEffect(() => {
    if (revealedRuntimeEdges.has(props.id)) {
      setVisible(true)
      return
    }
    const frame = requestAnimationFrame(() => setVisible(true))
    revealedRuntimeEdges.add(props.id)
    return () => cancelAnimationFrame(frame)
  }, [props.id])
  const runStatus = data.runStatus
  const stroke =
    runStatus === 'error'
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
        fill="none"
        stroke={stroke}
        strokeWidth={2}
        strokeLinecap="round"
        className="transition-[stroke-dashoffset,stroke] duration-700 [stroke-dasharray:1] [transition-timing-function:cubic-bezier(0.22,1,0.36,1)] motion-reduce:!transition-none"
        style={{
          strokeDashoffset: visible ? 0 : 1,
          opacity: data.isTargetActive ? 1 : 0.9,
        }}
      />
      {data.label && (
        <EdgeLabelRenderer>
          <div
            className="pointer-events-none absolute rounded-full border border-[var(--border-1)] bg-[var(--surface-2)] px-2 py-0.5 text-[11px] text-[var(--text-muted)] shadow-sm"
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
const registerCapability = (presentation: CapabilityPresentation, aliases: string[]) =>
  aliases.forEach((alias) => CAPABILITY_PRESENTATIONS.set(alias.toLowerCase(), presentation))

registerCapability({ label: 'Tutor', type: 'agent', nodeKind: 'agent' }, [
  'Tutor',
  'tutor',
  'answer_user',
  'dialog.answer',
  'teach.explain',
  'dialog.negotiate',
  'negotiator',
])
registerCapability({ label: '学习陪伴', type: 'agent', nodeKind: 'agent' }, [
  '学习陪伴',
  'learning_companion',
  'dialog.converse',
])
registerCapability({ label: '主动追问', type: 'agent', nodeKind: 'agent' }, [
  '主动追问',
  'probe_user',
  'dialog.probe',
])
registerCapability({ label: 'Adaptive Tutor', type: 'agent', nodeKind: 'agent' }, [
  'Adaptive Tutor',
  'adaptive_tutor',
  'adaptive_pedagogy',
  'teach.strategy',
])
registerCapability({ label: 'Lesson Intro', type: 'agent', nodeKind: 'agent' }, [
  'Lesson Intro',
  'lesson_intro',
  'content.lesson_intro',
  'lecture_hook',
])
registerCapability({ label: 'Lecture Deck', type: 'agent', nodeKind: 'agent' }, [
  'Lecture Deck',
  'lecture_deck',
  'content.deck',
  'interactive_lecture_deck',
])
registerCapability({ label: 'Visual Explainer', type: 'agent', nodeKind: 'agent' }, [
  'Visual Explainer',
  'visual_explainer',
  'content.visual',
  'interactive_visual_explainer',
])
registerCapability({ label: 'Quiz Generator', type: 'agent', nodeKind: 'agent' }, [
  'Quiz Generator',
  'quiz_generator',
  'assess.generate',
])
registerCapability({ label: 'Formative Assessor', type: 'agent', nodeKind: 'agent' }, [
  'Formative Assessor',
  'formative_assessor',
  'assess.interpret',
])
registerCapability({ label: 'Retrieval Practice', type: 'agent', nodeKind: 'agent' }, [
  'Retrieval Practice',
  'retrieval_practice',
  'review_scheduler',
  'review.schedule',
])
registerCapability({ label: 'Curriculum Mapper', type: 'agent', nodeKind: 'agent' }, [
  'Curriculum Mapper',
  'curriculum_mapper',
  'prerequisite_analyzer',
  'graph.build',
  'graph.prerequisite',
])
registerCapability({ label: 'Learner Reflector', type: 'agent', nodeKind: 'agent' }, [
  'Learner Reflector',
  'learner_reflector',
  'learner_state_reflector',
  'model.reflect',
])
registerCapability({ label: 'Investigator', type: 'agent', nodeKind: 'agent' }, [
  'Investigator',
  'investigator',
  'pack_investigate',
  'tool.investigate',
  'web_search',
  'web_fetch',
])
registerCapability({ label: 'Learning Reporter', type: 'agent', nodeKind: 'agent' }, [
  'Learning Reporter',
  'learning_reporter',
  'pack_report',
  'meta.report',
])
registerCapability({ label: 'Skill Forge', type: 'agent', nodeKind: 'agent' }, [
  'Skill Forge',
  'skill_forge',
  'meta.author_skill',
])
registerCapability({ label: 'Knowledge Probe', type: 'function', nodeKind: 'deterministic' }, [
  'Knowledge Probe',
  'knowledge_probe',
  'pack_probe',
  'knowledge.search',
  'kb.search',
])
registerCapability({ label: 'Deterministic Grader', type: 'function', nodeKind: 'deterministic' }, [
  'Deterministic Grader',
  'deterministic_grader',
  'assess.grade',
  'quiz_submit',
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
      return [
        [
          id,
          {
            ...block,
            name: runtimeLabel(presentation.label),
            type: presentation.type,
            rows: runtimeRows(block),
            data: { ...data, nodeKind: presentation.nodeKind },
          },
        ],
      ]
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
          // Backend event sequence numbers can change when a plan is
          // re-emitted. React Flow treats a changed edge id as a new edge and
          // restarts its growth animation, which is the source of the
          // flicker. The semantic endpoints are the stable identity here.
          id: `runtime-edge-${encodeURIComponent(source)}-${encodeURIComponent(edge.target)}`,
          source,
          label: collapsed ? '灵析运行时' : runtimeLabel(edge.label || 'Capability dependency'),
          data: {
            ...edge.data,
            label: collapsed ? '灵析运行时' : runtimeLabel(edge.label || 'Capability dependency'),
          },
        })
        continue
      }
      if (visitedHidden.has(edge.target)) continue
      visitedHidden.add(edge.target)
      for (const next of outgoing.get(edge.target) ?? [])
        queue.push({ edge: next, collapsed: true })
    }
  }
  return { blocks, edges }
}

export function LingxiRuntimeGraph({ taskId, workflowState, events = [] }: RuntimeGraphProps) {
  const previousPositions = useRef<Record<string, { x: number; y: number }>>({})
  const observedNodeIds = useRef(new Set<string>())
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance | null>(null)
  const graph = workflowState ?? {}
  const rawBlocks = (graph.blocks ?? {}) as Record<string, Record<string, unknown>>
  const rawEdges = (graph.edges ?? []) as Array<Record<string, unknown>>
  const semantic = useMemo(() => semanticGraph(rawBlocks, rawEdges), [rawBlocks, rawEdges])
  const blocks = useMemo(() => {
    const controls: Record<string, Record<string, unknown>> = {}
    let inputState = 'completed'
    const labels: Record<string, string> = {
      learning_plan_decision: '学习计划决策',
    }
    for (const event of events) {
      const agent = String(event.agent ?? '')
      if (agent === 'goal_interpreter' && ['model.started', 'model.completed', 'model.failed'].includes(event.kind)) {
        inputState = event.kind === 'model.failed' ? 'failed' : event.kind === 'model.started' ? 'running' : 'completed'
      }
      if (!labels[agent] || !['model.started', 'model.completed', 'model.failed'].includes(event.kind)) continue
      const id = `control-${agent}`
      controls[id] = {
        name: labels[agent], type: 'intent', executionState: event.kind === 'model.failed' ? 'failed' : event.kind === 'model.completed' ? 'completed' : 'running',
        data: { nodeKind: 'intent', controlPlane: true, provider: agent, capability: `control.${agent}` },
        rows: [{ title: '节点类型', value: '运行时控制面' }, { title: '模型节点', value: labels[agent] }],
      }
    }
    return {
      'runtime-user-input': {
        name: '用户输入', type: 'input', executionState: inputState,
        data: { nodeKind: 'input', input: true },
        rows: [{ title: '节点类型', value: '用户输入' }, { title: '作用', value: '触发本轮学习计划' }],
      },
      ...controls,
      ...semantic.blocks,
    }
  }, [events, semantic.blocks])
  const explicitEdges = semantic.edges
  const edges = useMemo(() => {
    // The control plane is a real, observable model chain.  Each card has a
    // concrete predecessor and successor; it is never rendered as an orphan
    // annotation or replaced by a fixed graph edge.
    const next = explicitEdges.filter((edge) => !String(edge.source).startsWith('control-') && !String(edge.target).startsWith('control-'))
    const known = new Set(next.map((edge) => `${edge.source}->${edge.target}`))
    for (const [target, block] of Object.entries(blocks)) {
      const dependencies =
        block.depends_on ??
        block.dependsOn ??
        (block.data as Record<string, unknown> | undefined)?.depends_on
      if (!Array.isArray(dependencies)) continue
      for (const dependency of dependencies) {
        const source = String(dependency)
        const key = `${source}->${target}`
        if (!blocks[source] || known.has(key)) continue
        known.add(key)
        next.push({
          id: `runtime-dependency-${source}-${target}`,
          source,
          target,
          data: { kind: 'dependency' },
        })
      }
    }
    const controlChain = ['runtime-user-input', 'control-learning_plan_decision']
      .filter((id) => Boolean(blocks[id]))
    for (let index = 1; index < controlChain.length; index += 1) {
      const source = controlChain[index - 1]
      const target = controlChain[index]
      const key = `${source}->${target}`
      if (known.has(key)) continue
      known.add(key)
      next.push({
        id: `runtime-control-${source}-${target}`,
        source,
        target,
        data: { kind: 'control', label: '评估效用并生成动态学习计划' },
      })
    }
    for (const id of Object.keys(blocks)) {
      if (id === 'runtime-user-input' || id.startsWith('control-')) continue
      const source = blocks['control-learning_plan_decision']
        ? 'control-learning_plan_decision'
        : controlChain.at(-1) ?? 'runtime-user-input'
      const key = `${source}->${id}`
      if (known.has(key)) continue
      known.add(key)
      next.push({
        id: `runtime-intent-${id}`,
        source,
        target: id,
        data: { kind: 'request', label: source === 'control-learning_plan_decision' ? '动态计划任务' : '控制面结果' },
      })
    }
    return next
  }, [blocks, explicitEdges])
  const topologySignature = useMemo(
    () =>
      [
        ...Object.keys(blocks).sort(),
        ...edges.map((edge) => `${edge.id}:${edge.source}->${edge.target}`).sort(),
      ].join('|'),
    [blocks, edges]
  )
  const positions = useMemo(() => {
    const next = layoutRuntimeGraph(blocks, edges, previousPositions.current)
    previousPositions.current = next
    return next
  }, [topologySignature])
  const metadata = (graph.metadata as Record<string, unknown> | undefined) ?? {}
  const running = !Boolean(graph.terminal ?? metadata.terminal)
  const latestStatusText = [...events]
    .reverse()
    .map((event) => {
      const payload = event.payload as Record<string, unknown>
      return event.kind === 'agent.status'
        ? String(payload.text ?? '')
        : event.kind === 'agent.output'
          ? String(payload.message ?? payload.text ?? '')
          : ''
    })
    .find(Boolean)
  const nodes = useMemo<Node[]>(
    () =>
      Object.entries(blocks).map(([id, block]) => ({
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
    () =>
      edges.map((edge) => {
        const targetStatus = blockState(blocks[edge.target] ?? {})
        const sourceStatus = blockState(blocks[edge.source] ?? {})
        const runStatus: EdgeRunStatus =
          targetStatus === 'failed'
            ? 'error'
            : sourceStatus === 'completed' || sourceStatus === 'cached'
              ? 'success'
              : undefined
        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          type: 'lingxiRuntimeEdge',
          sourceHandle: 'source',
          targetHandle: 'target',
          data: {
            runStatus,
            label: runtimeLabel(edge.data?.label ?? edge.label ?? 'Capability dependency'),
            isTargetActive: targetStatus === 'running' || targetStatus === 'retrying',
            isWorkflowRunning: running,
          },
          selectable: false,
        }
      }),
    [blocks, edges, running]
  )
  const lastFittedTopology = useRef('')
  useEffect(() => {
    if (!flowInstance || nodes.length === 0) return
    if (lastFittedTopology.current) return
    lastFittedTopology.current = topologySignature
    const frame = requestAnimationFrame(() => {
      void flowInstance.fitView({ padding: 0.12, minZoom: 0.1, maxZoom: 1.2, duration: 180 })
    })
    return () => cancelAnimationFrame(frame)
  }, [flowInstance, nodes.length, topologySignature])
  useEffect(() => {
    if (!flowInstance || nodes.length === 0) return
    const fresh = nodes.filter((node) => !observedNodeIds.current.has(node.id))
    nodes.forEach((node) => observedNodeIds.current.add(node.id))
    // The initial fit above frames the whole graph. Afterwards follow only
    // newly created runtime nodes, preserving the learner's live context.
    if (fresh.length === 0 || observedNodeIds.current.size === fresh.length) return
    const newest = fresh.at(-1)!
    void flowInstance.setCenter(newest.position.x + 180, newest.position.y + 72, {
      zoom: flowInstance.getZoom(),
      duration: 220,
    })
  }, [flowInstance, nodes, topologySignature])

  if (!taskId) return <div className="p-6 text-sm text-[var(--text-muted)]">暂无运行任务。</div>
  if (nodes.length === 0)
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--text-muted)]">
        等待运行图节点…
      </div>
    )
  return (
    <div className="relative h-full w-full overflow-auto bg-[var(--surface-1)]">
      {latestStatusText && (
        <div className="pointer-events-none absolute left-4 right-4 top-3 z-10 rounded-lg border border-[var(--border-1)] bg-[var(--surface-2)]/95 px-3 py-2 text-xs text-[var(--text-body)] shadow-sm">
          {latestStatusText}
        </div>
      )}
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={flowEdges}
          nodeTypes={{ lingxiRuntimeNode: RuntimeNode }}
          edgeTypes={{ lingxiRuntimeEdge: RuntimeEdge }}
          onInit={setFlowInstance}
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
