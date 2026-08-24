'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getMothershipAttachmentPreviewUrl } from '@/lib/copilot/chat/attachment-preview'
import type { FilePreviewSession } from '@/lib/copilot/request/session/file-preview-session-contract'
import type { MothershipResource, MothershipResourceType } from '@/lib/copilot/resources/types'
import {
  agentTaskV1Events,
  answerAgentInteraction,
  api,
  subscribeAgentV1Events,
} from '@/lib/lingxi/api'
import type { ChatContext } from '@/lib/lingxi/chat-context'
import type { LingxiTaskTransport } from '@/lib/lingxi/lingxi-task-transport'
import { decodeLingxiV1Event } from '@/lib/lingxi/stream/decode-v1'
import {
  decodeInteractionOptionId,
  emptyV1ThreadModel,
  interactionAnswerLabels,
  type LingxiV1ThreadModel,
  reduceV1Event,
} from '@/lib/lingxi/stream/turn-model'
import {
  type LingxiTurnState,
  reconcileLingxiTurnState,
  reduceLingxiTurnState,
  turnStateFromTask,
} from '@/lib/lingxi/turn-state'
import type { AgentTaskEvent, AgentTaskSnapshot } from '@/lib/lingxi/types'
import type { TypedQuestionAnswer } from '@/app/workspace/[workspaceId]/home/components/message-content/components/question/typed-answers'
import { useMothershipQueueStore } from '@/stores/mothership-queue/store'
import type { QueuedMothershipMessage } from '../chat-queue-types'
import type {
  ChatMessage,
  ChatMessageAttachment,
  FileAttachmentForApi,
  GenericResourceData,
} from '../types'
import type { SendMessageOptions, UseChatOptions, UseChatReturn } from './chat-controller-types'
import {
  mergeAgentTaskEvent,
  RUNTIME_GRAPH_REFRESH_EVENTS,
  reduceV1TurnState,
} from './controllers/event-controller'
import {
  lingxiIdempotencyKey,
  queueHead,
  queueKeyFor,
  queueKeysContaining,
  queueMigration,
} from './controllers/queue-controller'
import { artifactResourceId, artifactResources } from './controllers/resource-controller'
import { createStreamController } from './controllers/stream-controller'
import {
  buildInteractionAnswerCommand,
  executeInteractionAnswerCommand,
  runTaskCommand,
} from './controllers/task-controller'

function userMessage(
  id: string,
  content: string,
  contexts?: ChatContext[],
  fileAttachments?: FileAttachmentForApi[]
): ChatMessage {
  return {
    id,
    role: 'user',
    content,
    contexts: contexts?.map((context) => ({ ...context })),
    attachments: fileAttachments?.map<ChatMessageAttachment>((attachment) => ({
      id: attachment.id,
      filename: attachment.filename,
      media_type: attachment.media_type,
      size: attachment.size,
      previewUrl: getMothershipAttachmentPreviewUrl(attachment),
    })),
  }
}

const EMPTY_LINGXI_QUEUE: QueuedMothershipMessage[] = []

function generateLingxiId(prefix: string): string {
  const uuid = globalThis.crypto?.randomUUID?.()
  return `${prefix}:${uuid ?? `${Date.now()}:${Math.random().toString(36).slice(2, 8)}`}`
}

export function getLingxiGraphUseChatOptions(
  options: Pick<
    UseChatOptions,
    | 'onResourceEvent'
    | 'onStreamEnd'
    | 'initialActiveResourceId'
    | 'activeResourceState'
    | 'onRequestStarted'
  > & { adapter: LingxiTaskTransport }
): UseChatOptions {
  return { ...options }
}

export function useWorkspaceChatController(
  workspaceId: string,
  initialChatId: string | undefined,
  options?: UseChatOptions
): UseChatReturn {
  const router = useRouter()
  const adapter = options?.adapter
  const adapterRef = useRef<LingxiTaskTransport | undefined>(adapter)
  adapterRef.current = adapter
  const onResourceEventRef = useRef(options?.onResourceEvent)
  const onStreamEndRef = useRef(options?.onStreamEnd)
  const onRequestStartedRef = useRef(options?.onRequestStarted)
  onResourceEventRef.current = options?.onResourceEvent
  onStreamEndRef.current = options?.onStreamEnd
  onRequestStartedRef.current = options?.onRequestStarted

  const [resolvedChatId, setResolvedChatId] = useState<string | undefined>(initialChatId)
  const [task, setTask] = useState<AgentTaskSnapshot | null>(null)
  const [workflowState, setWorkflowState] = useState<Record<string, unknown> | null>(null)
  const [events, setEvents] = useState<AgentTaskEvent[]>([])
  const [streamProtocol, setStreamProtocol] = useState<'v1' | 'legacy-v0' | null>(null)
  const [legacyProjection, setLegacyProjection] = useState<{
    blocks: NonNullable<ChatMessage['contentBlocks']>
    assistantText: string
    isTerminal: boolean
  } | null>(null)
  const [v1Model, setV1Model] = useState<LingxiV1ThreadModel | null>(null)
  const [localUsers, setLocalUsers] = useState<ChatMessage[]>([])
  const [isSending, setIsSending] = useState(false)
  const [isReconnecting, setIsReconnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [locallyStopped, setLocallyStopped] = useState(false)
  const [subscriptionEpoch, setSubscriptionEpoch] = useState(0)
  const [turnState, setTurnState] = useState<LingxiTurnState>('idle')
  const [dispatchingHeadId, setDispatchingHeadId] = useState<string | null>(null)
  const [activeResourceIdState, setActiveResourceIdState] = useState<string | null>(
    options?.initialActiveResourceId ?? null
  )
  const internalActiveResourceState = useState<string | null>(
    options?.initialActiveResourceId ?? null
  )
  const [activeResourceId, setActiveResourceId] =
    options?.activeResourceState ?? internalActiveResourceState
  const v1ModelRef = useRef<LingxiV1ThreadModel | null>(null)
  // SSE Last-Event-ID belongs to the durable AgentTaskEvent table.  Never use
  // LingxiV1ThreadModel.lastSeq here: that is the protocol envelope sequence.
  const v1RowSequenceRef = useRef(0)
  const messagesRef = useRef<ChatMessage[]>([])
  const requestIdRef = useRef<string | undefined>(initialChatId)
  const resolvedChatIdRef = useRef<string | undefined>(initialChatId)
  const queueKeyRef = useRef(queueKeyFor(workspaceId, initialChatId))
  const turnStateRef = useRef<LingxiTurnState>('idle')
  const optimisticActiveRef = useRef(false)
  const dispatchingHeadIdRef = useRef<string | null>(null)
  const drainQueueRef = useRef<() => Promise<void>>(async () => {})

  const queueKey = queueKeyFor(workspaceId, resolvedChatId)
  queueKeyRef.current = queueKey
  const messageQueue = useMothershipQueueStore(
    (state) => state.queues[queueKey] ?? EMPTY_LINGXI_QUEUE
  )
  const editingQueuedId = useMothershipQueueStore((state) => state.editing[queueKey] ?? null)
  const enqueueQueuedMessage = useMothershipQueueStore((state) => state.enqueue)
  const replaceQueuedMessage = useMothershipQueueStore((state) => state.replaceAt)
  const removeQueuedMessage = useMothershipQueueStore((state) => state.remove)
  const setQueuedEditing = useMothershipQueueStore((state) => state.setEditing)
  const migrateQueuedMessages = useMothershipQueueStore((state) => state.migrate)

  const applyTurnState = useCallback((next: LingxiTurnState) => {
    const previous = turnStateRef.current
    turnStateRef.current = next
    setTurnState(next)
    if (next === 'awaiting_user' && previous !== 'awaiting_user') {
      queueMicrotask(() => void drainQueueRef.current())
    }
  }, [])

  useEffect(() => {
    resolvedChatIdRef.current = resolvedChatId
  }, [resolvedChatId])

  const effectiveActiveResourceId = options?.activeResourceState
    ? activeResourceId
    : activeResourceIdState
  const setEffectiveActiveResourceId = useCallback(
    (id: string | null) => {
      if (options?.activeResourceState) setActiveResourceId(id)
      else setActiveResourceIdState(id)
    },
    [options?.activeResourceState, setActiveResourceId]
  )

  useEffect(() => {
    setResolvedChatId(initialChatId)
    resolvedChatIdRef.current = initialChatId
    requestIdRef.current = initialChatId
    setTask(null)
    setWorkflowState(null)
    setEvents([])
    setStreamProtocol(null)
    setLegacyProjection(null)
    setV1Model(null)
    v1ModelRef.current = null
    v1RowSequenceRef.current = 0
    setLocalUsers([])
    setError(null)
    setLocallyStopped(false)
    optimisticActiveRef.current = false
    applyTurnState('idle')
    dispatchingHeadIdRef.current = null
    setDispatchingHeadId(null)
  }, [applyTurnState, initialChatId])

  useEffect(() => {
    const currentAdapter = adapterRef.current
    const taskId = resolvedChatIdRef.current
    if (!currentAdapter || !taskId || locallyStopped) {
      return
    }

    let cancelled = false
    let runtimeGraphRefreshTimer: ReturnType<typeof globalThis.setTimeout> | null = null
    let runtimeGraphRefreshInFlight = false
    let stream: ReturnType<typeof createStreamController> | null = null
    let legacyTask: AgentTaskSnapshot | null = null
    let projectLegacy:
      | ((
          task: AgentTaskSnapshot,
          events: AgentTaskEvent[]
        ) => {
          blocks: NonNullable<ChatMessage['contentBlocks']>
          assistantText: string
          isTerminal: boolean
        })
      | null = null
    setIsReconnecting(true)
    setError(null)

    const refreshRuntimeGraph = async () => {
      if (cancelled || runtimeGraphRefreshInFlight) return
      runtimeGraphRefreshInFlight = true
      try {
        const graph = await api.runtimeGraph(taskId)
        if (!cancelled) setWorkflowState(graph.workflowState)
      } catch {
        // The graph endpoint can briefly lag identity persistence; the next
        // lifecycle event/catch-up tick schedules another coalesced refresh.
      } finally {
        runtimeGraphRefreshInFlight = false
      }
    }

    const scheduleRuntimeGraphRefresh = () => {
      if (cancelled || runtimeGraphRefreshTimer !== null) return
      runtimeGraphRefreshTimer = globalThis.setTimeout(() => {
        runtimeGraphRefreshTimer = null
        void refreshRuntimeGraph()
      }, 150)
    }

    const appendEvent = (event: AgentTaskEvent) => {
      if (cancelled) return
      const eventState = reduceLingxiTurnState(turnStateRef.current, event)
      applyTurnState(eventState)
      setEvents((current) => {
        const next = mergeAgentTaskEvent(current, event)
        if (legacyTask && projectLegacy) setLegacyProjection(projectLegacy(legacyTask, next))
        return next
      })
      void api.recordLearningEvent(taskId, event).catch(() => {})
      const eventWorkflowState =
        event.workflowState ?? (event.payload.workflowState as Record<string, unknown> | undefined)
      if (eventWorkflowState) setWorkflowState(eventWorkflowState)
      if (RUNTIME_GRAPH_REFRESH_EVENTS.has(event.kind)) scheduleRuntimeGraphRefresh()
      if (event.kind === 'artifact.ready') {
        const artifact = typeof event.payload.artifact === 'string' ? event.payload.artifact : ''
        if (artifact)
          onResourceEventRef.current?.(artifactResourceId(taskId, artifact), 'artifact.ready')
        void currentAdapter
          .loadTask(taskId)
          .then((refreshed) => {
            if (!cancelled) {
              setTask(refreshed)
              if (!optimisticActiveRef.current) {
                applyTurnState(reconcileLingxiTurnState(refreshed, [event]))
              }
            }
          })
          .catch(() => {})
      }
      if (event.kind === 'delivery.unlocked') {
        const artifact = typeof event.payload.artifact === 'string' ? event.payload.artifact : ''
        if (artifact)
          onResourceEventRef.current?.(artifactResourceId(taskId, artifact), 'delivery.unlocked')
        void currentAdapter
          .loadTask(taskId)
          .then((refreshed) => {
            if (!cancelled) {
              setTask(refreshed)
              if (!optimisticActiveRef.current) {
                applyTurnState(reconcileLingxiTurnState(refreshed, [event]))
              }
            }
          })
          .catch(() => {})
      }
    }

    const applyV1Event = (row: AgentTaskEvent) => {
      if (cancelled) return
      const decoded = decodeLingxiV1Event(row.payload)
      if (!decoded.ok) {
        stream?.stop()
        cancelled = true
        setIsReconnecting(false)
        setError(`V1 protocol error at ${decoded.error.path}: ${decoded.error.message}`)
        return
      }
      const envelope = decoded.event
      if (typeof row.sequence === 'number') {
        v1RowSequenceRef.current = Math.max(v1RowSequenceRef.current, row.sequence)
      }
      // V1 identity is canonical. A malformed row fails this protocol session
      // and is never reinterpreted by the historical heuristic reader.
      applyTurnState(reduceV1TurnState(turnStateRef.current, envelope))
      const model = v1ModelRef.current ?? emptyV1ThreadModel(taskId)
      reduceV1Event(model, envelope)
      v1ModelRef.current = model
      setV1Model({ chatId: model.chatId, turns: model.turns, lastSeq: model.lastSeq })
      if (envelope.type === 'run' || envelope.type === 'span') {
        scheduleRuntimeGraphRefresh()
      }
      if (envelope.type === 'resource') {
        const resource = (envelope.payload as Record<string, unknown>).resource as
          | Record<string, unknown>
          | undefined
        const id = typeof resource?.id === 'string' ? resource.id : ''
        if (id) onResourceEventRef.current?.(id, 'artifact.ready')
      }
    }

    const start = async () => {
      try {
        const loaded = await currentAdapter.loadTask(taskId)
        if (cancelled) return
        setTask(loaded)
        // A send can win the race with the worker's first status update. Keep
        // the optimistic active turn until an event or snapshot catches up.
        if (!optimisticActiveRef.current) applyTurnState(turnStateFromTask(loaded))
        // The server classifies the retained task once. Empty current tasks
        // are V1; only tasks whose durable rows are exclusively pre-V1 enter
        // the explicit historical reader. There is no content-based fallback.
        const protocolHistory = await agentTaskV1Events(taskId)
        if (cancelled) return
        setStreamProtocol(protocolHistory.protocol)
        stream = createStreamController({
          subscribeV0: (from, onEvent, onEnd) =>
            currentAdapter.subscribe(taskId, { from, onEvent, onEnd }),
          subscribeV1: (from, onEvent) => subscribeAgentV1Events(taskId, onEvent, { from }),
          catchUpV1: async (from) => (await agentTaskV1Events(taskId, from)).events,
        })

        if (protocolHistory.protocol === 'v1') {
          const model = emptyV1ThreadModel(taskId)
          for (const row of protocolHistory.events.sort(
            (left, right) => left.sequence - right.sequence
          )) {
            const decoded = decodeLingxiV1Event(row.payload)
            if (!decoded.ok) {
              throw new Error(
                `V1 protocol error at ${decoded.error.path}: ${decoded.error.message}`
              )
            }
            reduceV1Event(model, decoded.event)
          }
          v1RowSequenceRef.current = Math.max(
            0,
            ...protocolHistory.events.map((row) => row.sequence)
          )
          v1ModelRef.current = model
          setV1Model(model)
          setEvents([])
          setLegacyProjection(null)
          stream.startV1(applyV1Event)
        } else {
          const historyEvents = await currentAdapter.loadEvents(taskId)
          if (cancelled) return
          const orderedHistory = historyEvents.sort((left, right) => left.sequence - right.sequence)
          const legacy = await import('@/lib/lingxi/legacy/v0/lingxi-graph-v0')
          legacyTask = loaded
          projectLegacy = legacy.projectLingxiGraphV0History
          legacy.assertV0History(orderedHistory)
          setEvents(orderedHistory)
          setV1Model(null)
          v1ModelRef.current = null
          setLegacyProjection(projectLegacy(loaded, orderedHistory))
          if (!optimisticActiveRef.current) {
            applyTurnState(reconcileLingxiTurnState(loaded, orderedHistory))
          }
          stream.startLegacyV0(orderedHistory.at(-1)?.sequence ?? 0, appendEvent, async () => {
            try {
              const refreshed = await currentAdapter.loadTask(taskId)
              if (!cancelled) {
                legacyTask = refreshed
                setTask(refreshed)
                optimisticActiveRef.current = false
                applyTurnState(turnStateFromTask(refreshed))
                onStreamEndRef.current?.(taskId, messagesRef.current)
                if (turnStateFromTask(refreshed) === 'awaiting_user') {
                  void drainQueueRef.current()
                }
              }
            } finally {
              if (!cancelled) setIsReconnecting(false)
            }
          })
        }
        void api
          .runtimeGraph(taskId)
          .then((graph) => {
            if (!cancelled) setWorkflowState(graph.workflowState)
          })
          .catch(() => {
            if (loaded.latest_execution_id) {
              void api
                .executionSnapshot(loaded.latest_execution_id)
                .then((snapshot) => setWorkflowState(snapshot.workflowState))
                .catch(() => {})
            }
          })
        setLocalUsers((current) =>
          current.length > 0 ? current : [userMessage(`lingxi-user:${loaded.id}`, loaded.prompt)]
        )
        requestIdRef.current = loaded.id
        setIsReconnecting(false)
      } catch (cause) {
        if (cancelled) return
        setIsReconnecting(false)
        setError(cause instanceof Error ? cause.message : String(cause))
      }
    }
    void start()
    return () => {
      cancelled = true
      stream?.stop()
      if (runtimeGraphRefreshTimer !== null) globalThis.clearTimeout(runtimeGraphRefreshTimer)
    }
  }, [applyTurnState, locallyStopped, resolvedChatId, subscriptionEpoch])

  const resources = useMemo(() => artifactResources(task), [task])
  // This is the same state used by the queue dispatcher and composer. The
  // task snapshot alone cannot represent a paused turn while its SSE stays
  // open, and an optimistic active flag alone cannot represent a terminal
  // task after reconnect.
  const assistantStreaming = turnState === 'active' && !locallyStopped
  const messages = useMemo<ChatMessage[]>(() => {
    if (!task) return localUsers.length > 0 ? localUsers : []
    // V1 transcript: every turn independently owns its user text, content
    // blocks, interactions and AgentRuns (issue #18 §18.3).  Local user
    // messages already claimed by a turn's userText are not duplicated.
    if (v1Model && v1Model.turns.length > 0) {
      const claimedTexts = v1Model.turns
        .map((turn) => turn.userText.trim())
        .filter((text) => text.length > 0)
      const unclaimedLocals = localUsers.filter(
        (local) =>
          !claimedTexts.some(
            (text) => text === local.content.trim() || text.startsWith(local.content.trim())
          )
      )
      const lastTurn = v1Model.turns[v1Model.turns.length - 1]
      const turnMessages: ChatMessage[] = []
      for (const turn of v1Model.turns) {
        if (turn.userText.trim()) {
          turnMessages.push(
            userMessage(`lingxi-user:${task.id}:${turn.turnId}`, turn.userText.trim())
          )
        }
        const isLastTurn = turn === lastTurn
        const resolvedCard = turn.interactions.find((item) => item.status === 'resolved')
        turnMessages.push({
          id: `lingxi-assistant:${task.id}:${turn.turnId}`,
          role: 'assistant',
          content: turn.assistantText || (isLastTurn ? '正在连接学习图谱…' : ''),
          contentBlocks: [
            ...turn.blocks,
            ...(locallyStopped && isLastTurn && turn.status === 'active'
              ? [{ type: 'stopped' as const }]
              : []),
          ],
          requestId: task.id,
          ...(resolvedCard ? { questionAnswers: interactionAnswerLabels(resolvedCard) } : {}),
        })
      }
      return [...turnMessages, ...unclaimedLocals]
    }
    // An empty V1 thread is still V1. Never reinterpret it with the historical
    // reader; it simply has not emitted a learner-facing turn yet.
    if (streamProtocol !== 'legacy-v0' || !legacyProjection) {
      return [
        ...(localUsers.length > 0
          ? localUsers
          : [userMessage(`lingxi-user:${task.id}`, task.prompt)]),
        {
          id: `lingxi-assistant:${task.id}`,
          role: 'assistant',
          content: '正在连接学习图谱…',
          contentBlocks: locallyStopped ? [{ type: 'stopped' as const }] : [],
          requestId: task.id,
        },
      ]
    }
    const currentProjection = legacyProjection
    const assistant: ChatMessage = {
      id: `lingxi-assistant:${task.id}`,
      role: 'assistant',
      content: currentProjection.assistantText || 'Connecting to the learning graph…',
      contentBlocks: [
        ...currentProjection.blocks,
        ...(locallyStopped && !currentProjection.isTerminal ? [{ type: 'stopped' as const }] : []),
      ],
      requestId: task.id,
    }
    return [
      ...(localUsers.length > 0
        ? localUsers
        : [userMessage(`lingxi-user:${task.id}`, task.prompt)]),
      assistant,
    ]
  }, [legacyProjection, localUsers, locallyStopped, streamProtocol, task, v1Model])
  messagesRef.current = messages

  const sendDirect = useCallback(
    async (
      message: string,
      fileAttachments?: FileAttachmentForApi[],
      contexts?: ChatContext[],
      userMessageId = generateLingxiId('lingxi-user'),
      explicitIdempotencyKey?: string
    ): Promise<boolean> => {
      const currentAdapter = adapterRef.current
      const content = message.trim()
      if (!currentAdapter || !content) return false

      // A question-card option id carries its typed interaction identity
      // (issue #18 §10.5): answer through the structured API instead of
      // sending a formatted string the backend would have to guess at.
      const existingTaskId = resolvedChatIdRef.current
      const encoded = decodeInteractionOptionId(content)
      if (encoded && existingTaskId) {
        const model = v1ModelRef.current
        let label = content
        for (const turn of model?.turns ?? []) {
          const card = turn.interactions.find(
            (item) => item.interactionId === encoded.interactionId
          )
          const option = card?.questions
            .find((question) => question.id === encoded.questionId)
            ?.options.find((item) => item.id === encoded.optionId)
          if (option) {
            label = option.label
            break
          }
        }
        const previousTurnState = turnStateRef.current
        optimisticActiveRef.current = true
        applyTurnState('active')
        setIsSending(true)
        setError(null)
        setLocalUsers((current) =>
          current.some((candidate) => candidate.id === userMessageId)
            ? current
            : [...current, userMessage(userMessageId, label)]
        )
        try {
          await answerAgentInteraction(
            existingTaskId,
            encoded.interactionId,
            [
              {
                questionId: encoded.questionId,
                selectedOptionIds: [encoded.optionId],
                text: null,
              },
            ],
            explicitIdempotencyKey ?? lingxiIdempotencyKey(userMessageId)
          )
          onRequestStartedRef.current?.({ requestId: existingTaskId, userMessageId })
          return true
        } catch (cause) {
          optimisticActiveRef.current = false
          applyTurnState(previousTurnState)
          setError(cause instanceof Error ? cause.message : String(cause))
          return false
        } finally {
          setIsSending(false)
        }
      }

      const idempotencyKey = explicitIdempotencyKey ?? lingxiIdempotencyKey(userMessageId)
      const previousTurnState = turnStateRef.current
      optimisticActiveRef.current = true
      applyTurnState('active')
      setIsSending(true)
      setError(null)
      setLocallyStopped(false)
      setSubscriptionEpoch((current) => current + 1)
      setLocalUsers((current) =>
        current.some((candidate) => candidate.id === userMessageId)
          ? current
          : [...current, userMessage(userMessageId, content, contexts, fileAttachments)]
      )

      try {
        const result = await runTaskCommand(
          {
            taskId: resolvedChatIdRef.current,
            message: content,
            attachments: fileAttachments,
            contexts,
            idempotencyKey,
          },
          currentAdapter
        )
        if (!result) return false
        const taskId = result.taskId
        if (result.kind === 'created') {
          const migration = queueMigration(workspaceId, taskId)
          migrateQueuedMessages(migration.from, migration.to)
          resolvedChatIdRef.current = taskId
          requestIdRef.current = taskId
          setResolvedChatId(taskId)
          router.replace(`/workspace/${workspaceId}/chat/${taskId}`)
          onRequestStartedRef.current?.({ requestId: taskId, userMessageId })
          onResourceEventRef.current?.(`runtime-graph:${taskId}`)
        } else {
          requestIdRef.current = taskId
          onRequestStartedRef.current?.({ requestId: taskId, userMessageId })
        }
        return true
      } catch (cause) {
        optimisticActiveRef.current = false
        applyTurnState(previousTurnState)
        setError(cause instanceof Error ? cause.message : String(cause))
        return false
      } finally {
        setIsSending(false)
      }
    },
    [applyTurnState, migrateQueuedMessages, router, workspaceId]
  )

  /**
   * Answer the open blocking interaction through the structured API.
   *
   * The question card reports option ids, never a formatted string, so
   * single-select, multi-select and free-text answers all reach the backend as
   * `{interactionId, answers:[{questionId, selectedOptionIds, text}]}`
   * (issue #18 §10.5).  A synchronous `false` means this card is not a typed
   * V1 interaction and the caller may fall back to an ordinary message; a
   * promise means the typed path owns it, and it resolves false when the
   * server rejected the answer so the card can stay answerable.
   *
   * The answer is a continuation of the current turn, not a new user message:
   * the resolved interaction renders as the card's own recap, so no local user
   * bubble is created — one would duplicate the recap live and vanish on
   * refresh (issue #18 §10.6).
   */
  const answerInteraction = useCallback(
    (submitted: TypedQuestionAnswer[]): boolean | Promise<boolean> => {
      const taskId = resolvedChatIdRef.current
      const model = v1ModelRef.current
      if (!taskId || !model) return false
      const answerId = generateLingxiId('lingxi-interaction-answer')
      const command = buildInteractionAnswerCommand({
        taskId,
        model,
        submitted,
        idempotencyKey: lingxiIdempotencyKey(answerId),
      })
      if (!command) return false
      const previousTurnState = turnStateRef.current
      optimisticActiveRef.current = true
      applyTurnState('active')
      setIsSending(true)
      setError(null)

      return (async () => {
        try {
          await executeInteractionAnswerCommand(command, {
            answerInteraction: answerAgentInteraction,
          })
          onRequestStartedRef.current?.({ requestId: taskId, userMessageId: answerId })
          return true
        } catch (cause) {
          // The interaction is still pending server-side; hand the card back
          // its active state so the learner can retry.
          optimisticActiveRef.current = false
          applyTurnState(previousTurnState)
          setError(cause instanceof Error ? cause.message : String(cause))
          return false
        } finally {
          setIsSending(false)
        }
      })()
    },
    [applyTurnState]
  )

  const dispatchQueuedMessage = useCallback(
    async (message: QueuedMothershipMessage): Promise<boolean> => {
      const dispatchKey = queueKeyRef.current
      const liveMessage =
        useMothershipQueueStore
          .getState()
          .queues[dispatchKey]?.find((candidate) => candidate.id === message.id) ?? message
      if (!liveMessage || dispatchingHeadIdRef.current) return false
      dispatchingHeadIdRef.current = liveMessage.id
      setDispatchingHeadId(liveMessage.id)
      try {
        const sent = await sendDirect(
          liveMessage.content,
          liveMessage.fileAttachments,
          liveMessage.contexts,
          liveMessage.id,
          liveMessage.idempotencyKey ?? lingxiIdempotencyKey(liveMessage.id)
        )
        // Remove only after the server accepted the command. If the response
        // is lost after commit, the item stays persisted and the same key is
        // retried, so the backend command ledger makes it exactly-once.
        if (sent) {
          const currentQueues = useMothershipQueueStore.getState().queues
          for (const chatKey of queueKeysContaining(currentQueues, liveMessage.id)) {
            removeQueuedMessage(chatKey, liveMessage.id)
          }
        }
        return sent
      } finally {
        dispatchingHeadIdRef.current = null
        setDispatchingHeadId(null)
      }
    },
    [removeQueuedMessage, sendDirect]
  )

  const drainQueue = useCallback(async () => {
    // A native interrupt is a resumable learner turn. An SSE stream remains
    // open in this state, so queue draining must be triggered by the event or
    // snapshot transition rather than by stream end.
    const dispatchKey = queueKeyRef.current
    const state = useMothershipQueueStore.getState()
    const queue = state.queues[dispatchKey] ?? EMPTY_LINGXI_QUEUE
    const next = queueHead(
      queue,
      state.editing[dispatchKey],
      dispatchingHeadIdRef.current,
      turnStateRef.current
    )
    if (!next) return
    await dispatchQueuedMessage(next)
  }, [dispatchQueuedMessage])
  drainQueueRef.current = drainQueue

  const sendMessage = useCallback(
    async (
      message: string,
      fileAttachments?: FileAttachmentForApi[],
      contexts?: ChatContext[],
      _sendOptions?: SendMessageOptions
    ) => {
      const content = message.trim()
      if (!content && !(fileAttachments && fileAttachments.length > 0)) return

      const dispatchKey = queueKeyRef.current
      const queueState = useMothershipQueueStore.getState()
      const currentEditId = queueState.editing[dispatchKey]
      if (currentEditId) {
        if (dispatchingHeadIdRef.current === currentEditId) return
        replaceQueuedMessage(dispatchKey, currentEditId, {
          content: content || 'Analyze the attached file(s).',
          fileAttachments,
          contexts,
          idempotencyKey: lingxiIdempotencyKey(currentEditId, generateLingxiId('edit')),
        })
        // `replaceAt` deliberately keeps the original index. Editing the
        // head pauses dispatch until submit completes; editing a later entry
        // never jumps it ahead of earlier queued learner messages.
        setQueuedEditing(dispatchKey, null)
        void drainQueueRef.current()
        return
      }

      const queuedId = generateLingxiId('lingxi-queued')
      const queued: QueuedMothershipMessage = {
        id: queuedId,
        content: content || 'Analyze the attached file(s).',
        fileAttachments,
        contexts,
        idempotencyKey: lingxiIdempotencyKey(queuedId),
      }
      const queue = queueState.queues[dispatchKey] ?? EMPTY_LINGXI_QUEUE
      if (turnStateRef.current === 'active' || queue.length > 0 || dispatchingHeadIdRef.current) {
        enqueueQueuedMessage(dispatchKey, queued)
        return
      }

      // Persist even the first idle send until the POST is accepted. This is
      // the same response-loss boundary as a queued interjection and leaves a
      // stable idempotency key available after a remount.
      enqueueQueuedMessage(dispatchKey, queued)
      void drainQueueRef.current()
    },
    [enqueueQueuedMessage, replaceQueuedMessage, setQueuedEditing]
  )

  const stopGeneration = useCallback(async () => {
    setLocallyStopped(true)
    optimisticActiveRef.current = false
    applyTurnState('terminal')
    const taskId = resolvedChatIdRef.current
    const currentAdapter = adapterRef.current
    if (!taskId || !currentAdapter) return
    try {
      await currentAdapter.cancelTask(taskId)
      const refreshed = await currentAdapter.loadTask(taskId)
      setTask(refreshed)
      applyTurnState(turnStateFromTask(refreshed))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [applyTurnState])

  const addResource = useCallback((_resource: MothershipResource) => true, [])
  const removeResource = useCallback(
    (_type: MothershipResourceType, resourceId: string) => {
      if (effectiveActiveResourceId === resourceId) setEffectiveActiveResourceId(null)
    },
    [effectiveActiveResourceId, setEffectiveActiveResourceId]
  )
  const reorderResources = useCallback((_next: MothershipResource[]) => {}, [])
  const removeFromQueue = useCallback(
    (id: string) => {
      const dispatchKey = queueKeyRef.current
      removeQueuedMessage(dispatchKey, id)
      if (useMothershipQueueStore.getState().editing[dispatchKey] === id) {
        setQueuedEditing(dispatchKey, null)
      }
    },
    [removeQueuedMessage, setQueuedEditing]
  )

  const sendNow = useCallback(
    async (id: string) => {
      const dispatchKey = queueKeyRef.current
      const message = useMothershipQueueStore
        .getState()
        .queues[dispatchKey]?.find((candidate) => candidate.id === id)
      // Send now is an interjection/resume command. It must never cancel the
      // durable task: cancellation is reserved for the explicit Stop action.
      if (!message || dispatchingHeadIdRef.current) return
      await dispatchQueuedMessage(message)
    },
    [dispatchQueuedMessage]
  )

  const editQueuedMessage = useCallback(
    (id: string): QueuedMothershipMessage | undefined => {
      if (dispatchingHeadIdRef.current === id) return undefined
      const dispatchKey = queueKeyRef.current
      const message = useMothershipQueueStore
        .getState()
        .queues[dispatchKey]?.find((candidate) => candidate.id === id)
      if (!message) return undefined
      setQueuedEditing(dispatchKey, id)
      return message
    },
    [setQueuedEditing]
  )

  const cancelQueueEdit = useCallback(() => {
    setQueuedEditing(queueKeyRef.current, null)
  }, [setQueuedEditing])

  return {
    messages,
    isSending: isSending || assistantStreaming,
    isReconnecting,
    error,
    resolvedChatId,
    desktopScopeId: `lingxi:${resolvedChatId ?? 'pending'}`,
    sendMessage,
    answerInteraction,
    stopGeneration,
    resources,
    activeResourceId: effectiveActiveResourceId,
    setActiveResourceId: setEffectiveActiveResourceId,
    addResource,
    removeResource,
    reorderResources,
    messageQueue,
    removeFromQueue,
    sendNow,
    editQueuedMessage,
    cancelQueueEdit,
    editingQueuedId,
    dispatchingHeadId,
    previewSession: null as FilePreviewSession | null,
    genericResourceData: null as GenericResourceData | null,
    lingxiRuntime: { task, events, workflowState, turnState, v1Model },
    getCurrentRequestId: () => requestIdRef.current,
  }
}
