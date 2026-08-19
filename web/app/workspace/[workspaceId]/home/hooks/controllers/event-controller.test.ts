import type { AgentTaskEvent } from '@/lib/lingxi/types'
import { mergeAgentTaskEvent, reduceV1TurnState } from './event-controller'

describe('V1 turn-state reducer', () => {
  it('is deterministic and leaves unrelated events unchanged', () => {
    const events = [
      { type: 'turn', payload: { status: 'started' } },
      { type: 'run', payload: { status: 'checkpoint_pause' } },
      { type: 'turn', payload: { status: 'delivered' } },
    ]
    const reduce = () => events.reduce((state, event) => reduceV1TurnState(state, event), 'idle' as const)
    expect(reduce()).toBe('terminal')
    expect(reduce()).toBe('terminal')
    expect(reduceV1TurnState('awaiting_user', { type: 'text', payload: {} })).toBe('awaiting_user')
  })
})

describe('SSE replay merge', () => {
  it('deduplicates reconnect events and preserves sequence order', () => {
    const event = (sequence: number) => ({ sequence }) as AgentTaskEvent
    const current = [event(1), event(3)]
    expect(mergeAgentTaskEvent(current, event(2)).map((item) => item.sequence)).toEqual([1, 2, 3])
    expect(mergeAgentTaskEvent(current, event(1))).toBe(current)
  })
})
