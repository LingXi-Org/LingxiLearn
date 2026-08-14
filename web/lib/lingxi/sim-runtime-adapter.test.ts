import { describe, expect, it } from 'vitest'
import { applySimRuntimeEvent, replaySimRuntimeEvents } from './sim-runtime-adapter'
import type { AgentTaskEvent, SimExecutionSnapshot } from './types'

const snapshot: SimExecutionSnapshot = {
  executionId: 'exec-1',
  workflowId: 'lingxi-agent',
  workflowState: { blocks: { a: { status: 'completed' } } },
  traceSpans: [],
  executionMetadata: { trigger: 'agent-task', startedAt: '2026-08-14T00:00:00Z', cost: null },
}

describe('Sim runtime transport adapter', () => {
  it('keeps the server execution id and runtime metadata during replay', () => {
    const event: AgentTaskEvent = {
      sequence: 1,
      kind: 'node.started',
      agent: 'intent',
      payload: {},
      ts: null,
      execution_id: 'exec-1',
      runtime: { run_id: 'run-1', step: 2, node: 'recognize_intent' },
    }
    const state = applySimRuntimeEvent(replaySimRuntimeEvents(snapshot, []), event)
    expect(state.executionId).toBe('exec-1')
    expect(state.events[0].runtime?.run_id).toBe('run-1')
  })
})
