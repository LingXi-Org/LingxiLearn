export const AGENT_EVENT_KINDS = [
  'task.started',
  'task.completed',
  'task.failed',
  'task.cancelled',
  'intent.started',
  'intent.completed',
  'agent.started',
  'agent.completed',
  'agent.failed',
  'reasoning.delta',
  'assistant.delta',
  'tool.call.delta',
  'tool.result',
  'model.started',
  'model.completed',
  'model.usage',
  'node.appeared',
  'node.started',
  'node.completed',
  'node.failed',
  'node.retrying',
  'node.cached',
  'interrupt.raised',
  'artifact.ready',
  'artifact.recovered',
  'sidecar.started',
  'sidecar.completed',
  'sidecar.failed',
  'schedule.proposed',
  'schedule.permission',
  'plan.created',
  'plan.replanned',
  'state.updated',
  'run.started',
  'run.resumed',
  'run.paused',
  'run.ended',
  'run.completed',
  'run.failed',
  'run.cancelled',
  'run.timed_out',
  'run.budget_exceeded',
] as const

export type AgentEventKind = (typeof AGENT_EVENT_KINDS)[number]

export const TERMINAL_AGENT_EVENT_KINDS = new Set<string>([
  'task.completed',
  'task.failed',
  'task.cancelled',
  'run.ended',
  'run.completed',
  'run.failed',
  'run.cancelled',
  'run.timed_out',
  'run.budget_exceeded',
])

export function isKnownAgentEventKind(kind: string): kind is AgentEventKind {
  return (AGENT_EVENT_KINDS as readonly string[]).includes(kind)
}

