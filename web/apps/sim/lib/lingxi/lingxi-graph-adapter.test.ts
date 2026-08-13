import { describe, expect, it } from 'vitest'
import { projectLingxiGraphEvents } from './lingxi-graph-adapter'
import type { AgentTaskEvent, AgentTaskSnapshot } from './types'

const task: AgentTaskSnapshot = {
  id: 'task-1',
  status: 'completed',
  prompt: 'Explain packet retransmission',
  graph_version: 'knowledge_deep_dive.v1',
  intent: { topic: 'packet retransmission' },
  agents: {
    intent: { status: 'completed' },
    lecture_hook: { status: 'completed' },
    interactive_lecture_deck: { status: 'pending' },
    quiz_generator: { status: 'pending' },
    interactive_visual_explainer: { status: 'pending' },
    adaptive_pedagogy: { status: 'pending' },
    curriculum_graph_builder: { status: 'pending' },
  },
  artifacts: {
    lesson_intro: { available: true, url: '/api/artifacts/intro' },
    lecture_deck: { available: false, url: '' },
    quiz: { available: false, data: null },
    visual: { available: false, url: '' },
    knowledge_graph: { available: false, url: '', status: 'pending' },
  },
  quiz_submission: null,
  error: '',
  created_at: null,
  updated_at: null,
}

function event(
  sequence: number,
  kind: string,
  agent: string,
  payload: Record<string, unknown>
): AgentTaskEvent {
  return { sequence, kind, agent, payload, ts: null }
}

describe('LingxiGraph Sim adapter', () => {
  it('projects skills and tools into safe Sim blocks without exposing reasoning deltas', () => {
    const projection = projectLingxiGraphEvents(task, [
      event(1, 'task.started', 'coordinator', {}),
      event(2, 'intent.started', 'intent', {}),
      event(3, 'reasoning.delta', 'intent', { delta: 'private chain of thought' }),
      event(4, 'intent.completed', 'intent', { topic: 'packet retransmission' }),
      event(5, 'agent.started', 'lesson_intro', { skill: 'lesson-intro' }),
      event(6, 'tool.call.delta', 'lesson_intro', {
        calls: [
          {
            id: 'tool-1',
            name: 'web_search',
            args: { query: 'retransmission', content: 'secret source' },
          },
        ],
      }),
      event(7, 'tool.result', 'lesson_intro', {
        tool_call_id: 'tool-1',
        name: 'web_search',
        status: 'success',
        content: 'private fetched page',
      }),
      event(8, 'agent.completed', 'lesson_intro', {}),
      event(9, 'assistant.delta', 'coordinator', { delta: 'The lesson intro is ready.' }),
      event(10, 'task.completed', 'coordinator', {}),
    ])

    expect(
      projection.blocks.some((block) => block.content?.includes('private chain of thought'))
    ).toBe(false)
    expect(projection.blocks.some((block) => block.content?.includes('private fetched page'))).toBe(
      false
    )
    expect(
      projection.blocks.some((block) => block.reasoningStep?.summary.includes('private'))
    ).toBe(false)

    const skillCall = projection.blocks.find(
      (block) => block.type === 'tool_call' && block.toolCall?.name === 'lingxi_skill_lesson_intro'
    )
    const toolCall = projection.blocks.find(
      (block) => block.type === 'tool_call' && block.toolCall?.id === 'tool-1'
    )
    expect(skillCall?.toolCall?.status).toBe('success')
    expect(toolCall?.toolCall?.status).toBe('success')
    expect(toolCall?.toolCall?.params?.content).toMatch(/^\[redacted/)
    expect(projection.assistantText).toBe('The lesson intro is ready.')
  })
})
