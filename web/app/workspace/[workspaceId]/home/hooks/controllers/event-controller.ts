import type { LingxiTurnState } from '@/lib/lingxi/turn-state'
import type { AgentTaskEvent } from '@/lib/lingxi/types'

export const RUNTIME_GRAPH_REFRESH_EVENTS = new Set([
  'run.started',
  'run.resumed',
  'round.started',
  'decision.recorded',
  'node.started',
  'node.completed',
  'node.failed',
  'node.held',
  'node.revising',
  'agent.started',
  'agent.completed',
  'agent.failed',
])

/** Pure V1 turn/run lifecycle reducer; V0 remains in turn-state as fallback. */
export function reduceV1TurnState(
  current: LingxiTurnState,
  envelope: { type: string; payload: Record<string, unknown> }
): LingxiTurnState {
  const status = typeof envelope.payload.status === 'string' ? envelope.payload.status : ''
  switch (envelope.type) {
    case 'turn':
      if (status === 'started' || status === 'resumed') return 'active'
      if (status === 'awaiting_user') return 'awaiting_user'
      if (status === 'delivered' || status === 'failed' || status === 'cancelled') return 'terminal'
      return current
    case 'run':
      if (status === 'started' || status === 'resumed') return 'active'
      if (status === 'checkpoint_pause') return 'awaiting_user'
      return current
    case 'span':
    case 'tool':
      return 'active'
    default:
      return current
  }
}

/** Replay-safe merge shared by initial history and SSE reconnect delivery. */
export function mergeAgentTaskEvent(
  current: AgentTaskEvent[],
  incoming: AgentTaskEvent
): AgentTaskEvent[] {
  if (current.some((event) => event.sequence === incoming.sequence)) return current
  return [...current, incoming].sort((left, right) => left.sequence - right.sequence)
}
