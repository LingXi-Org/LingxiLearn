import { api, subscribeAgentEvents } from '@/lib/lingxi/api'
import type { AgentTaskEvent, AgentTaskSnapshot } from '@/lib/lingxi/types'
import type {
  ContentBlock,
  ReasoningStep,
  ToolCallInfo,
  ToolCallStatus,
} from '@/app/workspace/[workspaceId]/home/types'

export const LINGXI_GRAPH_ADAPTER_KIND = 'lingxigraph' as const

export interface LingxiGraphProjection {
  blocks: ContentBlock[]
  assistantText: string
  isTerminal: boolean
}

export interface LingxiGraphSubscriptionOptions {
  from?: number
  onEvent: (event: AgentTaskEvent) => void
  onEnd?: (status: string) => void
  onError?: (error: Error) => void
}

export interface LingxiGraphChatAdapter {
  readonly kind: typeof LINGXI_GRAPH_ADAPTER_KIND
  createTask(prompt: string): Promise<{ id: string; status: string }>
  loadTask(taskId: string): Promise<AgentTaskSnapshot>
  sendMessage(taskId: string, message: string): Promise<{ status: string }>
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
  return agent && agent !== 'coordinator' ? agent : undefined
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
  task: AgentTaskSnapshot,
  events: AgentTaskEvent[],
  runs: AgentRun[],
  tools: ToolRun[]
): ReasoningStep[] {
  const steps = new Map<string, ReasoningStep>()
  const upsert = (step: ReasoningStep) => steps.set(step.id, step)
  const terminal = TERMINAL_TASK_STATUSES.has(task.status)

  for (const event of events) {
    const timestamp = event.ts ? Date.parse(event.ts) || undefined : undefined
    const payload = eventPayload(event)
    if (event.kind === 'task.started') {
      upsert(
        reasoningStep(
          'task',
          '准备学习任务',
          '学习任务已创建，智能体图正在启动。',
          terminal ? 'complete' : 'active',
          timestamp
        )
      )
    } else if (event.kind === 'intent.started') {
      upsert(
        reasoningStep(
          'intent',
          '理解学习目标',
          '智能体图正在识别你的意图与学习范围。',
          'active',
          timestamp
        )
      )
    } else if (event.kind === 'intent.completed') {
      const topic = stringValue(payload.topic)
      upsert(
        reasoningStep(
          'intent',
          '理解学习目标',
          topic
            ? `智能体图识别到主题“${topic.slice(0, 120)}”。`
            : '智能体图已识别学习意图。',
          'complete',
          timestamp,
          timestamp
        )
      )
    } else if (event.kind === 'agent.started') {
      const run = runs.find(
        (candidate) =>
          candidate.startSequence === event.sequence && candidate.agent === eventAgent(event)
      )
      if (run)
        upsert(
          reasoningStep(
            `agent:${run.startSequence}`,
            agentLabel(run.agent),
            `${agentLabel(run.agent)}已开始这一学习阶段。`,
            run.status === 'executing' ? 'active' : run.status === 'error' ? 'error' : 'complete',
            timestamp
          )
        )
    } else if (event.kind === 'agent.completed' || event.kind === 'agent.failed') {
      const run = [...runs]
        .reverse()
        .find(
          (candidate) =>
            candidate.agent === eventAgent(event) && candidate.endSequence === event.sequence
        )
      if (run)
        upsert(
          reasoningStep(
            `agent:${run.startSequence}`,
            agentLabel(run.agent),
            event.kind === 'agent.failed'
              ? `${agentLabel(run.agent)}未能完成这一阶段。`
              : `${agentLabel(run.agent)}已完成这一阶段。`,
            event.kind === 'agent.failed' ? 'error' : 'complete',
            undefined,
            timestamp
          )
        )
    } else if (event.kind === 'artifact.ready') {
      const artifact = stringValue(payload.artifact)
      upsert(
        reasoningStep(
          `artifact:${artifact || event.sequence}`,
          '准备学习产物',
          artifact
            ? `${humanize(artifact)}产物已准备好，可查看。`
            : '学习产物已准备好，可查看。',
          'complete',
          timestamp,
          timestamp
        )
      )
    } else if (event.kind === 'task.completed') {
      upsert(
        reasoningStep(
          'task',
          '准备学习任务',
          payload.status === 'partial'
            ? '当前学习产物已准备好，但部分阶段只完成了一部分。'
            : '学习任务及其产物已完成。',
          'complete',
          undefined,
          timestamp
        )
      )
      upsert(
        reasoningStep(
          'finish',
          '总结学习结果',
          '智能体图已返回当前学习结果。',
          'complete',
          timestamp,
          timestamp
        )
      )
    } else if (event.kind === 'task.failed') {
      upsert(
        reasoningStep(
          'finish',
          '总结学习结果',
          '智能体图在全部学习产物准备完成前停止了。',
          'error',
          timestamp,
          timestamp
        )
      )
    } else if (event.kind === 'node.started' || event.kind === 'node.retrying') {
      upsert(
        reasoningStep(
          `node:${event.sequence}`,
          '推进智能体图',
          event.kind === 'node.retrying'
            ? '图节点正在结合当前上下文重试。'
            : '智能体图正在推进到下一个节点。',
          'active',
          timestamp
        )
      )
    }
  }

  for (const tool of tools) {
    upsert(
      reasoningStep(
        `tool:${tool.id}`,
        toolLabel(tool.name),
        tool.status === 'executing'
          ? `智能体图正在通过“${toolLabel(tool.name)}”收集依据。`
          : tool.status === 'error'
            ? `${toolLabel(tool.name)}返回了错误；智能体图正在保留安全状态。`
            : `${toolLabel(tool.name)}已为当前阶段返回结果。`,
        tool.status === 'executing' ? 'active' : tool.status === 'error' ? 'error' : 'complete',
        tool.startedAt,
        tool.status === 'executing' ? undefined : tool.startedAt
      )
    )
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

/**
 * Converts the durable LingxiGraph event log to Sim's transcript contract.
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

    if (event.kind === 'assistant.delta' || event.kind === 'agent.output') {
      const text = eventText(event)
      if (!text) continue
      if (event.kind === 'agent.output' && event.agent === 'adaptive_pedagogy') {
        // The deep-dive graph has exactly one learner-facing writer. Keep its
        // latest Chinese response in the chat body while retaining the run
        // block for the debug trace.
        assistantText = text
      }
      if (event.kind === 'assistant.delta' && !agent) {
        assistantText += text
        blocks.push({ type: 'text', content: text, timestamp: event.sequence })
      } else if (agent && run) {
        blocks.push({
          type: 'subagent_text',
          content: text,
          subagent: agent,
          spanId: run.spanId,
          parentSpanId: 'main',
          timestamp: event.sequence,
        })
      }
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
    } else if (event.kind === 'task.failed' && !assistantText) {
      assistantText = task.error || '学习任务未能完成。'
      blocks.push({ type: 'text', content: assistantText, timestamp: event.sequence })
    }
  }

  return {
    blocks,
    assistantText,
    isTerminal:
      isTerminal(task) ||
      events.some((event) => event.kind === 'task.completed' || event.kind === 'task.failed'),
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
