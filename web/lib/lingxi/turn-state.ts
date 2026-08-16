import type { AgentTaskEvent, AgentTaskSnapshot } from './types'
import { isAgentTaskTerminal } from './types'

/** The browser-visible lifecycle of one learner turn. */
export type LingxiTurnState = 'idle' | 'active' | 'awaiting_user' | 'terminal'

const TERMINAL_EVENT_KINDS = new Set([
  'task.completed',
  'task.failed',
  'task.cancelled',
  'run.completed',
  'run.ended',
  'run.failed',
  'run.cancelled',
  'run.timed_out',
  'run.budget_exceeded',
])

const AWAITING_EVENT_KINDS = new Set([
  'interrupt.raised',
  'run.paused',
  'task.awaiting_user',
  'turn.awaiting_user',
  'awaiting_user',
])

const ACTIVE_EVENT_KINDS = new Set([
  'task.started',
  'task.queued',
  'run.started',
  'run.resumed',
  'run.step',
  'node.started',
  'node.completed',
  'agent.started',
  'agent.completed',
  'model.started',
  'model.completed',
  'assistant.delta',
  'agent.output',
  'tool.call.delta',
  'tool.result',
])

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value.trim().toLowerCase() : ''
}

function payloadStatus(event: AgentTaskEvent): string {
  const payload = event.payload ?? {}
  return stringValue(
    payload.status ??
      payload.task_status ??
      payload.taskStatus ??
      payload.turn_status ??
      payload.turnStatus
  )
}

function stateForStatus(status: string): LingxiTurnState | undefined {
  if (!status) return undefined
  if (['awaiting_user', 'awaiting-user', 'paused', 'waiting'].includes(status)) {
    return 'awaiting_user'
  }
  if (
    [
      'completed',
      'delivered',
      'handed_off',
      'failed',
      'cancelled',
      'timed_out',
      'budget_exceeded',
      'partial',
    ].includes(status)
  ) {
    return 'terminal'
  }
  if (['queued', 'running', 'active', 'resumed'].includes(status)) return 'active'
  return undefined
}

/** Convert the authoritative task snapshot into the single UI turn state. */
export function turnStateFromTask(task: AgentTaskSnapshot | null | undefined): LingxiTurnState {
  if (!task) return 'idle'
  if (isAgentTaskTerminal(task)) return 'terminal'
  if (task.status === 'awaiting_user' || task.turnStatus === 'awaiting_user') {
    return 'awaiting_user'
  }
  if (['queued', 'running'].includes(task.status) || task.turnStatus === 'active') {
    return 'active'
  }
  return 'idle'
}

/** Apply one durable event without making the SSE connection's close signal authoritative. */
export function reduceLingxiTurnState(
  current: LingxiTurnState,
  event: AgentTaskEvent
): LingxiTurnState {
  if (TERMINAL_EVENT_KINDS.has(event.kind)) return 'terminal'
  if (AWAITING_EVENT_KINDS.has(event.kind)) return 'awaiting_user'
  const statusState = stateForStatus(payloadStatus(event))
  if (statusState) return statusState
  if (ACTIVE_EVENT_KINDS.has(event.kind)) return 'active'
  return current
}

/** Replay an event log while preserving the task snapshot as its authority. */
export function reconcileLingxiTurnState(
  task: AgentTaskSnapshot | null | undefined,
  events: AgentTaskEvent[]
): LingxiTurnState {
  const snapshotState = turnStateFromTask(task)
  if (snapshotState === 'terminal') return 'terminal'
  let replayState: LingxiTurnState = 'idle'
  for (const event of [...events].sort((left, right) => left.sequence - right.sequence)) {
    replayState = reduceLingxiTurnState(replayState, event)
  }
  // A loaded awaiting snapshot is authoritative even when the replay cursor
  // contains older activity. Conversely, a just-persisted interrupt can be
  // visible in the event log before the task row catches up.
  if (snapshotState === 'awaiting_user' || replayState === 'awaiting_user') {
    return 'awaiting_user'
  }
  if (replayState === 'terminal') return 'terminal'
  return snapshotState === 'active' ? 'active' : replayState
}

export function isLearnerTurn(state: LingxiTurnState): boolean {
  return state === 'awaiting_user'
}
