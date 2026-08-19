import { describe, expect, it } from 'vitest'
import type { AgentTaskEvent, AgentTaskSnapshot } from '@/lib/lingxi/types'
import { assertV0History, projectLingxiGraphV0History } from './lingxi-graph-v0'

const task = { id: 'legacy-task', status: 'completed' } as AgentTaskSnapshot

function event(
  sequence: number,
  kind: string,
  agent: string,
  payload: Record<string, unknown>
): AgentTaskEvent {
  return { sequence, kind, agent, payload, ts: null }
}

describe('legacy V0 history reader', () => {
  it('keeps only explicit learner-facing output and question text', () => {
    const projection = projectLingxiGraphV0History(task, [
      event(1, 'agent.output', 'prerequisite_analyzer', { message: 'private analysis' }),
      event(2, 'agent.output', 'answer_user', { message: 'Visible answer.' }),
      event(3, 'interrupt.raised', 'coordinator', { prompt: 'Continue?' }),
    ])

    expect(projection.assistantText).toBe('Visible answer.\n\nContinue?')
    expect(projection.assistantText).not.toContain('private')
    expect(projection.blocks).toHaveLength(1)
    expect(projection.isTerminal).toBe(true)
  })

  it('does not synthesize V0 run, tool, or plan identities', () => {
    const projection = projectLingxiGraphV0History(task, [
      event(1, 'agent.started', 'lesson_intro', { skill: 'lesson-intro' }),
      event(2, 'tool.result', 'lesson_intro', { tool_call_id: 'tool-1', result: 'private' }),
      event(3, 'plan.created', 'coordinator', { steps: ['private'] }),
    ])

    expect(projection).toMatchObject({ assistantText: '', blocks: [] })
  })

  it('rejects canonical and malformed V1-shaped rows', () => {
    const v1 = event(1, 'v1.span', '', {
      v: 1,
      seq: 1,
      type: 'span',
      stream: {},
      scope: {},
    })
    expect(() => assertV0History([v1])).toThrow(/rejects Mothership Stream V1/)

    const shaped = event(2, 'unknown', '', {
      seq: 2,
      type: 'tool',
      stream: {},
      scope: {},
    })
    expect(() => assertV0History([shaped])).toThrow(/rejects Mothership Stream V1/)
  })
})
