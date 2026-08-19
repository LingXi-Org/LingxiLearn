import { describe, expect, it, vi } from 'vitest'
import { emptyV1ThreadModel } from '@/lib/lingxi/stream/turn-model'
import type { LingxiV1ThreadModel } from '@/lib/lingxi/stream/turn-model'
import {
  buildInteractionAnswerCommand,
  buildTaskCommand,
  createTaskController,
  executeInteractionAnswerCommand,
  executeTaskCommand,
  runInteractionAnswer,
  runTaskCommand,
  type InteractionAnswerCommand,
  type TaskCommand,
} from './task-controller'

function pendingModel(): LingxiV1ThreadModel {
  const model = emptyV1ThreadModel('task-1')
  model.turns = [
    {
      turnId: 'turn-1',
      turnIndex: 0,
      status: 'awaiting_user',
      userText: '选择一个主题',
      assistantText: '',
      streamText: {},
      blocks: [],
      interactions: [
        {
          interactionId: 'it_1',
          blocking: true,
          prompt: '选择一个主题',
          questions: [
            {
              id: 'question-1',
              type: 'single_select',
              prompt: '主题',
              options: [
                { id: 'option-a', label: '数学' },
                { id: 'option-b', label: '物理' },
              ],
              allowFreeText: false,
            },
          ],
          status: 'pending',
          answers: [],
        },
      ],
      resources: [],
      agentRuns: [],
      executionIds: [],
    },
  ]
  return model
}

const commonInput = {
  message: '  Explain this file  ',
  attachments: [
    {
      id: 'attachment-1',
      key: 'file-key',
      filename: 'notes.md',
      media_type: 'text/markdown',
      size: 12,
    },
    {
      id: 'attachment-without-key',
      key: '',
      filename: 'ignored.txt',
      media_type: 'text/plain',
      size: 4,
    },
  ],
  contexts: [
    { kind: 'file' as const, fileId: 'file-1', label: 'Notes' },
    { kind: 'skill' as const, skillId: 'skill-1', label: 'Tutor' },
  ],
  idempotencyKey: 'message-key-1',
}

describe('task command decision', () => {
  it('builds a create command when the thread has no task id', () => {
    const command = buildTaskCommand({ ...commonInput, taskId: undefined })

    expect(command).toEqual({
      kind: 'create',
      prompt: 'Explain this file\n\n[Context]\n- Notes\n- Tutor',
      attachments: [
        {
          key: 'file-key',
          filename: 'notes.md',
          media_type: 'text/markdown',
          size: 12,
        },
      ],
      options: {
        resourceRefs: [{ type: 'file', id: 'file-1', label: 'Notes' }],
        skillIds: ['skill-1'],
        idempotencyKey: 'message-key-1',
      },
    })
  })

  it('builds a send command for an existing task and trims its identity', () => {
    const command = buildTaskCommand({ ...commonInput, taskId: '  task-1  ' })

    expect(command?.kind).toBe('send')
    expect(command).toMatchObject({
      taskId: 'task-1',
      message: 'Explain this file\n\n[Context]\n- Notes\n- Tutor',
      options: { idempotencyKey: 'message-key-1' },
    })
  })

  it('returns a no-op for blank messages', () => {
    expect(buildTaskCommand({ ...commonInput, message: ' \n\t' })).toBeNull()
  })
})

describe('task command execution', () => {
  it('executes create through the injected transport', async () => {
    const command = buildTaskCommand({ ...commonInput, taskId: null }) as TaskCommand
    const createTask = vi.fn(async () => ({ id: 'created-task', status: 'queued' }))
    const sendMessage = vi.fn()

    await expect(executeTaskCommand(command, { createTask, sendMessage })).resolves.toEqual({
      kind: 'created',
      taskId: 'created-task',
      status: 'queued',
    })
    expect(createTask).toHaveBeenCalledWith(
      'Explain this file\n\n[Context]\n- Notes\n- Tutor',
      [
        {
          key: 'file-key',
          filename: 'notes.md',
          media_type: 'text/markdown',
          size: 12,
        },
      ],
      expect.objectContaining({ idempotencyKey: 'message-key-1' })
    )
    expect(sendMessage).not.toHaveBeenCalled()
  })

  it('executes send through the injected transport and preserves the task id', async () => {
    const command = buildTaskCommand({ ...commonInput, taskId: 'task-1' }) as TaskCommand
    const createTask = vi.fn()
    const sendMessage = vi.fn(async () => ({ status: 'accepted' }))

    await expect(executeTaskCommand(command, { createTask, sendMessage })).resolves.toEqual({
      kind: 'sent',
      taskId: 'task-1',
      status: 'accepted',
    })
    expect(sendMessage).toHaveBeenCalledWith(
      'task-1',
      'Explain this file\n\n[Context]\n- Notes\n- Tutor',
      expect.any(Array),
      expect.objectContaining({ idempotencyKey: 'message-key-1' })
    )
    expect(createTask).not.toHaveBeenCalled()
  })

  it('does not call transport for a blank message', async () => {
    const createTask = vi.fn()
    const sendMessage = vi.fn()
    await expect(
      runTaskCommand({ ...commonInput, message: '' }, { createTask, sendMessage })
    ).resolves.toBeNull()
    expect(createTask).not.toHaveBeenCalled()
    expect(sendMessage).not.toHaveBeenCalled()
  })
})

describe('typed interaction answer decision and execution', () => {
  it('builds a structured answer from the pending card and keeps option identity', () => {
    const command = buildInteractionAnswerCommand({
      taskId: '  task-1 ',
      model: pendingModel(),
      submitted: [
        {
          questionIndex: 0,
          selectedOptionIds: ['it_1|question-1|option-b'],
          text: '',
        },
      ],
      idempotencyKey: 'answer-key-1',
    })

    expect(command).toEqual({
      taskId: 'task-1',
      interactionId: 'it_1',
      answers: [
        { questionId: 'question-1', selectedOptionIds: ['option-b'], text: null },
      ],
      labels: ['物理'],
      idempotencyKey: 'answer-key-1',
    })
  })

  it('returns null when the typed path does not own the submission', () => {
    const submitted = [
      { questionIndex: 0, selectedOptionIds: [], text: 'answer' },
    ]
    expect(
      buildInteractionAnswerCommand({
        taskId: undefined,
        model: pendingModel(),
        submitted,
        idempotencyKey: 'answer-key-1',
      })
    ).toBeNull()
    expect(
      buildInteractionAnswerCommand({
        taskId: 'task-1',
        model: emptyV1ThreadModel('task-1'),
        submitted,
        idempotencyKey: 'answer-key-1',
      })
    ).toBeNull()
  })

  it('executes the structured answer through an injected transport', async () => {
    const command = buildInteractionAnswerCommand({
      taskId: 'task-1',
      model: pendingModel(),
      submitted: [{ questionIndex: 0, selectedOptionIds: [], text: '  free text  ' }],
      idempotencyKey: 'answer-key-2',
    }) as InteractionAnswerCommand
    const answerInteraction = vi.fn(async () => ({
      status: 'accepted',
      interactionId: 'it_1',
    }))

    await expect(
      executeInteractionAnswerCommand(command, { answerInteraction })
    ).resolves.toEqual({ status: 'accepted', interactionId: 'it_1' })
    expect(answerInteraction).toHaveBeenCalledWith(
      'task-1',
      'it_1',
      [{ questionId: 'question-1', selectedOptionIds: [], text: 'free text' }],
      'answer-key-2'
    )
  })

  it('run facade returns null without invoking answer transport on fallback', async () => {
    const answerInteraction = vi.fn()
    await expect(
      runInteractionAnswer(
        {
          taskId: 'task-1',
          model: pendingModel(),
          submitted: [{ questionIndex: 0, selectedOptionIds: [], text: '' }],
          idempotencyKey: 'answer-key-3',
        },
        { answerInteraction }
      )
    ).resolves.toBeNull()
    expect(answerInteraction).not.toHaveBeenCalled()
  })
})

describe('task controller facade', () => {
  it('binds both transports without adding mutable controller state', async () => {
    const createTask = vi.fn(async () => ({ id: 'task-2', status: 'queued' }))
    const sendMessage = vi.fn(async () => ({ status: 'accepted' }))
    const answerInteraction = vi.fn(async () => ({
      status: 'accepted',
      interactionId: 'it_1',
    }))
    const controller = createTaskController({
      task: { createTask, sendMessage },
      interaction: { answerInteraction },
    })

    await expect(controller.runTaskCommand({ ...commonInput })).resolves.toMatchObject({
      kind: 'created',
      taskId: 'task-2',
    })
    await expect(
      controller.runInteractionAnswer({
        taskId: 'task-1',
        model: pendingModel(),
        submitted: [{ questionIndex: 0, selectedOptionIds: [], text: 'hello' }],
        idempotencyKey: 'answer-key-4',
      })
    ).resolves.toEqual({ status: 'accepted', interactionId: 'it_1' })
  })
})
