'use client'

import {
  AgentIcon,
  ConditionalIcon,
  JiraIcon,
  SlackIcon,
  StartIcon,
  TableIcon,
} from '@/components/icons'
import type { AgentTaskEvent, AgentTaskSnapshot } from '@/lib/lingxi/types'
import { HeroWorkflowStage } from '@/app/(landing)/components/hero/components/hero-platform-loop/hero-workflow-stage'
import { EditorLoop, type EditorLoopContent } from '@/app/(landing)/components/shared/editor-loop'

export type WorkflowNodeStatus = 'idle' | 'queued' | 'running' | 'completed' | 'failed'

/** Runtime information rendered inside a node of the workspace graph. */
export interface WorkflowNodeActivity {
  status: WorkflowNodeStatus
  messages: string[]
  thoughts: string[]
  skills: string[]
  lastSequence?: number
  executionId?: string
}

export interface WorkflowsEditorRuntime {
  task: AgentTaskSnapshot | null
  events: AgentTaskEvent[]
  executionSnapshot?: Record<string, unknown> | null
}

export interface WorkflowsEditorLoopProps {
  /** Durable LingxiGraph state. Omit it to render the landing-page loop. */
  runtime?: WorkflowsEditorRuntime
  /** Render the graph as a live workspace panel instead of the decorative loop. */
  live?: boolean
}

/**
 * The workflows hero's content for the shared {@link EditorLoop}: a builder's
 * workspace sidebar and the complete support-routing workflow - a trigger, an
 * agent, a router, and a three-way fan-out to Slack, Jira, and Tables. Wider
 * than the chat heroes' half-pane flows (center spine at x=555, terminals
 * fanned across 1360 design px) because the canvas owns the whole workspace
 * pane here. Colors follow the stage convention - grey ramp for platform
 * blocks, brand tiles only for real third-party marks. Blocks are ordered by
 * build sequence; an edge draws once both endpoints are on canvas. The agent
 * block is the one the "editing" beat selects once the flow is assembled.
 */
const WORKFLOWS_EDITOR_CONTENT: EditorLoopContent = {
  sidebarChats: [
    'Support bot revamp',
    'Lead scoring tweaks',
    'Invoice matching flow',
    'Weekly digest agent',
  ],
  sidebarWorkflows: [
    'Support ticket routing',
    'Lead enrichment',
    'Invoice matching',
    'Weekly digest',
    'Churn-risk alerts',
  ],
  blocks: [
    {
      id: 'start',
      name: 'Start',
      icon: StartIcon,
      bgColor: 'var(--text-muted)',
      isTrigger: true,
      rows: [{ title: 'Inputs', value: '-' }],
      x: 555,
      y: 20,
    },
    {
      id: 'agent',
      name: 'Support agent',
      icon: AgentIcon,
      bgColor: 'var(--text-primary)',
      rows: [
        { title: 'Messages', value: '-' },
        { title: 'Model', value: '-' },
      ],
      x: 555,
      y: 230,
    },
    {
      id: 'route',
      name: 'Route intent',
      icon: ConditionalIcon,
      bgColor: 'var(--text-secondary)',
      rows: [{ title: 'Conditions', value: '-' }],
      x: 555,
      y: 470,
    },
    {
      id: 'slack',
      name: 'Reply in Slack',
      icon: SlackIcon,
      bgColor: '#611F69',
      isTerminal: true,
      rows: [
        { title: 'Channel', value: '-' },
        { title: 'Message', value: '-' },
      ],
      x: 100,
      y: 700,
    },
    {
      id: 'jira',
      name: 'Escalate to Jira',
      icon: JiraIcon,
      bgColor: '#FFFFFF',
      tileBorder: true,
      isTerminal: true,
      rows: [
        { title: 'Project', value: '-' },
        { title: 'Summary', value: '-' },
      ],
      x: 555,
      y: 700,
    },
    {
      id: 'tables',
      name: 'Log to Tables',
      icon: TableIcon,
      bgColor: 'var(--text-body)',
      isTerminal: true,
      rows: [
        { title: 'Table', value: '-' },
        { title: 'Operation', value: '-' },
      ],
      x: 1010,
      y: 700,
    },
  ],
  edges: [
    ['start', 'agent'],
    ['agent', 'route'],
    ['route', 'slack'],
    ['route', 'jira'],
    ['route', 'tables'],
  ],
  canvas: { width: 1360, height: 910 },
  selectedBlockId: 'agent',
}

const WORKSPACE_AGENT_DEFS = [
  {
    id: 'global_router',
    name: '全局路由',
    skill: 'global-router',
    icon: ConditionalIcon,
    bgColor: 'var(--text-primary)',
    x: 555,
    y: 190,
  },
  {
    id: 'knowledge_deep_dive',
    name: 'Knowledge Deep Dive',
    skill: 'knowledge_deep_dive',
    icon: AgentIcon,
    bgColor: 'var(--brand-accent)',
    x: 555,
    y: 400,
  },
  {
    id: 'practice',
    name: 'Adaptive Practice',
    skill: 'assessment-builder',
    icon: AgentIcon,
    bgColor: 'var(--text-secondary)',
    x: 100,
    y: 400,
  },
  {
    id: 'review',
    name: 'Retrieval Review',
    skill: 'retrieval',
    icon: AgentIcon,
    bgColor: 'var(--text-secondary)',
    x: 330,
    y: 400,
  },
  {
    id: 'learning_plan',
    name: 'Learning Path',
    skill: 'curriculum graph',
    icon: AgentIcon,
    bgColor: 'var(--text-secondary)',
    x: 780,
    y: 400,
  },
  {
    id: 'knowledge_map',
    name: 'Knowledge Map',
    skill: 'curriculum graph',
    icon: AgentIcon,
    bgColor: 'var(--text-secondary)',
    x: 1010,
    y: 400,
  },
  {
    id: 'direct_tutor',
    name: 'Direct Tutor',
    skill: 'adaptive-pedagogy',
    icon: AgentIcon,
    bgColor: 'var(--text-secondary)',
    x: 1010,
    y: 610,
  },
  {
    id: 'lecture_hook',
    name: '课程引入',
    skill: 'lesson-intro',
    icon: AgentIcon,
    bgColor: 'var(--brand-accent)',
    x: 100,
    y: 610,
  },
  {
    id: 'interactive_lecture_deck',
    name: '交互式讲义',
    skill: 'interactive-lecture-deck',
    icon: AgentIcon,
    bgColor: 'var(--text-secondary)',
    x: 330,
    y: 610,
  },
  {
    id: 'quiz_generator',
    name: '知识检测',
    skill: 'quiz-generator',
    icon: AgentIcon,
    bgColor: 'var(--text-secondary)',
    x: 780,
    y: 610,
  },
  {
    id: 'interactive_visual_explainer',
    name: '可视化讲解',
    skill: 'interactive-visual-explainer',
    icon: AgentIcon,
    bgColor: 'var(--text-secondary)',
    x: 1010,
    y: 610,
  },
  {
    id: 'adaptive_pedagogy',
    name: '学习结果整合',
    skill: 'adaptive-pedagogy',
    icon: AgentIcon,
    bgColor: 'var(--text-primary)',
    x: 555,
    y: 850,
  },
  {
    id: 'task_hub',
    name: '任务 Hub',
    skill: 'handoff',
    icon: AgentIcon,
    bgColor: 'var(--text-primary)',
    x: 555,
    y: 1080,
  },
  {
    id: 'session_end',
    name: 'Session Reflection',
    skill: 'metacognitive-reflection',
    icon: AgentIcon,
    bgColor: 'var(--text-primary)',
    x: 555,
    y: 1280,
  },
] as const

const WORKSPACE_EDGES: ReadonlyArray<readonly [string, string]> = [
  ['start', 'global_router'],
  ['global_router', 'knowledge_deep_dive'],
  ['global_router', 'practice'],
  ['global_router', 'review'],
  ['global_router', 'learning_plan'],
  ['global_router', 'knowledge_map'],
  ['global_router', 'direct_tutor'],
  ['knowledge_deep_dive', 'lecture_hook'],
  ['knowledge_deep_dive', 'interactive_lecture_deck'],
  ['knowledge_deep_dive', 'quiz_generator'],
  ['knowledge_deep_dive', 'interactive_visual_explainer'],
  ['lecture_hook', 'adaptive_pedagogy'],
  ['interactive_lecture_deck', 'adaptive_pedagogy'],
  ['quiz_generator', 'adaptive_pedagogy'],
  ['interactive_visual_explainer', 'adaptive_pedagogy'],
  ['adaptive_pedagogy', 'task_hub'],
  ['practice', 'task_hub'],
  ['review', 'task_hub'],
  ['learning_plan', 'task_hub'],
  ['knowledge_map', 'task_hub'],
  ['direct_tutor', 'task_hub'],
  ['task_hub', 'session_end'],
]

const AGENT_LABELS: Record<string, string> = {
  intent: '全局路由',
  coordinator: '全局路由',
  global_router: '全局路由',
  knowledge_deep_dive: 'Knowledge Deep Dive',
  lecture_hook: '课程引入',
  interactive_lecture_deck: '交互式讲义',
  quiz_generator: '知识检测',
  interactive_visual_explainer: '可视化讲解',
  adaptive_pedagogy: '学习结果整合',
  answer_user: 'Direct Tutor',
  task_hub: '任务 Hub',
  session_end: 'Session Reflection',
}

const AGENT_NODE_ALIASES: Record<string, string> = {
  intent: 'global_router',
  coordinator: 'global_router',
  handoff: 'task_hub',
  answer_user: 'direct_tutor',
}

function humanizeAgent(agent: string): string {
  return agent.replace(/[-_]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase())
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function textValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function compactText(value: string, max = 120): string {
  const normalized = value.replace(/\s+/g, ' ').trim()
  return normalized.length > max ? `${normalized.slice(0, max)}…` : normalized
}

function eventText(event: AgentTaskEvent): string {
  const payload = recordValue(event.payload)
  return textValue(payload.message) || textValue(payload.text) || textValue(payload.delta)
}

function addUnique(values: string[], value: string): void {
  if (value && !values.includes(value)) values.push(value)
}

function initialActivity(): WorkflowNodeActivity {
  return { status: 'idle', messages: [], thoughts: [], skills: [] }
}

/**
 * Project the durable event stream into node-local runtime data. The graph
 * deliberately consumes events directly: messages, safe thought summaries,
 * and skill names stay attached to the node that produced them.
 */
export function projectWorkflowNodeActivities(
  events: AgentTaskEvent[],
  task: AgentTaskSnapshot | null = null
): Record<string, WorkflowNodeActivity> {
  const activities: Record<string, WorkflowNodeActivity> = {}
  const ensure = (agent: string) => {
    activities[agent] ??= initialActivity()
    return activities[agent]
  }

  for (const event of [...events].sort((a, b) => a.sequence - b.sequence)) {
    const rawAgent = textValue(event.agent)
    if (!rawAgent) continue
    const agent = AGENT_NODE_ALIASES[rawAgent] ?? rawAgent
    const activity = ensure(agent)
    const payload = recordValue(event.payload)
    activity.lastSequence = event.sequence
    activity.executionId =
      event.execution_id || textValue(event.runtime?.execution_id) || activity.executionId

    if (event.kind === 'agent.started') {
      activity.status = 'running'
      addUnique(activity.skills, textValue(payload.skill))
      activity.thoughts = [`${AGENT_LABELS[agent] ?? agent}正在处理当前学习阶段。`]
    } else if (event.kind === 'agent.completed') {
      activity.status = 'completed'
      activity.thoughts = [`${AGENT_LABELS[agent] ?? agent}已完成当前学习阶段。`]
    } else if (event.kind === 'agent.failed') {
      activity.status = 'failed'
      const error = textValue(payload.error)
      activity.thoughts = [error ? `处理失败：${compactText(error)}` : '处理失败，已保留当前状态。']
    } else if (event.kind === 'agent.output' || event.kind === 'assistant.delta') {
      const message = compactText(eventText(event))
      if (message) activity.messages = [...activity.messages.slice(-1), message]
    } else if (event.kind === 'reasoning.delta') {
      // Do not expose hidden chain-of-thought. Keep a safe, node-local phase
      // marker while still allowing the graph to represent that thinking is
      // happening for this node.
      activity.thoughts = ['正在结合当前上下文整理下一步。']
      if (activity.status === 'idle') activity.status = 'running'
    } else if (event.kind === 'node.started' || event.kind === 'node.retrying') {
      activity.status = 'running'
      activity.thoughts = [
        event.kind === 'node.retrying'
          ? '节点正在结合当前上下文重试。'
          : '节点已启动，正在推进任务。',
      ]
    } else if (event.kind === 'node.completed') {
      activity.status = 'completed'
      activity.thoughts = ['节点已完成，结果已交给后续节点。']
    } else if (event.kind === 'tool.call.delta') {
      const calls = Array.isArray(payload.calls)
        ? payload.calls
        : Array.isArray(payload.chunks)
          ? payload.chunks
          : []
      for (const call of calls) {
        const tool = recordValue(call)
        addUnique(activity.skills, textValue(tool.name))
      }
    } else if (event.kind === 'tool.result') {
      const tool = textValue(payload.name)
      if (tool) addUnique(activity.skills, tool)
      activity.thoughts = ['已收到工具结果，正在更新节点上下文。']
    }
  }

  if (task && ['completed', 'partial', 'handed_off', 'failed'].includes(task.status)) {
    for (const activity of Object.values(activities)) {
      if (activity.status === 'running' || activity.status === 'queued') {
        activity.status = task.status === 'failed' ? 'failed' : 'completed'
      }
    }
  }

  return activities
}

function activityRows(activity: WorkflowNodeActivity, skill: string) {
  const latestMessage = activity.messages.at(-1) || '等待节点消息'
  const latestThought = activity.thoughts.at(-1) || '等待节点思考'
  const skills = activity.skills.length > 0 ? activity.skills.join(' · ') : skill
  const status =
    activity.status === 'running'
      ? '执行中'
      : activity.status === 'completed'
        ? '已完成'
        : activity.status === 'failed'
          ? '失败'
          : '等待中'
  return [
    { title: '状态', value: status },
    { title: '消息', value: compactText(latestMessage, 54) },
    { title: '思考', value: compactText(latestThought, 54) },
    { title: 'Skill', value: compactText(skills, 54) },
    {
      title: 'Trace',
      value: activity.executionId ? compactText(activity.executionId, 54) : '等待运行',
    },
  ]
}

function createWorkspaceContent(runtime: WorkflowsEditorRuntime): EditorLoopContent {
  const activities = projectWorkflowNodeActivities(runtime.events, runtime.task)
  const knownAgentIds = new Set<string>(WORKSPACE_AGENT_DEFS.map((definition) => definition.id))
  const additionalAgentDefs = Object.keys(activities)
    .filter((id) => !knownAgentIds.has(id))
    .map((id, index) => ({
      id,
      name: AGENT_LABELS[id] ?? humanizeAgent(id),
      skill: humanizeAgent(id),
      icon: AgentIcon,
      bgColor: 'var(--text-secondary)',
      x: 100 + (index % 4) * 300,
      y: 1480 + Math.floor(index / 4) * 250,
    }))
  const agentDefs = [...WORKSPACE_AGENT_DEFS, ...additionalAgentDefs]
  const blocks = [
    {
      id: 'start',
      name: '学习任务',
      icon: StartIcon,
      bgColor: 'var(--text-muted)',
      isTrigger: true,
      rows: [
        { title: '消息', value: compactText(runtime.task?.prompt || '等待学习主题', 54) },
        { title: '节点', value: 'LingxiGraph' },
      ],
      x: 555,
      y: 20,
    },
    ...agentDefs.map((definition) => ({
      ...definition,
      rows: activityRows(activities[definition.id] ?? initialActivity(), definition.skill),
    })),
  ]
  const additionalEdges: ReadonlyArray<readonly [string, string]> = additionalAgentDefs.map(
    (definition) => ['global_router', definition.id] as const
  )
  const active = Object.entries(activities)
    .filter(([, activity]) => activity.status === 'running')
    .sort(([, left], [, right]) => (right.lastSequence ?? 0) - (left.lastSequence ?? 0))[0]?.[0]

  return {
    sidebarChats: ['当前学习任务', '知识点复习', '错题回顾', '学习计划'],
    sidebarWorkflows: ['多智能体学习编排', '课程引入', '知识检测', '可视化讲解', '学习结果'],
    blocks,
    edges: [...WORKSPACE_EDGES, ...additionalEdges],
    canvas: { width: 1480, height: 1450 + Math.ceil(additionalAgentDefs.length / 4) * 250 },
    selectedBlockId: active || 'start',
  }
}

function LiveWorkflowsEditor({ runtime }: { runtime: WorkflowsEditorRuntime }) {
  const content = createWorkspaceContent(runtime)
  const visibleBlockIds = new Set(content.blocks.map((block) => block.id))

  return (
    <div className='h-full min-h-[520px] w-full overflow-hidden rounded-[6px] border border-[var(--border)] bg-[var(--bg)]'>
      <div className='flex h-10 items-center justify-between border-[var(--border)] border-b px-3'>
        <div className='flex items-center gap-2 text-[var(--text-primary)] text-xs'>
          <span className='size-1.5 rounded-full bg-[var(--brand-accent)]' />
          多智能体可视化编排
        </div>
        <span className='text-[var(--text-muted)] text-[10px]'>节点消息 · 思考 · Skill</span>
      </div>
      <div className='h-[calc(100%-2.5rem)]'>
        <HeroWorkflowStage
          builtCount={content.blocks.length}
          blocks={content.blocks}
          edges={content.edges}
          canvas={content.canvas}
          selectedId={content.selectedBlockId}
          visibleBlockIds={visibleBlockIds}
        />
      </div>
    </div>
  )
}

/**
 * The workflows hero's editor loop - the shared {@link EditorLoop} replaying
 * the support-routing workflow with the agent block as the "being edited"
 * beat.
 */
export function WorkflowsEditorLoop({ runtime, live = false }: WorkflowsEditorLoopProps = {}) {
  if (live && runtime) return <LiveWorkflowsEditor runtime={runtime} />
  return <EditorLoop content={WORKFLOWS_EDITOR_CONTENT} />
}
