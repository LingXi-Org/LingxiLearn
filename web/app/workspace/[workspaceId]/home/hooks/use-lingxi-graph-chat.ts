'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getMothershipAttachmentPreviewUrl } from '@/lib/copilot/chat/attachment-preview'
import type { FilePreviewSession } from '@/lib/copilot/request/session/file-preview-session-contract'
import type { MothershipResource, MothershipResourceType } from '@/lib/copilot/resources/types'
import { api, type LingxiAttachmentRef } from '@/lib/lingxi/api'
import {
  type LingxiGraphChatAdapter,
  projectLingxiGraphEvents,
} from '@/lib/lingxi/lingxi-graph-adapter'
import {
  type LingxiTurnState,
  reconcileLingxiTurnState,
  reduceLingxiTurnState,
  turnStateFromTask,
} from '@/lib/lingxi/turn-state'
import type { AgentTaskEvent, AgentTaskSnapshot } from '@/lib/lingxi/types'
import { useMothershipQueueStore } from '@/stores/mothership-queue/store'
import type { QueuedMothershipMessage } from '@/stores/mothership-queue/types'
import type { ChatContext } from '@/stores/panel'
import type {
  ChatMessage,
  ChatMessageAttachment,
  FileAttachmentForApi,
  GenericResourceData,
} from '../types'
import type { SendMessageOptions, UseChatOptions, UseChatReturn } from './use-chat'

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

function contextSuffix(contexts?: ChatContext[]): string {
  const entries = (contexts ?? [])
    .map((context) => {
      const label = context.label.trim()
      const selectionText =
        'text' in context && typeof context.text === 'string' ? context.text.trim() : ''
      return selectionText ? `${label}:\n${selectionText}` : label
    })
    .filter(Boolean)
  return entries.length > 0
    ? `\n\n[Context]\n${entries.map((entry) => `- ${entry}`).join('\n')}`
    : ''
}

function requestMessage(content: string, contexts?: ChatContext[]): string {
  const normalized = content.trim()
  const maxLength = 4000
  if (normalized.length >= maxLength) return normalized.slice(0, maxLength)
  return `${normalized}${contextSuffix(contexts).slice(0, maxLength - normalized.length)}`
}

function attachmentRefs(attachments?: FileAttachmentForApi[]): LingxiAttachmentRef[] {
  return (attachments ?? [])
    .filter((attachment) => Boolean(attachment.key && attachment.filename))
    .map((attachment) => ({
      key: attachment.key,
      ...(attachment.path ? { path: attachment.path } : {}),
      filename: attachment.filename,
      media_type: attachment.media_type,
      size: attachment.size,
    }))
}

function normalizeArtifactKind(artifact: string): string {
  if (artifact === 'lesson_intro') return 'lesson-intro'
  if (artifact === 'lecture_deck') return 'lecture-deck'
  return artifact
}

function artifactResourceId(taskId: string, artifact: string): string {
  return `lingxi-artifact:${taskId}:${normalizeArtifactKind(artifact)}`
}

/**
 * Translate shared chat chips into the small, learner-scoped reference contract
 * understood by the LingxiGraph API. Unsupported legacy editor chips are
 * intentionally ignored; this surface never sends an editable workflow
 * reference to the learning graph.
 */
function contextOptions(contexts?: ChatContext[]) {
  const resourceRefs: Array<Record<string, unknown>> = []
  const skillIds: string[] = []
  for (const context of contexts ?? []) {
    switch (context.kind) {
      case 'file':
        resourceRefs.push({ type: 'file', id: context.fileId, label: context.label })
        break
      case 'file_selection':
        resourceRefs.push({
          type: 'file',
          id: context.fileId,
          label: context.label,
          selection: {
            text: context.text,
            fileName: context.fileName,
            ...(context.startLine !== undefined ? { startLine: context.startLine } : {}),
            ...(context.endLine !== undefined ? { endLine: context.endLine } : {}),
          },
        })
        break
      case 'table':
        resourceRefs.push({ type: 'table', id: context.tableId, label: context.label })
        break
      case 'table_selection':
        resourceRefs.push({
          type: 'table',
          id: context.tableId,
          label: context.label,
          selection: {
            tableName: context.tableName,
            rowIds: context.rowIds,
            ...(context.columnIds ? { columnIds: context.columnIds } : {}),
          },
        })
        break
      case 'knowledge':
        if (context.knowledgeId) {
          resourceRefs.push({ type: 'knowledge', id: context.knowledgeId, label: context.label })
        }
        break
      case 'past_chat':
        resourceRefs.push({ type: 'task', id: context.chatId, label: context.label })
        break
      case 'skill':
        skillIds.push(context.skillId)
        break
      default:
        break
    }
  }
  return {
    resourceRefs: resourceRefs.filter((ref) => typeof ref.id === 'string' && ref.id.length > 0),
    skillIds: [...new Set(skillIds)],
  }
}

function artifactResources(task: AgentTaskSnapshot | null): MothershipResource[] {
  if (!task) return []
  const entries: Array<{
    key: keyof AgentTaskSnapshot['artifacts']
    title: string
    path?: string
  }> = [
    {
      key: 'lesson_intro',
      title: '课程引入',
      path: task.artifacts.lesson_intro?.url,
    },
    {
      key: 'lecture_deck',
      title: '交互式讲义',
      path: task.artifacts.lecture_deck?.url,
    },
    {
      key: 'quiz',
      title: '知识检测',
    },
    {
      key: 'visual',
      title: '交互式可视化',
      path: task.artifacts.visual?.url,
    },
  ]
  const graphResource: MothershipResource = {
    type: 'generic',
    id: `runtime-graph:${task.id}`,
    title: '实时运行图',
  }
  const unlocked = new Set(
    (task.delivery?.queue ?? [])
      .filter((item) => item.state === 'unlocked' || item.state === 'consumed')
      .map((item) => item.artifact)
  )
  const hasDeliveryGate = (task.delivery?.queue ?? []).length > 0
  const artifactResources = entries
    .filter(({ key }) => {
      const artifact =
        key === 'lesson_intro' ? 'lesson-intro' : key === 'lecture_deck' ? 'lecture-deck' : key
      return Boolean(task.artifacts[key]?.available) && (!hasDeliveryGate || unlocked.has(artifact))
    })
    .sort((left, right) => {
      const order = task.delivery?.order ?? []
      return (
        order.indexOf(
          left.key === 'lesson_intro'
            ? 'lesson-intro'
            : left.key === 'lecture_deck'
              ? 'lecture-deck'
              : left.key
        ) -
        order.indexOf(
          right.key === 'lesson_intro'
            ? 'lesson-intro'
            : right.key === 'lecture_deck'
              ? 'lecture-deck'
              : right.key
        )
      )
    })
    .map(({ key, title, path }) => ({
      type: 'file' as const,
      id: `lingxi-artifact:${task.id}:${key === 'lesson_intro' ? 'lesson-intro' : key === 'lecture_deck' ? 'lecture-deck' : key}`,
      title,
      path,
    }))
  return [graphResource, ...artifactResources]
}

const EMPTY_LINGXI_QUEUE: QueuedMothershipMessage[] = []

function generateLingxiId(prefix: string): string {
  const uuid = globalThis.crypto?.randomUUID?.()
  return `${prefix}:${uuid ?? `${Date.now()}:${Math.random().toString(36).slice(2, 8)}`}`
}

function lingxiIdempotencyKey(messageId: string, revision = ''): string {
  return `lingxi-message:${messageId}${revision ? `:${revision}` : ''}`
}

export function useLingxiGraphChat(
  workspaceId: string,
  initialChatId: string | undefined,
  options?: UseChatOptions
): UseChatReturn {
  const router = useRouter()
  const adapter = options?.adapter
  const adapterRef = useRef<LingxiGraphChatAdapter | undefined>(adapter)
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
  const [localUsers, setLocalUsers] = useState<ChatMessage[]>([])
  const [isSending, setIsSending] = useState(false)
  const [isReconnecting, setIsReconnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [locallyStopped, setLocallyStopped] = useState(false)
  const [subscriptionEpoch, setSubscriptionEpoch] = useState(0)
  const [turnState, setTurnState] = useState<LingxiTurnState>('idle')
  const [dispatchingHeadId, setDispatchingHeadId] = useState<string | null>(null)
  const pendingQueueKey = useMemo(() => `lingxi:pending:${workspaceId}`, [workspaceId])
  const [activeResourceIdState, setActiveResourceIdState] = useState<string | null>(
    options?.initialActiveResourceId ?? null
  )
  const internalActiveResourceState = useState<string | null>(
    options?.initialActiveResourceId ?? null
  )
  const [activeResourceId, setActiveResourceId] =
    options?.activeResourceState ?? internalActiveResourceState
  const unsubscribeRef = useRef<(() => void) | null>(null)
  const messagesRef = useRef<ChatMessage[]>([])
  const requestIdRef = useRef<string | undefined>(initialChatId)
  const resolvedChatIdRef = useRef<string | undefined>(initialChatId)
  const queueKeyRef = useRef(initialChatId ?? pendingQueueKey)
  const turnStateRef = useRef<LingxiTurnState>('idle')
  const optimisticActiveRef = useRef(false)
  const dispatchingHeadIdRef = useRef<string | null>(null)
  const drainQueueRef = useRef<() => Promise<void>>(async () => {})

  const queueKey = resolvedChatId ?? pendingQueueKey
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
    if (!currentAdapter || currentAdapter.kind !== 'lingxigraph' || !taskId || locallyStopped) {
      unsubscribeRef.current?.()
      unsubscribeRef.current = null
      return
    }

    let cancelled = false
    setIsReconnecting(true)
    setError(null)

    const appendEvent = (event: AgentTaskEvent) => {
      if (cancelled) return
      const eventState = reduceLingxiTurnState(turnStateRef.current, event)
      applyTurnState(eventState)
      setEvents((current) => {
        if (current.some((candidate) => candidate.sequence === event.sequence)) return current
        return [...current, event].sort((a, b) => a.sequence - b.sequence)
      })
      void api.recordLearningEvent(taskId, event).catch(() => {})
      const eventWorkflowState =
        event.workflowState ?? (event.payload.workflowState as Record<string, unknown> | undefined)
      if (eventWorkflowState) setWorkflowState(eventWorkflowState)
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

    const start = async () => {
      try {
        const loaded = await currentAdapter.loadTask(taskId)
        if (cancelled) return
        setTask(loaded)
        // A send can win the race with the worker's first status update. Keep
        // the optimistic active turn until an event or snapshot catches up.
        if (!optimisticActiveRef.current) applyTurnState(turnStateFromTask(loaded))
        // Hydrate the durable event log in one state update.  Replaying old
        // SSE frames one-by-one makes a historical chat look like it has just
        // started running again and retriggers graph animations.
        const historyEvents = await currentAdapter.loadEvents(taskId)
        if (cancelled) return
        const orderedHistory = historyEvents.sort((left, right) => left.sequence - right.sequence)
        setEvents(orderedHistory)
        if (!optimisticActiveRef.current) {
          applyTurnState(reconcileLingxiTurnState(loaded, orderedHistory))
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
        unsubscribeRef.current = currentAdapter.subscribe(taskId, {
          from: historyEvents.at(-1)?.sequence ?? 0,
          onEvent: appendEvent,
          onEnd: async () => {
            try {
              const refreshed = await currentAdapter.loadTask(taskId)
              if (!cancelled) {
                setTask(refreshed)
                optimisticActiveRef.current = false
                applyTurnState(turnStateFromTask(refreshed))
                void api
                  .runtimeGraph(taskId)
                  .then((graph) => setWorkflowState(graph.workflowState))
                  .catch(() => {})
                onStreamEndRef.current?.(taskId, messagesRef.current)
                if (turnStateFromTask(refreshed) === 'awaiting_user') {
                  void drainQueueRef.current()
                }
              }
            } finally {
              if (!cancelled) setIsReconnecting(false)
            }
          },
        })
      } catch (cause) {
        if (cancelled) return
        setIsReconnecting(false)
        setError(cause instanceof Error ? cause.message : String(cause))
      }
    }
    void start()
    return () => {
      cancelled = true
      unsubscribeRef.current?.()
      unsubscribeRef.current = null
    }
  }, [applyTurnState, locallyStopped, resolvedChatId, subscriptionEpoch])

  const projection = useMemo(
    () =>
      task
        ? (adapterRef.current?.project(task, events) ?? projectLingxiGraphEvents(task, events))
        : null,
    [events, task]
  )
  const resources = useMemo(() => artifactResources(task), [task])
  // This is the same state used by the queue dispatcher and composer. The
  // task snapshot alone cannot represent a paused turn while its SSE stays
  // open, and an optimistic active flag alone cannot represent a terminal
  // task after reconnect.
  const assistantStreaming = turnState === 'active' && !locallyStopped
  const messages = useMemo(() => {
    if (!task) return localUsers.length > 0 ? localUsers : []
    const currentProjection = projection ?? projectLingxiGraphEvents(task, events)
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
  }, [events, localUsers, locallyStopped, projection, task])
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
      if (!currentAdapter || currentAdapter.kind !== 'lingxigraph' || !content) return false

      const prompt = requestMessage(content, contexts)
      const attachments = attachmentRefs(fileAttachments)
      const idempotencyKey = explicitIdempotencyKey ?? lingxiIdempotencyKey(userMessageId)
      const context = { ...contextOptions(contexts), idempotencyKey }
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
        let taskId = resolvedChatIdRef.current
        if (!taskId) {
          const created = await currentAdapter.createTask(prompt, attachments, context)
          taskId = created.id
          migrateQueuedMessages(pendingQueueKey, taskId)
          resolvedChatIdRef.current = taskId
          requestIdRef.current = taskId
          setResolvedChatId(taskId)
          router.replace(`/workspace/${workspaceId}/chat/${taskId}`)
          onRequestStartedRef.current?.({ requestId: taskId, userMessageId })
          onResourceEventRef.current?.(`runtime-graph:${taskId}`)
        } else {
          requestIdRef.current = taskId
          await currentAdapter.sendMessage(taskId, prompt, attachments, context)
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
    [applyTurnState, migrateQueuedMessages, pendingQueueKey, router, workspaceId]
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
          for (const [chatKey, queue] of Object.entries(currentQueues)) {
            if (queue.some((candidate) => candidate.id === liveMessage.id)) {
              removeQueuedMessage(chatKey, liveMessage.id)
            }
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
    if (dispatchingHeadIdRef.current) return
    // A native interrupt is a resumable learner turn. An SSE stream remains
    // open in this state, so queue draining must be triggered by the event or
    // snapshot transition rather than by stream end.
    if (!['idle', 'awaiting_user'].includes(turnStateRef.current)) return
    const dispatchKey = queueKeyRef.current
    const state = useMothershipQueueStore.getState()
    const queue = state.queues[dispatchKey] ?? EMPTY_LINGXI_QUEUE
    const next = queue[0]
    if (!next || state.editing[dispatchKey] === next.id) return
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
    if (!taskId || !currentAdapter || currentAdapter.kind !== 'lingxigraph') return
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
    lingxiRuntime: { task, events, workflowState, turnState },
    getCurrentRequestId: () => requestIdRef.current,
  }
}
