import { describe, expect, it } from 'vitest'
import type { AgentTaskEvent, AgentTaskSnapshot } from './types'
import {
  reconcileLingxiTurnState,
  reduceLingxiTurnState,
  turnStateFromTask,
} from './turn-state'

function task(overrides: Partial<AgentTaskSnapshot> = {}): AgentTaskSnapshot {
  return {
    id: 'task-1',
    status: 'queued',
    prompt: 'Explain packet retransmission',
    graph_version: 'lingxi.v1',
    intent: {},
    agents: {},
    artifacts: {
      lesson_intro: { available: false, url: '' },
      lecture_deck: { available: false, url: '' },
      quiz: { available: false, data: null },
      visual: { available: false, url: '' },
    },
    delivery: { order: [], queue: [], cursor: 0 },
    quiz_submission: null,
    error: '',
    created_at: null,
    updated_at: null,
    ...overrides,
  }
}

function event(
  sequence: number,
  kind: string,
  payload: Record<string, unknown> = {}
): AgentTaskEvent {
  return {
    sequence,
    kind,
    agent: 'coordinator',
    payload,
    ts: null,
  }
}

describe('Lingxi turn lifecycle', () => {
  it('maps task snapshots to one lifecycle state', () => {
    expect(turnStateFromTask(task({ status: 'running' }))).toBe('active')
    expect(turnStateFromTask(task({ status: 'awaiting_user' }))).toBe('awaiting_user')
    expect(turnStateFromTask(task({ status: 'completed' }))).toBe('terminal')
  })

  it('keeps interrupt waiting independent from SSE stream end', () => {
    let state = reduceLingxiTurnState('idle', event(1, 'run.started'))
    state = reduceLingxiTurnState(state, event(2, 'interrupt.raised'))
    expect(state).toBe('awaiting_user')

    state = reduceLingxiTurnState(state, event(3, 'run.resumed'))
    expect(state).toBe('active')
    expect(reduceLingxiTurnState(state, event(4, 'run.ended'))).toBe('terminal')
  })

  it('lets lifecycle event kinds override stale payload status', () => {
    expect(
      reduceLingxiTurnState('active', event(1, 'interrupt.raised', { status: 'running' }))
    ).toBe('awaiting_user')
    expect(
      reduceLingxiTurnState('active', event(2, 'task.completed', { status: 'running' }))
    ).toBe('terminal')
  })

  it('reconciles a persisted interrupt before the task row catches up', () => {
    expect(
      reconcileLingxiTurnState(task({ status: 'running' }), [
        event(1, 'run.started'),
        event(2, 'interrupt.raised'),
      ])
    ).toBe('awaiting_user')
    expect(
      reconcileLingxiTurnState(task({ status: 'awaiting_user' }), [event(1, 'run.started')])
    ).toBe('awaiting_user')
  })
})
