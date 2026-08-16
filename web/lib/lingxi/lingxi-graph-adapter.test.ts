import { describe, expect, it } from 'vitest'
import { projectLingxiGraphEvents } from './lingxi-graph-adapter'
import type { AgentTaskEvent, AgentTaskSnapshot } from './types'

const task: AgentTaskSnapshot = {
  id: 'task-1',
  status: 'completed',
  prompt: 'Explain packet retransmission',
  intent: { topic: 'packet retransmission' },
  agents: {
    intent: { status: 'completed' },
    lecture_hook: { status: 'completed' },
    interactive_lecture_deck: { status: 'pending' },
    quiz_generator: { status: 'pending' },
    interactive_visual_explainer: { status: 'pending' },
  },
  artifacts: {
    lesson_intro: { available: true, url: '/api/artifacts/intro' },
    lecture_deck: { available: false, url: '' },
    quiz: { available: false, data: null },
    visual: { available: false, url: '' },
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

describe('LingxiGraph chat adapter', () => {
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

  it('keeps native approval and safe runtime narration visible', () => {
    const projection = projectLingxiGraphEvents(task, [
      {
        ...event(1, 'agent.started', 'lesson_intro', { skill: 'lesson-intro' }),
        span_id: 'lesson-span-1',
      },
      {
        ...event(2, 'agent.status', 'lesson_intro', { text: '正在整理课程引入。' }),
        span_id: 'lesson-span-1',
      },
      {
        ...event(3, 'schedule.proposed', 'coordinator', {
          proposalId: 'proposal-1',
          toolCallId: 'proposal-1',
          toolName: 'schedule.propose',
          cron: '0 9 * * 1',
          timezone: 'Asia/Shanghai',
        }),
      },
      {
        ...event(4, 'interrupt.raised', 'coordinator', {
          id: 'interrupt-1',
          toolName: 'await_user',
          prompt: '请确认是否继续。',
        }),
      },
    ])

    const statusBlock = projection.blocks.find(
      (block) => block.type === 'subagent_text' && block.content === '正在整理课程引入。'
    )
    const scheduleBlock = projection.blocks.find(
      (block) => block.toolCall?.id === 'proposal-1'
    )
    const interruptBlock = projection.blocks.find(
      (block) => block.toolCall?.id === 'interrupt-1'
    )

    expect(statusBlock?.spanId).toBe('lesson-span-1')
    expect(scheduleBlock?.toolCall?.status).toBe('awaiting_approval')
    expect(scheduleBlock?.toolCall?.params?.cron).toBe('0 9 * * 1')
    expect(interruptBlock?.toolCall?.status).toBe('interrupted')
    expect(interruptBlock?.toolCall?.userPrompt).toBe('请确认是否继续。')
  })

  it('projects only explicit answer output into the learner transcript', () => {
    const projection = projectLingxiGraphEvents(task, [
      event(1, 'agent.output', 'answer_user', {
        message: '这是面向学习者的答疑结果。',
      }),
      event(2, 'agent.output', 'prerequisite_analyzer', {
        message: '内部依赖分析，不应显示。',
      }),
    ])

    expect(projection.assistantText).toBe('这是面向学习者的答疑结果。')
    expect(projection.blocks.some((block) => block.content?.includes('内部依赖分析'))).toBe(
      false
    )
  })
})
