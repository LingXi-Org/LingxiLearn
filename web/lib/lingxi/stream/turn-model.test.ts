/**
 * V1 turn-model tests: envelopes → per-turn transcript (issue #18 §18.3/§14.5).
 */

import { describe, expect, it } from 'vitest'

import type { LingxiMothershipEventV1 } from '@/lib/lingxi/generated/mothership-stream-v1'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { decodeLingxiMothershipEvent } from '@/lib/lingxi/generated/mothership-stream-v1'
import { collectTypedAnswers } from '@/app/workspace/[workspaceId]/home/components/message-content/components/question/typed-answers'
import {
  buildInteractionAnswerRequest,
  buildV1ThreadModel,
  decodeInteractionOptionId,
  encodeInteractionOptionId,
  interactionAnswerLabels,
  pendingInteraction,
  visibleAgentRunIds,
} from '@/lib/lingxi/stream/turn-model'

function envelope(
  seq: number,
  type: string,
  payload: Record<string, unknown>,
  extra: Partial<LingxiMothershipEventV1> = {}
): LingxiMothershipEventV1 {
  return {
    v: 1,
    seq,
    ts: `2026-01-01T00:00:${String(seq).padStart(2, '0')}Z`,
    type: type as LingxiMothershipEventV1['type'],
    stream: { chatId: 't1', turnId: 'turn_1', executionId: 'exec_1', streamId: '' },
    scope: { agentRunId: '', parentAgentRunId: '', skillRunId: '' },
    trace: { requestId: 'exec_1', runId: 'exec_1' },
    payload: payload as LingxiMothershipEventV1['payload'],
    ...extra,
  }
}

describe('turn model reduction', () => {
  it('builds one turn per turn.started with the user text', () => {
    const model = buildV1ThreadModel('t1', [
      envelope(1, 'turn', { turnId: 'turn_1', turnIndex: 0, status: 'started', userText: '什么是量子叠加？' }),
      envelope(2, 'turn', { turnId: 'turn_1', turnIndex: 0, status: 'delivered' }),
      envelope(3, 'turn', { turnId: 'turn_2', turnIndex: 1, status: 'started', userText: '那测量之后呢？' }),
    ])
    expect(model.turns.map((turn) => turn.turnId)).toEqual(['turn_1', 'turn_2'])
    expect(model.turns[0].userText).toBe('什么是量子叠加？')
    expect(model.turns[0].status).toBe('delivered')
    expect(model.turns[1].status).toBe('active')
  })

  it('maps spans to agent-group blocks with stable identity', () => {
    const model = buildV1ThreadModel('t1', [
      envelope(1, 'span', {
        kind: 'agent',
        event: 'start',
        agentRunId: 'ar_1',
        providerId: 'answer_user',
        displayName: '知识点答疑',
        executionKind: 'model',
        capability: 'dialog.answer',
        presentationRole: 'primary',
      }),
      envelope(2, 'text', { channel: 'narration', text: '正在检索你提供的资料…' }, {
        scope: { agentRunId: 'ar_1', parentAgentRunId: '', skillRunId: '' },
      }),
      envelope(3, 'span', { kind: 'agent', event: 'end', agentRunId: 'ar_1', status: 'completed' }),
    ])
    const turn = model.turns[0]
    expect(turn.blocks[0]).toMatchObject({ type: 'subagent', subagent: '知识点答疑', spanId: 'ar_1' })
    expect(turn.blocks[1]).toMatchObject({
      type: 'subagent_text',
      content: '正在检索你提供的资料…',
      spanId: 'ar_1',
    })
    expect(turn.blocks[2]).toMatchObject({ type: 'subagent_end', spanId: 'ar_1' })
    expect(turn.agentRuns[0]).toMatchObject({ agentRunId: 'ar_1', status: 'completed' })
    expect(visibleAgentRunIds(model)).toEqual(new Set(['ar_1']))
  })

  it('assembles assistant text from deltas and closes with a full text event', () => {
    const model = buildV1ThreadModel('t1', [
      envelope(1, 'text', { channel: 'assistant', delta: '量子叠加', streamId: 's1' }),
      envelope(2, 'text', { channel: 'assistant', delta: '是指…' , streamId: 's1' }),
      envelope(3, 'text', { channel: 'assistant', text: '量子叠加是指一个系统可同时处于多个状态。', streamId: 's1' }),
    ])
    expect(model.turns[0].assistantText).toBe('量子叠加是指一个系统可同时处于多个状态。')
  })

  it('upserts tool calls by id and maps statuses', () => {
    const model = buildV1ThreadModel('t1', [
      envelope(1, 'tool', {
        toolCallId: 'sr_1',
        toolKind: 'skill',
        toolName: 'lingxi.skill',
        displayTitle: '自适应教学',
        status: 'executing',
        safeParams: { skillId: 'adaptive-pedagogy' },
      }),
      envelope(2, 'tool', {
        toolCallId: 'sr_1',
        toolKind: 'skill',
        toolName: 'lingxi.skill',
        status: 'success',
        safeResult: { ok: true },
      }),
    ])
    const blocks = model.turns[0].blocks
    expect(blocks).toHaveLength(1)
    expect(blocks[0].toolCall).toMatchObject({ id: 'sr_1', status: 'success' })
    expect(blocks[0].toolCall?.result?.success).toBe(true)
  })

  it('renders a blocking interaction as a question tag and recap answers', () => {
    const interactionId = 'it_1'
    const model = buildV1ThreadModel('t1', [
      envelope(1, 'interaction', {
        interactionId,
        purpose: 'clarification',
        presentation: 'question',
        blocking: true,
        prompt: '你想先学哪个方向？',
        questions: [
          {
            id: 'q1',
            type: 'single_select',
            prompt: '学习目标偏向？',
            options: [
              { id: 'o1', label: '概念理解' },
              { id: 'o2', label: '解题训练' },
            ],
            allowFreeText: false,
          },
        ],
        reasonCode: 'goal_ambiguous',
      }),
    ])
    const turn = model.turns[0]
    expect(turn.status).toBe('awaiting_user')
    expect(turn.assistantText).toContain('<question>')
    expect(turn.assistantText).toContain(encodeInteractionOptionId(interactionId, 'q1', 'o1'))

    const resolved = buildV1ThreadModel('t1', [
      ...model.turns.length ? [] : [],
      envelope(1, 'interaction', {
        interactionId,
        blocking: true,
        prompt: '你想先学哪个方向？',
        questions: [
          {
            id: 'q1',
            type: 'single_select',
            prompt: '学习目标偏向？',
            options: [
              { id: 'o1', label: '概念理解' },
              { id: 'o2', label: '解题训练' },
            ],
            allowFreeText: false,
          },
        ],
      }),
      envelope(2, 'interaction', {
        interactionId,
        answers: [{ questionId: 'q1', selectedOptionIds: ['o2'], text: null }],
      }),
    ])
    const card = resolved.turns[0].interactions[0]
    expect(card.status).toBe('resolved')
    expect(interactionAnswerLabels(card)).toEqual(['解题训练'])
  })

  it('round-trips encoded interaction option ids', () => {
    const encoded = encodeInteractionOptionId('it_ab', 'q1', 'o2')
    expect(decodeInteractionOptionId(encoded)).toEqual({
      interactionId: 'it_ab',
      questionId: 'q1',
      optionId: 'o2',
    })
    expect(decodeInteractionOptionId('o1')).toBeNull()
    expect(decodeInteractionOptionId('it_ab|q1')).toBeNull()
    expect(decodeInteractionOptionId('file_x|q1|o1')).toBeNull()
  })

  it('exposes resources and embeds real workspace-file references', () => {
    const model = buildV1ThreadModel('t1', [
      envelope(1, 'resource', {
        resource: {
          id: 'file_abc',
          type: 'file',
          title: '交互式可视化',
          path: '学习产物/t/visual-explainer.html',
          artifactKind: 'visual',
          sourceAgentRunId: 'ar_2',
        },
        removed: false,
      }),
      envelope(2, 'resource', {
        resource: { id: 'artifact:t1:visual', type: 'file', title: 'visual', artifactKind: 'visual' },
        removed: false,
      }),
    ])
    const turn = model.turns[0]
    expect(turn.resources).toHaveLength(2)
    expect(turn.assistantText).toContain('<workspace_resource type="file" id="file_abc"')
    expect(turn.assistantText).not.toContain('artifact:t1:visual')
  })
})

describe('left/right identity parity (issue #18 §14.5)', () => {
  it('chat-visible agent runs equal runtime-graph node ids for the same facts', () => {
    // The same execution facts drive both projections: the chat turn model
    // here, and the backend execution graph (server/tests parity fixtures).
    const envelopes = [
      envelope(1, 'span', { kind: 'agent', event: 'start', agentRunId: 'ar_a', displayName: 'A' }),
      envelope(2, 'span', { kind: 'agent', event: 'start', agentRunId: 'ar_b', displayName: 'B' }),
      envelope(3, 'span', { kind: 'agent', event: 'end', agentRunId: 'ar_a', status: 'completed' }),
      envelope(4, 'span', { kind: 'agent', event: 'end', agentRunId: 'ar_b', status: 'completed' }),
    ]
    const model = buildV1ThreadModel('t1', envelopes)
    const graphNodeIds = new Set(['ar_a', 'ar_b'])
    expect(visibleAgentRunIds(model)).toEqual(graphNodeIds)
  })
})

describe('typed interaction answers', () => {
  const QUESTION_ENVELOPES = [
    envelope(1, 'turn', { turnId: 'turn_1', turnIndex: 0, status: 'started', userText: '帮我准备量子力学' }),
    envelope(2, 'interaction', {
      interactionId: 'it_1',
      purpose: 'clarification',
      presentation: 'question',
      blocking: true,
      prompt: '你想先学哪个方向？',
      reasonCode: 'goal_ambiguous',
      questions: [
        {
          id: 'q1',
          type: 'single_select',
          prompt: '学习目标偏向？',
          options: [
            { id: 'o1', label: '概念理解' },
            { id: 'o2', label: '解题训练' },
          ],
          allowFreeText: true,
        },
        {
          id: 'q2',
          type: 'multi_select',
          prompt: '想覆盖哪些主题？',
          options: [
            { id: 'a', label: '叠加' },
            { id: 'b', label: '纠缠' },
          ],
          allowFreeText: true,
        },
      ],
    }),
  ]

  /** The card the learner sees, as SpecialTags renders it from the turn. */
  const CARD_QUESTIONS = [
    {
      type: 'single_select' as const,
      prompt: '学习目标偏向？',
      options: [
        { id: encodeInteractionOptionId('it_1', 'q1', 'o1'), label: '概念理解' },
        { id: encodeInteractionOptionId('it_1', 'q1', 'o2'), label: '解题训练' },
      ],
    },
    {
      type: 'multi_select' as const,
      prompt: '想覆盖哪些主题？',
      options: [
        { id: encodeInteractionOptionId('it_1', 'q2', 'a'), label: '叠加' },
        { id: encodeInteractionOptionId('it_1', 'q2', 'b'), label: '纠缠' },
      ],
    },
  ]

  it('finds the open blocking interaction', () => {
    const model = buildV1ThreadModel('t1', QUESTION_ENVELOPES)
    expect(pendingInteraction(model)?.interactionId).toBe('it_1')
    expect(model.turns[0].status).toBe('awaiting_user')
  })

  it('submits single-select and multi-select answers as real option ids', () => {
    const model = buildV1ThreadModel('t1', QUESTION_ENVELOPES)
    // What the card reports after clicking 解题训练, then 叠加 + 纠缠.
    const submitted = collectTypedAnswers(
      CARD_QUESTIONS,
      [
        [encodeInteractionOptionId('it_1', 'q1', 'o2')],
        [
          encodeInteractionOptionId('it_1', 'q2', 'b'),
          encodeInteractionOptionId('it_1', 'q2', 'a'),
        ],
      ],
      ['', '']
    )
    const request = buildInteractionAnswerRequest(model, submitted)
    expect(request).toEqual({
      interactionId: 'it_1',
      answers: [
        { questionId: 'q1', selectedOptionIds: ['o2'], text: null },
        // Option order, not click order.
        { questionId: 'q2', selectedOptionIds: ['a', 'b'], text: null },
      ],
      labels: ['解题训练', '叠加', '纠缠'],
    })
  })

  it('submits free text with no selected option', () => {
    const model = buildV1ThreadModel('t1', QUESTION_ENVELOPES)
    const submitted = collectTypedAnswers(CARD_QUESTIONS, [[], []], ['先讲讲背景', ''])
    expect(buildInteractionAnswerRequest(model, submitted)).toEqual({
      interactionId: 'it_1',
      answers: [{ questionId: 'q1', selectedOptionIds: [], text: '先讲讲背景' }],
      labels: ['先讲讲背景'],
    })
  })

  it('returns null when no typed interaction is open, so the caller sends a message', () => {
    const answered = buildV1ThreadModel('t1', [
      ...QUESTION_ENVELOPES,
      envelope(3, 'interaction', {
        interactionId: 'it_1',
        answers: [{ questionId: 'q1', selectedOptionIds: ['o2'] }],
      }),
    ])
    const submitted = collectTypedAnswers(CARD_QUESTIONS, [[], []], ['随便聊聊', ''])
    expect(buildInteractionAnswerRequest(answered, submitted)).toBeNull()
    expect(buildInteractionAnswerRequest(buildV1ThreadModel('t1', []), submitted)).toBeNull()
  })

  it('ignores an empty submission', () => {
    const model = buildV1ThreadModel('t1', QUESTION_ENVELOPES)
    expect(buildInteractionAnswerRequest(model, [])).toBeNull()
    expect(
      buildInteractionAnswerRequest(model, collectTypedAnswers(CARD_QUESTIONS, [[], []], ['', '']))
    ).toBeNull()
  })
})

describe('primary vs supporting transcript routing', () => {
  it('renders only the primary agent in the turn body, supporting inside its span', () => {
    const fixturePath = path.resolve(
      __dirname,
      '..',
      '..',
      '..',
      '..',
      'contracts',
      'fixtures',
      'mothership-stream-v1',
      'primary-and-supporting.json'
    )
    const raw = JSON.parse(readFileSync(fixturePath, 'utf-8')) as unknown[]
    const events = raw.map((item) => decodeLingxiMothershipEvent(item)!)
    const model = buildV1ThreadModel('task_fixture', events)

    expect(model.turns).toHaveLength(1)
    const turn = model.turns[0]
    expect(turn.assistantText).toContain('叠加态是指一个量子系统')
    // The supporting agent's own words belong to its AgentGroup, not the
    // top-level ChatContent (issue #18 §6.2).
    expect(turn.assistantText).not.toContain('可视化已生成')

    const narrationBlocks = turn.blocks.filter((block) => block.type === 'subagent_text')
    expect(narrationBlocks.map((block) => block.spanId)).toEqual(['ar_visual', 'ar_visual'])
    expect(narrationBlocks.map((block) => block.content)).toEqual([
      '正在生成交互式可视化…',
      '可视化已生成，稍后在右侧查看。',
    ])

    expect([...visibleAgentRunIds(model)]).toEqual(['ar_answer', 'ar_visual'])
    expect(turn.resources.map((resource) => resource.id)).toEqual(['file_fixture_visual'])
    expect(turn.status).toBe('delivered')
  })
})
