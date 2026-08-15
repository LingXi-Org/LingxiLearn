import { api, subscribeAgentEvents, type LingxiAttachmentRef } from '@/lib/lingxi/api'
import type {
  ContentBlock,
  ReasoningStep,
  ToolCallInfo,
  ToolCallStatus,
} from '@/lib/lingxi/chat-types'
import type { AgentTaskEvent, AgentTaskSnapshot } from '@/lib/lingxi/types'

export const LINGXI_GRAPH_ADAPTER_KIND = 'lingxigraph' as const

export interface LingxiGraphProjection {
  blocks: ContentBlock[]
  assistantText: string
  isTerminal: boolean
}

export interface LingxiTaskContextOptions {
  resourceRefs?: Array<Record<string, unknown>>
  skillIds?: string[]
}

export interface LingxiGraphSubscriptionOptions {
  from?: number
  onEvent: (event: AgentTaskEvent) => void
  onEnd?: (status: string) => void
  onError?: (error: Error) => void
}

export interface LingxiGraphChatAdapter {
  readonly kind: typeof LINGXI_GRAPH_ADAPTER_KIND
  createTask(
    prompt: string,
    attachments?: LingxiAttachmentRef[],
    options?: LingxiTaskContextOptions
  ): Promise<{ id: string; status: string }>
  loadTask(taskId: string): Promise<AgentTaskSnapshot>
  sendMessage(
    taskId: string,
    message: string,
    attachments?: LingxiAttachmentRef[],
    options?: LingxiTaskContextOptions
  ): Promise<{ status: string }>
  cancelTask(taskId: string): Promise<{ id: string; status: string }>
  updateTaskMetadata(
    taskId: string,
    patch: { resources?: Array<Record<string, unknown>> }
  ): Promise<unknown>
  subscribe(taskId: string, options: LingxiGraphSubscriptionOptions): () => void
  project(task: AgentTaskSnapshot, events: AgentTaskEvent[]): LingxiGraphProjection
}

const AGENT_LABELS: Record<string, string> = {
  coordinator: '图谱协调器',
  intent: '意图智能体',
  adaptive_pedagogy: '自适应教学技能',
  interactive_lecture_deck: '交互式讲义技能',
  interactive_visual_explainer: '交互式可视化讲解技能',
  learner_state_reflector: '学习状态反思器',
  lesson_intro: '课程引入技能',
  quiz_generator: '知识检测技能',
  answer_user: '答疑智能体',
  quiz_submit: '测验提交智能体',
  learning_companion: '即时学习陪伴',
  probe_user: '理解检查',
}

const CONTROL_PLANE_AGENTS = new Set([
  'coordinator',
  'orchestrator',
  'goal_interpreter',
  'goal-interpreter',
  'intent',
  'plan.present',
  'plan_presenter',
])

const LEARNER_FACING_OUTPUT_AGENTS = new Set([
  'learning_companion',
  'learner_interview',
])

const CAPABILITY_LABELS: Record<string, string> = {
  'dialog.answer': '即时答疑',
  'dialog.converse': '即时陪聊',
  'dialog.interview': '了解你的基础',
  'dialog.probe': '检查理解',
  'content.lesson_intro': '生成课程引入',
  'content.deck': '生成互动讲义',
  'content.visual': '生成可视化讲解',
  'assess.generate': '生成知识检测',
  'assess.grade': '批改学习结果',
  'assess.interpret': '分析学习误区',
  'model.reflect': '更新学习状态',
  'meta.report': '整理学习报告',
  'review.schedule': '安排复习计划',
}

const TOOL_LABELS: Record<string, string> = {
  web_search: '检索资料',
  web_fetch: '阅读资料',
  stage_artifact_file: '准备学习产物',
  stage_artifact_files: '准备学习产物',
  read_staged_artifact: '读取学习产物',
  list_staged_artifacts: '列出学习产物',
}

const TERMINAL_TASK_STATUSES = new Set(['handed_off', 'completed', 'partial', 'failed', 'cancelled'])
const TERMINAL_AGENT_EVENTS = new Set(['agent.completed', 'agent.failed'])

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

function agentLabel(agent: string): string {
  return AGENT_LABELS[agent] ?? humanize(agent)
}

function toolLabel(toolName: string): string {
  return TOOL_LABELS[toolName] ?? humanize(toolName)
}

function isSensitiveKey(key: string): boolean {
  return /token|secret|password|authorization|api[_-]?key|content|html|body|data|prompt/i.test(key)
}

/** Keep tool metadata useful for debugging without echoing source material or secrets. */
function sanitizeToolValue(value: unknown, key = ''): unknown {
  if (isSensitiveKey(key) && value !== undefined && value !== null) {
    const serialized = typeof value === 'string' ? value : JSON.stringify(value)
    return `[redacted · ${serialized.length} chars]`
  }
  if (Array.isArray(value)) return value.map((item) => sanitizeToolValue(item, key))
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([entryKey, entryValue]) => [
        entryKey,
        sanitizeToolValue(entryValue, entryKey),
      ])
    )
  }
  if (typeof value === 'string' && value.length > 240) {
    return `${value.slice(0, 240)}…[truncated]`
  }
  return value
}

function safeArgs(value: unknown): Record<string, unknown> | undefined {
  if (value === undefined || value === null) return undefined
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value) as unknown
      return asRecord(sanitizeToolValue(parsed))
    } catch {
      return { value: '[redacted argument string]' }
    }
  }
  const record = asRecord(value)
  return Object.keys(record).length > 0
    ? (sanitizeToolValue(record) as Record<string, unknown>)
    : undefined
}

function safePayloadSummary(value: unknown): string {
  if (value === undefined || value === null) return '没有返回公开结果详情。'
  if (typeof value === 'string') return `已返回结果（${value.length} 个字符）。`
  return '已返回结构化结果。'
}

function eventPayload(event: AgentTaskEvent): Record<string, unknown> {
  return asRecord(event.payload)
}

function eventText(event: AgentTaskEvent): string {
  const payload = eventPayload(event)
  return stringValue(payload.delta) || stringValue(payload.message) || stringValue(payload.text)
}

function eventToolCalls(event: AgentTaskEvent): Array<Record<string, unknown>> {
  const payload = eventPayload(event)
  const calls = Array.isArray(payload.calls)
    ? payload.calls
    : Array.isArray(payload.chunks)
      ? payload.chunks
      : []
  return calls.map(asRecord)
}

function toolCallId(event: AgentTaskEvent, call: Record<string, unknown>, index = 0): string {
  return (
    stringValue(call.id) ||
    stringValue(call.tool_call_id) ||
    stringValue(eventPayload(event).tool_call_id) ||
    `lingxi-tool:${event.sequence}:${index}`
  )
}

function resultToolCallId(event: AgentTaskEvent): string {
  const payload = eventPayload(event)
  return (
    stringValue(payload.tool_call_id) ||
    stringValue(payload.toolCallId) ||
    `lingxi-tool:${event.sequence}`
  )
}

interface AgentRun {
  agent: string
  spanId: string
  skillCallId: string
  startSequence: number
  startedAt?: number
  status: ToolCallStatus
  endSequence?: number
  skillId?: string
}

interface ToolRun {
  id: string
  name: string
  agent?: string
  spanId?: string
  params?: Record<string, unknown>
  firstSequence: number
  startedAt?: number
  status: ToolCallStatus
  result?: ToolCallInfo['result']
}

function eventAgent(event: AgentTaskEvent): string | undefined {
  const agent = stringValue(event.agent)
  return agent && !CONTROL_PLANE_AGENTS.has(agent) ? agent : undefined
}

function reduceAgentRuns(events: AgentTaskEvent[]): AgentRun[] {
  const runs: AgentRun[] = []
  const active = new Map<string, AgentRun>()
  for (const event of events) {
    const agent = eventAgent(event)
    if (!agent) continue
    if (event.kind === 'agent.started' || !active.has(agent)) {
      if (event.kind === 'agent.started' || !active.has(agent)) {
        const run: AgentRun = {
          agent,
          spanId: `lingxi-agent:${agent}:${event.sequence}`,
          skillCallId: `lingxi-skill:${agent}:${event.sequence}`,
          startSequence: event.sequence,
          startedAt: event.ts ? Date.parse(event.ts) || undefined : undefined,
          status: 'executing',
          skillId: stringValue(eventPayload(event).skill) || undefined,
        }
        runs.push(run)
        active.set(agent, run)
      }
    }
    const run = active.get(agent)
    if (!run) continue
    if (event.kind === 'agent.completed') {
      run.status = 'success'
      run.endSequence = event.sequence
      active.delete(agent)
    } else if (event.kind === 'agent.failed') {
      run.status = 'error'
      run.endSequence = event.sequence
      active.delete(agent)
    }
  }
  return runs
}

function reduceToolRuns(events: AgentTaskEvent[], runs: AgentRun[]): ToolRun[] {
  const tools = new Map<string, ToolRun>()
  const runFor = (agent: string | undefined, sequence: number): AgentRun | undefined => {
    if (!agent) return undefined
    return [...runs].reverse().find((run) => run.agent === agent && run.startSequence <= sequence)
  }

  for (const event of events) {
    const agent = eventAgent(event)
    if (event.kind === 'tool.call.delta') {
      for (const [index, call] of eventToolCalls(event).entries()) {
        const id = toolCallId(event, call, index)
        const run = runFor(agent, event.sequence)
        const current = tools.get(id)
        const args = safeArgs(call.args ?? call.arguments)
        tools.set(id, {
          id,
          name: stringValue(call.name) || current?.name || 'tool',
          agent: agent ?? current?.agent,
          spanId: run?.spanId ?? current?.spanId,
          params: args ?? current?.params,
          firstSequence: current?.firstSequence ?? event.sequence,
          startedAt:
            current?.startedAt ?? (event.ts ? Date.parse(event.ts) || undefined : undefined),
          status:
            current?.status === 'success' || current?.status === 'error'
              ? current.status
              : 'executing',
          result: current?.result,
        })
      }
    } else if (event.kind === 'tool.result') {
      const payload = eventPayload(event)
      const id = resultToolCallId(event)
      const run = runFor(agent, event.sequence)
      const current = tools.get(id)
      const failed = ['error', 'failed', 'failure'].includes(
        stringValue(payload.status).toLowerCase()
      )
      tools.set(id, {
        id,
        name: stringValue(payload.name) || current?.name || 'tool',
        agent: agent ?? current?.agent,
        spanId: run?.spanId ?? current?.spanId,
        params: current?.params ?? safeArgs(payload.arguments),
        firstSequence: current?.firstSequence ?? event.sequence,
        startedAt: current?.startedAt ?? (event.ts ? Date.parse(event.ts) || undefined : undefined),
        status: failed ? 'error' : 'success',
        result: {
          success: !failed,
          output: safePayloadSummary(payload.output ?? payload.content ?? payload.result),
        error: failed ? stringValue(payload.error) || '工具执行失败。' : undefined,
        },
      })
    }
  }
  return [...tools.values()].sort((a, b) => a.firstSequence - b.firstSequence)
}

function reasoningStep(
  id: string,
  title: string,
  summary: string,
  status: ReasoningStep['status'],
  timestamp?: number,
  endedAt?: number
): ReasoningStep {
  return { id, title, summary, status, timestamp, endedAt }
}

function reduceReasoningSteps(
  _task: AgentTaskSnapshot,
  events: AgentTaskEvent[],
  _runs: AgentRun[],
  _tools: ToolRun[]
): ReasoningStep[] {
  // The plan card is a projection of the current orchestration decision, not
  // a debug trace.  Raw loop nodes have no learner-facing task identity and
  // previously created the repeated “执行学习计划” entries.
  const steps = new Map<string, ReasoningStep>()
  let currentPlan = ''

  for (const event of events) {
    const timestamp = event.ts ? Date.parse(event.ts) || undefined : undefined
    const payload = eventPayload(event)
    if (event.kind === 'plan.created' || event.kind === 'plan.replanned') {
      currentPlan = stringValue(payload.decision_id) || `decision-${event.sequence}`
      steps.clear()
      const planTasks = Array.isArray(payload.tasks) ? payload.tasks : []
      for (const rawTask of planTasks) {
        const planned = asRecord(rawTask)
        const taskId = stringValue(planned.id)
        const capability = stringValue(planned.capability)
        if (!taskId || !capability) continue
        steps.set(
          `${currentPlan}:${taskId}`,
          reasoningStep(
            `${currentPlan}:${taskId}`,
            CAPABILITY_LABELS[capability] ?? capability,
            stringValue(planned.rationale) || '等待执行。',
            'pending',
            timestamp
          )
        )
      }
      continue
    }
    if (!currentPlan || !['node.started', 'node.retrying', 'node.held', 'node.revising', 'node.appeared', 'node.completed', 'node.failed'].includes(event.kind)) continue
    {
      const taskId = stringValue(payload.task_id)
      if (!taskId) continue
      const id = `${currentPlan}:${taskId}`
      const existing = steps.get(id)
      // Ignore internal graph nodes and only update tasks present in the
      // latest user-visible plan snapshot.
      if (!existing) continue
      steps.set(
        id,
        reasoningStep(
          id,
          existing.title,
          event.kind === 'node.retrying' || event.kind === 'node.revising' || event.kind === 'node.held'
            ? '正在根据新的学习证据重试。'
            : stringValue(payload.detail) || existing.summary,
          event.kind === 'node.failed'
            ? 'error'
            : event.kind === 'node.completed'
              ? 'complete'
              : event.kind === 'node.appeared'
                ? 'pending'
                : 'active',
          existing.timestamp ?? timestamp,
          event.kind === 'node.completed' || event.kind === 'node.failed' ? timestamp : undefined
        )
      )
    }
  }

  return [...steps.values()]
}

function skillToolInfo(run: AgentRun): ToolCallInfo {
  return {
    id: run.skillCallId,
    name: `lingxi_skill_${run.agent}`,
    displayTitle: run.skillId ? `${agentLabel(run.agent)} · ${run.skillId}` : agentLabel(run.agent),
    status: run.status,
    params: run.skillId ? { skillId: run.skillId } : undefined,
    calledBy: run.agent,
    startedAtMs: run.startedAt,
  }
}

function toolInfo(tool: ToolRun): ToolCallInfo {
  return {
    id: tool.id,
    name: tool.name,
    displayTitle: toolLabel(tool.name),
    status: tool.status,
    params: tool.params,
    calledBy: tool.agent,
    result: tool.result,
    startedAtMs: tool.startedAt,
  }
}

function isTerminal(task: AgentTaskSnapshot): boolean {
  return TERMINAL_TASK_STATUSES.has(task.status)
}

function quizQuestionTag(task: AgentTaskSnapshot): string | null {
  const quiz = task.artifacts.quiz?.data
  if (!quiz || task.quiz_submission) return null
  const questions = quiz.questions.map((question) => ({
    type:
      question.type === 'multi_choice'
        ? 'multi_select'
        : question.type === 'short_text'
          ? 'single_select'
          : 'single_select',
    prompt: question.prompt,
    options:
      question.options.length > 0
        ? question.options
        : [{ id: `${question.id}-free-text`, label: '直接输入答案' }],
  }))
  return questions.length > 0 ? `<question>${JSON.stringify(questions)}</question>` : null
}

/**
 * Converts the durable LingxiGraph event log to the shared chat transcript
 * contract.
 * `reasoning.delta` is deliberately absent: only the safe phase summaries
 * created by reduceReasoningSteps can become `thinking` blocks.
 */
export function projectLingxiGraphEvents(
  task: AgentTaskSnapshot,
  inputEvents: AgentTaskEvent[] = []
): LingxiGraphProjection {
  const events = [...new Map(inputEvents.map((event) => [event.sequence, event])).values()].sort(
    (a, b) => a.sequence - b.sequence
  )
  const runs = reduceAgentRuns(events)
  const tools = reduceToolRuns(events, runs)
  if (isTerminal(task)) {
    const terminalStatus: ToolCallStatus = task.status === 'failed' ? 'error' : 'success'
    for (const run of runs) {
      if (run.status === 'executing') run.status = terminalStatus
    }
    for (const tool of tools) {
      if (tool.status === 'executing') tool.status = terminalStatus
    }
  }
  const safeSteps = reduceReasoningSteps(task, events, runs, tools)
  const blocks: ContentBlock[] = safeSteps.map((step) => ({
    type: 'thinking',
    reasoningStep: step,
    timestamp: step.timestamp,
  }))
  const emittedRuns = new Set<string>()
  const emittedTools = new Set<string>()
  const streamedOutputBlocks = new Map<string, number>()
  let assistantText = ''

  for (const event of events) {
    const agent = eventAgent(event)
    const run = agent
      ? [...runs]
          .reverse()
          .find(
            (candidate) =>
              candidate.agent === agent &&
              candidate.startSequence <= event.sequence &&
              (!candidate.endSequence || candidate.endSequence >= event.sequence)
          )
      : undefined
    if (run && !emittedRuns.has(run.spanId)) {
      emittedRuns.add(run.spanId)
      blocks.push({
        type: 'subagent',
        content: run.agent,
        subagent: run.agent,
        spanId: run.spanId,
        parentSpanId: 'main',
        timestamp: run.startSequence,
      })
      blocks.push({
        type: 'tool_call',
        toolCall: skillToolInfo(run),
        spanId: run.spanId,
        parentSpanId: 'main',
        timestamp: run.startSequence,
      })
    }
    if (run && run.endSequence === event.sequence) {
      blocks.push({
        type: 'subagent',
        content: run.agent,
        subagent: run.agent,
        spanId: run.spanId,
        parentSpanId: 'main',
        timestamp: event.sequence,
        endedAt: event.sequence,
      })
    }

    if (event.kind === 'tool.call.delta' || event.kind === 'tool.result') {
      const related =
        event.kind === 'tool.call.delta'
          ? eventToolCalls(event).map((call, index) => toolCallId(event, call, index))
          : [resultToolCallId(event)]
      for (const id of related) {
        if (emittedTools.has(id)) continue
        const tool = tools.find((candidate) => candidate.id === id)
        if (!tool) continue
        emittedTools.add(id)
        blocks.push({
          type: 'tool_call',
          toolCall: toolInfo(tool),
          spanId: tool.spanId,
          parentSpanId: 'main',
          timestamp: tool.firstSequence,
        })
      }
      continue
    }

    if (event.kind === 'assistant.delta' || event.kind === 'agent.output' || event.kind === 'agent.output.delta') {
      const text = eventText(event)
      if (!text) continue
      const learnerFacingOutput =
        event.kind === 'agent.output' && LEARNER_FACING_OUTPUT_AGENTS.has(String(event.agent ?? ''))
      const deltaOutput =
        event.kind === 'agent.output.delta' && LEARNER_FACING_OUTPUT_AGENTS.has(String(event.agent ?? ''))
      if (deltaOutput) {
        const streamId = stringValue(eventPayload(event).stream_id) || String(event.agent ?? 'learner')
        const existingIndex = streamedOutputBlocks.get(streamId)
        if (existingIndex === undefined) {
          streamedOutputBlocks.set(streamId, blocks.length)
          blocks.push({ type: 'text', content: text, timestamp: event.sequence })
        } else {
          const block = blocks[existingIndex]
          block.content = `${block.content ?? ''}${text}`
        }
        assistantText += text
      } else if (learnerFacingOutput) {
        const streamId = stringValue(eventPayload(event).stream_id)
        if (streamId && streamedOutputBlocks.has(streamId)) continue
        assistantText += `${assistantText ? '\n\n' : ''}${text}`
        blocks.push({ type: 'text', content: text, timestamp: event.sequence })
      }
      // Never project assistant.delta: it is raw model/tool reasoning and may
      // contain partial JSON. Providers explicitly emit safe agent.output.
      continue
    }

    if (event.kind === 'task.completed') {
      const summary =
        eventPayload(event).status === 'partial'
          ? '当前学习产物已准备好，可查看。'
          : '学习任务已完成。'
      if (!assistantText) {
        assistantText = summary
        blocks.push({ type: 'text', content: summary, timestamp: event.sequence })
      }
    } else if (
      ['task.failed', 'task.cancelled', 'run.failed', 'run.cancelled', 'run.timed_out', 'run.budget_exceeded'].includes(event.kind) &&
      !assistantText
    ) {
      assistantText =
        event.kind === 'task.cancelled' || event.kind === 'run.cancelled'
          ? '学习任务已取消。'
          : event.kind === 'run.timed_out'
            ? '学习任务运行超时。'
            : event.kind === 'run.budget_exceeded'
              ? '学习任务超出了资源预算。'
              : task.error || '学习任务未能完成。'
      blocks.push({ type: 'text', content: assistantText, timestamp: event.sequence })
    }
  }

  const question = quizQuestionTag(task)
  if (question && !assistantText.includes('<question>')) {
    assistantText = `${assistantText ? `${assistantText}\n\n` : ''}${question}`
    blocks.push({ type: 'text', content: question })
  }

  return {
    blocks,
    assistantText,
    isTerminal:
      isTerminal(task) ||
      events.some((event) =>
        [
          'task.completed',
          'task.failed',
          'task.cancelled',
          'run.completed',
          'run.ended',
          'run.failed',
          'run.cancelled',
          'run.timed_out',
          'run.budget_exceeded',
        ].includes(event.kind)
      ),
  }
}

export function createLingxiGraphAdapter(): LingxiGraphChatAdapter {
  return {
    kind: LINGXI_GRAPH_ADAPTER_KIND,
    createTask: api.createAgentTask,
    loadTask: api.agentTask,
    sendMessage: api.agentMessage,
    cancelTask: api.cancelAgentTask,
    updateTaskMetadata: (taskId, patch) => api.updateAgentTask(taskId, patch),
    subscribe(taskId, options) {
      return subscribeAgentEvents(taskId, options.onEvent, {
        from: options.from,
        onEnd: options.onEnd,
      })
    },
    project: projectLingxiGraphEvents,
  }
}
