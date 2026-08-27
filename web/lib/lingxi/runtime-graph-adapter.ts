import type { Edge } from 'reactflow'
import { BLOCK_DIMENSIONS } from '@/components/workflow/dimensions'
import type { BlockData, BlockState } from '@/lib/workflows/domain/workflow'
import type { AgentTaskEvent } from './types'

export type RuntimeExecutionState =
  | 'queued'
  | 'pending'
  | 'running'
  | 'retrying'
  | 'completed'
  | 'cached'
  | 'failed'
  | 'cancelled'

export interface RuntimeRow {
  title: string
  value: string
}

export interface RuntimeBlockMetadata extends Record<string, unknown> {
  runtimeKind: 'input' | 'control' | 'agent' | 'deterministic'
  runtimeStatus: RuntimeExecutionState
  nodeKind: 'input' | 'intent' | 'agent' | 'deterministic'
  rows: RuntimeRow[]
  capability?: string
  provider?: string
  planTaskId?: string
  dependsOn?: string[]
}

/** BlockState with the small amount of presentation metadata the read-only canvas needs. */
export type RuntimeBlockState = Omit<BlockState, 'data'> & {
  data: BlockData & RuntimeBlockMetadata
  executionState: RuntimeExecutionState
  runtimeRows: RuntimeRow[]
}

export interface RuntimeGraphCanvasState {
  blocks: Record<string, RuntimeBlockState>
  edges: Edge[]
  running: boolean
  latestStatusText?: string
}

interface NativeExecutionNode extends Record<string, unknown> {
  id?: unknown
  label?: unknown
  kind?: unknown
  capability?: unknown
  provider?: unknown
  status?: unknown
  step?: unknown
  taskId?: unknown
  namespace?: unknown
  details?: unknown
}

/** Adapt the first-party execution domain to the existing read-only canvas. */
export function executionSnapshotToCanvasState(
  snapshot: Record<string, unknown> | null | undefined
): Record<string, unknown> {
  const value = snapshot ?? {}
  if (!value.nodes) return value
  const blocks = Object.fromEntries(
    Object.entries(asRecord(value.nodes)).map(([id, rawNode]) => {
      const node = rawNode as NativeExecutionNode
      const details = asRecord(node.details)
      const kind = stringValue(node.kind) || 'agent'
      const capability = stringValue(node.capability)
      return [
        id,
        {
          id,
          name: stringValue(node.label) || capability || id,
          type: kind === 'deterministic' ? 'function' : 'agent',
          enabled: true,
          status: stringValue(node.status) || 'queued',
          executionState: stringValue(node.status) || 'queued',
          data: {
            ...details,
            primitive: capability,
            provider: stringValue(node.provider),
            nodeKind: kind,
            step: node.step,
            taskId: node.taskId,
            namespace: node.namespace,
          },
        },
      ]
    })
  )
  const edges = (Array.isArray(value.dependencies) ? value.dependencies : []).map(
    (rawDependency) => {
      const dependency = asRecord(rawDependency)
      const id = stringValue(dependency.id)
      const source = stringValue(dependency.sourceNodeId)
      const target = stringValue(dependency.targetNodeId)
      return {
        id: id || `${source}->${target}`,
        source,
        target,
        data: {
          kind: dependency.kind,
          status: dependency.status,
          label: dependency.label,
        },
      }
    }
  )
  return {
    id: value.executionId,
    blocks,
    edges,
    variables: value.variables ?? {},
    loops: asRecord(value.groups).loops ?? {},
    parallels: asRecord(value.groups).parallels ?? {},
    metadata: value.metadata ?? {},
    status: value.status,
    paused: value.paused,
    terminal: value.terminal,
  }
}

export function timelineSpansToTraceSpans(
  spans: Array<Record<string, unknown>> | undefined
): Array<Record<string, unknown>> {
  return (spans ?? []).map((span) => ({
    ...span,
    type: stringValue(span.kind) || 'function',
    duration: Number(span.durationMs ?? 0),
    startTime: span.startedAt,
    endTime: span.endedAt,
    children: timelineSpansToTraceSpans(
      Array.isArray(span.children) ? (span.children as Array<Record<string, unknown>>) : []
    ),
  }))
}

interface CapabilityPresentation {
  label: string
  type: 'agent' | 'function'
  nodeKind: 'agent' | 'deterministic'
}

interface RawRuntimeBlock extends Record<string, unknown> {
  data?: Record<string, unknown>
  metadata?: Record<string, unknown>
  rows?: unknown[]
  status?: unknown
  executionState?: unknown
  depends_on?: unknown
  dependsOn?: unknown
  enabled?: unknown
  height?: unknown
}

interface ParsedRuntimeEdge {
  id: string
  source: string
  target: string
  data: Record<string, unknown>
  label: string
  status?: string
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
  queued: '已排队',
}

const CAPABILITY_LABELS: Record<string, string> = {
  Tutor: '辅导老师',
  tutor: '辅导老师',
  answer_user: '回答用户',
  'dialog.answer': '回答对话',
  'dialog.converse': '实时陪聊',
  'Learning Companion': '学习陪伴',
  learning_companion: '学习陪伴',
  learner_interview: '了解你的基础',
  'dialog.interview': '了解你的基础',
  'Socratic Probe': '主动追问',
  socratic_prober: '主动追问',
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
  curriculum_graph: '课程图谱',
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

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function humanize(value: string): string {
  return value.replace(/[-_]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase())
}

export function runtimeLabel(value: unknown): string {
  const text = String(value ?? '-')
  if (CAPABILITY_LABELS[text]) return CAPABILITY_LABELS[text]
  if (RUNTIME_LABELS[text]) return RUNTIME_LABELS[text]
  const normalized = text
    .replace(/[-_.]+/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .trim()
  return RUNTIME_LABELS[normalized] ?? text
}

function normalizeExecutionState(value: unknown): RuntimeExecutionState {
  const status = String(value ?? 'pending').toLowerCase()
  if (
    status === 'queued' ||
    status === 'pending' ||
    status === 'running' ||
    status === 'retrying' ||
    status === 'completed' ||
    status === 'cached' ||
    status === 'failed' ||
    status === 'cancelled'
  ) {
    return status
  }
  if (status === 'success' || status === 'complete') return 'completed'
  if (status === 'error' || status === 'failure') return 'failed'
  return 'pending'
}

function metadataFor(block: RawRuntimeBlock): Record<string, unknown> {
  const metadata = asRecord(block.metadata)
  if (Object.keys(metadata).length > 0) return metadata
  return asRecord(block.data)
}

function runtimeRows(block: RawRuntimeBlock): RuntimeRow[] {
  const metadata = metadataFor(block)
  const rows: RuntimeRow[] = [
    {
      title: '节点类型',
      value: metadata.controlPlane
        ? '大模型控制面'
        : metadata.nodeKind === 'deterministic'
          ? '确定性执行'
          : metadata.nodeKind === 'input'
            ? '用户输入'
            : '智能体 / 服务提供方',
    },
  ]
  if (metadata.capability) {
    rows.push({ title: '能力', value: runtimeLabel(metadata.capability) })
  }
  if (metadata.provider) {
    rows.push({ title: '服务提供方', value: runtimeLabel(metadata.provider) })
  }
  if (metadata.knowledgePointId) {
    rows.push({ title: '学习目标', value: String(metadata.knowledgePointId) })
  }
  if (metadata.doneWhen) {
    rows.push({ title: '完成条件', value: runtimeLabel(metadata.doneWhen) })
  }
  if (rows.length > 1) return rows.slice(0, 4)

  if (Array.isArray(block.rows)) {
    return block.rows.slice(0, 4).map((row) => {
      const item = asRecord(row)
      return {
        title: runtimeLabel(item.title ?? item.label ?? '详情'),
        value: runtimeLabel(item.value ?? '-'),
      }
    })
  }

  return Object.entries(metadata)
    .filter(([key]) => !['step', 'planTaskId', 'namespace', 'primitive'].includes(key))
    .slice(0, 3)
    .map(([title, value]) => ({ title: runtimeLabel(title), value: runtimeLabel(value) }))
}

function registerCapability(
  map: Map<string, CapabilityPresentation>,
  presentation: CapabilityPresentation,
  aliases: string[]
) {
  aliases.forEach((alias) => map.set(alias.toLowerCase(), presentation))
}

const CAPABILITY_PRESENTATIONS = new Map<string, CapabilityPresentation>()
registerCapability(CAPABILITY_PRESENTATIONS, { label: 'Tutor', type: 'agent', nodeKind: 'agent' }, [
  'Tutor',
  'tutor',
  'answer_user',
  'dialog.answer',
  'teach.explain',
  'dialog.negotiate',
  'negotiator',
])
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: '学习陪伴', type: 'agent', nodeKind: 'agent' },
  ['学习陪伴', 'Learning Companion', 'learning_companion', 'dialog.converse']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: '了解你的基础', type: 'agent', nodeKind: 'agent' },
  ['了解你的基础', 'learner_interview', 'dialog.interview']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: '主动追问', type: 'agent', nodeKind: 'agent' },
  ['主动追问', 'Socratic Probe', 'socratic_prober', 'probe_user', 'dialog.probe']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Adaptive Tutor', type: 'agent', nodeKind: 'agent' },
  ['Adaptive Tutor', 'adaptive_tutor', 'adaptive_pedagogy', 'teach.strategy']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Lesson Intro', type: 'agent', nodeKind: 'agent' },
  ['Lesson Intro', 'lesson_intro', 'content.lesson_intro', 'lecture_hook']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Lecture Deck', type: 'agent', nodeKind: 'agent' },
  ['Lecture Deck', 'lecture_deck', 'content.deck', 'interactive_lecture_deck']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Visual Explainer', type: 'agent', nodeKind: 'agent' },
  ['Visual Explainer', 'visual_explainer', 'content.visual', 'interactive_visual_explainer']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Quiz Generator', type: 'agent', nodeKind: 'agent' },
  ['Quiz Generator', 'quiz_generator', 'assess.generate']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Formative Assessor', type: 'agent', nodeKind: 'agent' },
  ['Formative Assessor', 'formative_assessor', 'assess.interpret']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Retrieval Practice', type: 'agent', nodeKind: 'agent' },
  ['Retrieval Practice', 'retrieval_practice', 'review_scheduler', 'review.schedule']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Curriculum Mapper', type: 'agent', nodeKind: 'agent' },
  [
    'Curriculum Mapper',
    'curriculum_mapper',
    'curriculum_graph',
    'prerequisite_analyzer',
    'graph.build',
    'graph.prerequisite',
  ]
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Learner Reflector', type: 'agent', nodeKind: 'agent' },
  ['Learner Reflector', 'learner_reflector', 'learner_state_reflector', 'model.reflect']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Investigator', type: 'agent', nodeKind: 'agent' },
  [
    'Investigator',
    'investigator',
    'pack_investigate',
    'tool.investigate',
    'web_search',
    'web_fetch',
  ]
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Learning Reporter', type: 'agent', nodeKind: 'agent' },
  ['Learning Reporter', 'learning_reporter', 'pack_report', 'meta.report']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Skill Forge', type: 'agent', nodeKind: 'agent' },
  ['Skill Forge', 'skill_forge', 'meta.author_skill']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Knowledge Probe', type: 'function', nodeKind: 'deterministic' },
  ['Knowledge Probe', 'knowledge_probe', 'pack_probe', 'knowledge.search', 'kb.search']
)
registerCapability(
  CAPABILITY_PRESENTATIONS,
  { label: 'Deterministic Grader', type: 'function', nodeKind: 'deterministic' },
  ['Deterministic Grader', 'deterministic_grader', 'assess.grade', 'quiz_submit']
)

function capabilityPresentation(block: RawRuntimeBlock): CapabilityPresentation | null {
  const data = asRecord(block.data)
  const candidates = [data.provider, data.primitive, data.capability, block.name]
  for (const candidate of candidates) {
    const presentation = CAPABILITY_PRESENTATIONS.get(String(candidate ?? '').toLowerCase())
    if (presentation) return presentation
  }
  return null
}

function blockStatus(block: RuntimeBlockState): RuntimeExecutionState {
  return block.executionState
}

function blockHeight(rows: RuntimeRow[], source: RawRuntimeBlock): number {
  const stored = Number(source.height)
  const computed =
    rows.length === 0
      ? BLOCK_DIMENSIONS.MIN_PAINTED_HEIGHT
      : BLOCK_DIMENSIONS.HEADER_HEIGHT +
        BLOCK_DIMENSIONS.WORKFLOW_CONTENT_PADDING +
        rows.length * BLOCK_DIMENSIONS.WORKFLOW_ROW_HEIGHT +
        Math.max(0, rows.length - 1) * BLOCK_DIMENSIONS.WORKFLOW_CONTENT_GAP
  return Number.isFinite(stored) && stored > 0 ? Math.max(stored, computed) : computed
}

function makeBlock(
  id: string,
  source: RawRuntimeBlock,
  presentation: CapabilityPresentation,
  runtimeKind: RuntimeBlockMetadata['runtimeKind'] = presentation.nodeKind
): RuntimeBlockState {
  const sourceData = asRecord(source.data)
  const rows = runtimeRows(source)
  const executionState = normalizeExecutionState(source.executionState ?? source.status)
  const dependsOn = [
    source.depends_on,
    source.dependsOn,
    sourceData.depends_on,
    sourceData.dependsOn,
  ].find(Array.isArray) as unknown[] | undefined
  const data: RuntimeBlockMetadata = {
    ...sourceData,
    runtimeKind,
    runtimeStatus: executionState,
    nodeKind:
      runtimeKind === 'input'
        ? 'input'
        : runtimeKind === 'control'
          ? 'intent'
          : presentation.nodeKind,
    rows,
    capability: stringValue(sourceData.capability) || presentation.label,
    provider: stringValue(sourceData.provider) || undefined,
    planTaskId: stringValue(sourceData.planTaskId) || undefined,
    dependsOn: dependsOn?.map(String),
  }
  return {
    id,
    type: presentation.type,
    // The semantic projection deliberately uses the canonical capability
    // label rather than an execution-specific step name.  This keeps the
    // visible card identity stable when V2 re-emits a plan with new step
    // metadata, matching the previous Runtime Graph semantics.
    name: runtimeLabel(presentation.label),
    position: { x: 0, y: 0 },
    subBlocks: {},
    outputs: {},
    enabled: source.enabled !== false,
    horizontalHandles: true,
    height: blockHeight(rows, source),
    data,
    executionState,
    runtimeRows: rows,
  }
}

function makeSpecialBlock(
  id: string,
  type: string,
  name: string,
  runtimeKind: 'input' | 'control',
  executionState: RuntimeExecutionState,
  rows: RuntimeRow[],
  sourceData: Record<string, unknown> = {}
): RuntimeBlockState {
  return {
    id,
    type,
    name,
    position: { x: 0, y: 0 },
    subBlocks: {},
    outputs: {},
    enabled: true,
    horizontalHandles: true,
    height: blockHeight(rows, {}),
    data: {
      ...sourceData,
      runtimeKind,
      runtimeStatus: executionState,
      nodeKind: runtimeKind === 'input' ? 'input' : 'intent',
      rows,
    },
    executionState,
    runtimeRows: rows,
  }
}

function parseEdges(rawEdges: unknown): ParsedRuntimeEdge[] {
  if (!Array.isArray(rawEdges)) return []
  return rawEdges
    .map((raw) => {
      const edge = asRecord(raw)
      const data = asRecord(edge.data)
      return {
        id: stringValue(edge.id),
        source: stringValue(edge.source),
        target: stringValue(edge.target),
        data,
        label: stringValue(edge.label) || stringValue(data.label),
        status: stringValue(edge.status) || stringValue(data.status) || undefined,
      }
    })
    .filter((edge) => edge.source && edge.target && edge.source !== edge.target)
}

function visibleSemanticGraph(
  rawBlocks: Record<string, RawRuntimeBlock>,
  rawEdges: ParsedRuntimeEdge[]
): { blocks: Record<string, RuntimeBlockState>; edges: ParsedRuntimeEdge[] } {
  const blocks: Record<string, RuntimeBlockState> = {}
  for (const [id, rawBlock] of Object.entries(rawBlocks)) {
    const presentation = capabilityPresentation(rawBlock)
    if (!presentation) continue
    blocks[id] = makeBlock(id, rawBlock, presentation)
  }

  const visible = new Set(Object.keys(blocks))
  const outgoing = new Map<string, ParsedRuntimeEdge[]>()
  for (const edge of rawEdges) {
    outgoing.set(edge.source, [...(outgoing.get(edge.source) ?? []), edge])
  }

  const edges: ParsedRuntimeEdge[] = []
  const seen = new Set<string>()
  for (const source of visible) {
    const queue = (outgoing.get(source) ?? []).map((edge) => ({ edge, collapsed: false }))
    const visitedHidden = new Set<string>()
    while (queue.length > 0) {
      const current = queue.shift()!
      const edge = current.edge
      if (visible.has(edge.target)) {
        const key = `${source}->${edge.target}`
        if (edge.target !== source && !seen.has(key)) {
          seen.add(key)
          const label = current.collapsed
            ? '灵析运行时'
            : runtimeLabel(edge.label || 'Capability dependency')
          edges.push({
            ...edge,
            id: `runtime-edge-${encodeURIComponent(source)}-${encodeURIComponent(edge.target)}`,
            source,
            label,
            data: { ...edge.data, label },
          })
        }
        continue
      }
      if (visitedHidden.has(edge.target)) continue
      visitedHidden.add(edge.target)
      for (const next of outgoing.get(edge.target) ?? []) {
        queue.push({ edge: next, collapsed: true })
      }
    }
  }
  return { blocks, edges }
}

function edgeFor(
  source: string,
  target: string,
  data: Record<string, unknown> = {}
): ParsedRuntimeEdge {
  return {
    id: `runtime-${String(data.kind ?? 'edge')}-${encodeURIComponent(source)}-${encodeURIComponent(target)}`,
    source,
    target,
    data,
    label: stringValue(data.label),
  }
}

function addEdge(edges: ParsedRuntimeEdge[], seen: Set<string>, edge: ParsedRuntimeEdge) {
  if (!edge.source || !edge.target || edge.source === edge.target) return
  const key = `${edge.source}->${edge.target}`
  if (seen.has(key)) return
  seen.add(key)
  edges.push(edge)
}

function buildControlAndDependencyEdges(
  blocks: Record<string, RuntimeBlockState>,
  explicitEdges: ParsedRuntimeEdge[]
): ParsedRuntimeEdge[] {
  const edges = explicitEdges.filter(
    (edge) => !edge.source.startsWith('control-') && !edge.target.startsWith('control-')
  )
  const seen = new Set(edges.map((edge) => `${edge.source}->${edge.target}`))

  for (const [target, block] of Object.entries(blocks)) {
    const dependencies = block.data.dependsOn ?? []
    for (const dependency of dependencies) {
      const source = String(dependency)
      if (!blocks[source]) continue
      addEdge(edges, seen, edgeFor(source, target, { kind: 'dependency' }))
    }
  }

  const controlChain = ['runtime-user-input', 'control-learning_plan_decision'].filter((id) =>
    Boolean(blocks[id])
  )
  for (let index = 1; index < controlChain.length; index += 1) {
    const source = controlChain[index - 1]
    const target = controlChain[index]
    addEdge(
      edges,
      seen,
      edgeFor(source, target, {
        kind: 'control',
        label: '评估效用并生成动态学习计划',
      })
    )
  }

  for (const id of Object.keys(blocks)) {
    if (id === 'runtime-user-input' || id.startsWith('control-')) continue
    const source = blocks['control-learning_plan_decision']
      ? 'control-learning_plan_decision'
      : (controlChain.at(-1) ?? 'runtime-user-input')
    if (!blocks[source]) continue
    addEdge(
      edges,
      seen,
      edgeFor(source, id, {
        kind: 'request',
        label: source === 'control-learning_plan_decision' ? '动态计划任务' : '控制面结果',
      })
    )
  }
  return edges
}

function toReactFlowEdges(edges: ParsedRuntimeEdge[]): Edge[] {
  return edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: 'source',
    targetHandle: 'target',
    type: 'lingxiRuntimeEdge',
    label: edge.label || undefined,
    data: {
      ...edge.data,
      label: edge.label || undefined,
      status: edge.status ?? edge.data.status,
    },
    selectable: false,
  }))
}

function latestStatusText(events: AgentTaskEvent[]): string | undefined {
  return [...events]
    .reverse()
    .map((event) => {
      const payload = event.payload ?? {}
      return event.kind === 'agent.status'
        ? stringValue(payload.text)
        : event.kind === 'agent.output'
          ? stringValue(payload.message ?? payload.text)
          : ''
    })
    .find(Boolean)
}

export function projectRuntimeGraph(
  executionSnapshot: Record<string, unknown> | null | undefined,
  events: AgentTaskEvent[] = []
): RuntimeGraphCanvasState {
  const graph = executionSnapshotToCanvasState(executionSnapshot)
  const rawBlocks = Object.fromEntries(
    Object.entries(asRecord(graph.blocks)).map(([id, block]) => [
      id,
      asRecord(block) as RawRuntimeBlock,
    ])
  )
  const parsed = visibleSemanticGraph(rawBlocks, parseEdges(graph.edges))

  let inputState: RuntimeExecutionState = 'completed'
  const controls: Record<string, RuntimeBlockState> = {}
  const controlLabels: Record<string, string> = {
    learning_plan_decision: '学习计划决策',
  }
  for (const event of events) {
    const agent = stringValue(event.agent)
    if (
      agent === 'goal_interpreter' &&
      ['model.started', 'model.completed', 'model.failed'].includes(event.kind)
    ) {
      inputState =
        event.kind === 'model.failed'
          ? 'failed'
          : event.kind === 'model.started'
            ? 'running'
            : 'completed'
    }
    const label = controlLabels[agent]
    if (!label || !['model.started', 'model.completed', 'model.failed'].includes(event.kind))
      continue
    controls[`control-${agent}`] = makeSpecialBlock(
      `control-${agent}`,
      'router_v2',
      label,
      'control',
      event.kind === 'model.failed'
        ? 'failed'
        : event.kind === 'model.started'
          ? 'running'
          : 'completed',
      [
        { title: '节点类型', value: '运行时控制面' },
        { title: '模型节点', value: label },
      ],
      { controlPlane: true, provider: agent, capability: `control.${agent}` }
    )
  }

  const blocks: Record<string, RuntimeBlockState> = {
    'runtime-user-input': makeSpecialBlock(
      'runtime-user-input',
      'workflow_input',
      '用户输入',
      'input',
      inputState,
      [
        { title: '节点类型', value: '用户输入' },
        { title: '作用', value: '触发本轮学习计划' },
      ],
      { input: true }
    ),
    ...controls,
    ...parsed.blocks,
  }
  const explicitEdges = parsed.edges
  const runtimeEdges = buildControlAndDependencyEdges(blocks, explicitEdges)
  const metadata = asRecord(graph.metadata)
  const running = !(graph.terminal ?? metadata.terminal)

  return {
    blocks,
    edges: toReactFlowEdges(runtimeEdges),
    running,
    latestStatusText: latestStatusText(events),
  }
}

export function runtimeBlockStatus(block: RuntimeBlockState): RuntimeExecutionState {
  return blockStatus(block)
}

export function runtimeStatusToRunPath(
  status: RuntimeExecutionState
): 'success' | 'error' | undefined {
  if (status === 'completed' || status === 'cached') return 'success'
  if (status === 'failed') return 'error'
  return undefined
}

export function runtimeEdgeStatus(
  source: RuntimeBlockState | undefined,
  target: RuntimeBlockState | undefined,
  edgeStatus?: unknown
): 'success' | 'error' | 'not-executed' {
  // A failed endpoint always wins over a traversed predecessor.  This keeps
  // the native renderer from painting a success edge into (or out of) a
  // failed block when the other endpoint completed earlier.
  if (source?.executionState === 'failed' || target?.executionState === 'failed') {
    return 'error'
  }
  const normalizedEdgeStatus = String(edgeStatus ?? '').toLowerCase()
  if (['error', 'failed', 'failure'].includes(normalizedEdgeStatus)) return 'error'
  if (['success', 'completed', 'cached'].includes(normalizedEdgeStatus)) return 'success'
  if (source && ['completed', 'cached'].includes(source.executionState)) return 'success'
  return 'not-executed'
}

export function runtimeIconType(block: RuntimeBlockState): string {
  if (block.data.runtimeKind === 'input') return 'workflow_input'
  if (block.data.runtimeKind === 'control') return 'router_v2'
  return block.type
}

export function runtimeTypeLabel(block: RuntimeBlockState): string {
  if (block.data.runtimeKind === 'input') return '用户输入'
  if (block.data.runtimeKind === 'control') return '运行时控制'
  return block.data.nodeKind === 'deterministic' ? '确定性执行' : '智能体 / 服务提供方'
}

export function runtimeDisplayName(block: RuntimeBlockState): string {
  return block.name || humanize(block.type)
}
