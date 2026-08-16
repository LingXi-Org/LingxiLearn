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
  type AgentTaskEvent,
  type AgentTaskSnapshot,
  isAgentTaskActive,
} from '@/lib/lingxi/types'
import type { ChatContext } from '@/stores/panel'
import type {
  ChatMessage,
  ChatMessageAttachment,
  FileAttachmentForApi,
  GenericResourceData,
  QueuedMessage,
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
  return entries.length > 0 ? `\n\n[Context]\n${entries.map((entry) => `- ${entry}`).join('\n')}` : ''
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
      const artifact = key === 'lesson_intro' ? 'lesson-intro' : key === 'lecture_deck' ? 'lecture-deck' : key
      return Boolean(task.artifacts[key]?.available) && (!hasDeliveryGate || unlocked.has(artifact))
    })
    .sort((left, right) => {
      const order = task.delivery?.order ?? []
      return order.indexOf(left.key === 'lesson_intro' ? 'lesson-intro' : left.key === 'lecture_deck' ? 'lecture-deck' : left.key) - order.indexOf(right.key === 'lesson_intro' ? 'lesson-intro' : right.key === 'lecture_deck' ? 'lecture-deck' : right.key)
    })
    .map(({ key, title, path }) => ({
      type: 'file' as const,
      id: `lingxi-artifact:${task.id}:${key === 'lesson_intro' ? 'lesson-intro' : key === 'lecture_deck' ? 'lecture-deck' : key}`,
      title,
      path,
    }))
  return [graphResource, ...artifactResources]
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
  /** LingxiGraph keeps one durable task but the composer may accept FIFO turns. */
  const [messageQueue, setMessageQueue] = useState<QueuedMessage[]>([])
  const [editingQueuedId, setEditingQueuedId] = useState<string | null>(null)
  const [dispatchingHeadId, setDispatchingHeadId] = useState<string | null>(null)
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
  const activeTurnRef = useRef(false)
  const queueRef = useRef<QueuedMessage[]>([])
  const drainQueueRef = useRef<() => Promise<void>>(async () => {})

  useEffect(() => {
    resolvedChatIdRef.current = resolvedChatId
  }, [resolvedChatId])

  useEffect(() => {
    queueRef.current = messageQueue
  }, [messageQueue])

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
    setTask(null)
    setWorkflowState(null)
    setEvents([])
    setLocalUsers([])
    setError(null)
    setLocallyStopped(false)
    setMessageQueue([])
    setEditingQueuedId(null)
    setDispatchingHeadId(null)
    activeTurnRef.current = false
  }, [initialChatId])

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
        if (artifact) onResourceEventRef.current?.(artifactResourceId(taskId, artifact), 'artifact.ready')
        void currentAdapter
          .loadTask(taskId)
          .then((refreshed) => {
            if (!cancelled) setTask(refreshed)
          })
          .catch(() => {})
      }
      if (event.kind === 'delivery.unlocked') {
        const artifact = typeof event.payload.artifact === 'string' ? event.payload.artifact : ''
        if (artifact) onResourceEventRef.current?.(artifactResourceId(taskId, artifact), 'delivery.unlocked')
        void currentAdapter
          .loadTask(taskId)
          .then((refreshed) => {
            if (!cancelled) setTask(refreshed)
          })
          .catch(() => {})
      }
    }

    const start = async () => {
      try {
        const loaded = await currentAdapter.loadTask(taskId)
        if (cancelled) return
        setTask(loaded)
        // A send increments the subscription epoch before the worker has
        // necessarily flipped the persisted task row from terminal/awaiting to
        // running. Preserve that local in-flight turn until the SSE end hook
        // observes the authoritative status.
        activeTurnRef.current = activeTurnRef.current || isAgentTaskActive(loaded)
        // Hydrate the durable event log in one state update.  Replaying old
        // SSE frames one-by-one makes a historical chat look like it has just
        // started running again and retriggers graph animations.
        const historyEvents = await currentAdapter.loadEvents(taskId)
        if (cancelled) return
        setEvents(historyEvents.sort((left, right) => left.sequence - right.sequence))
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
                activeTurnRef.current = isAgentTaskActive(refreshed)
                void api
                  .runtimeGraph(taskId)
                  .then((graph) => setWorkflowState(graph.workflowState))
                  .catch(() => {})
                onStreamEndRef.current?.(taskId, messagesRef.current)
                if (!isAgentTaskActive(refreshed)) void drainQueueRef.current()
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
  }, [locallyStopped, resolvedChatId, subscriptionEpoch])

  const projection = useMemo(
    () =>
      task
        ? (adapterRef.current?.project(task, events) ?? projectLingxiGraphEvents(task, events))
        : null,
    [events, task]
  )
  const resources = useMemo(() => artifactResources(task), [task])
  const assistantStreaming = Boolean(task && isAgentTaskActive(task) && !locallyStopped)
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
      userMessageId = `lingxi-user:${Date.now()}`
    ): Promise<boolean> => {
      const currentAdapter = adapterRef.current
      const content = message.trim()
      if (!currentAdapter || currentAdapter.kind !== 'lingxigraph' || !content) return false

      const prompt = requestMessage(content, contexts)
      const attachments = attachmentRefs(fileAttachments)
      const context = contextOptions(contexts)
      activeTurnRef.current = true
      setIsSending(true)
      setError(null)
      setLocallyStopped(false)
      setSubscriptionEpoch((current) => current + 1)
      setLocalUsers((current) => [
        ...current,
        userMessage(userMessageId, content, contexts, fileAttachments),
      ])

      try {
        let taskId = resolvedChatIdRef.current
        if (!taskId) {
          const created = await currentAdapter.createTask(prompt, attachments, context)
          taskId = created.id
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
        activeTurnRef.current = false
        setError(cause instanceof Error ? cause.message : String(cause))
        return false
      } finally {
        setIsSending(false)
      }
    },
    [router, workspaceId]
  )

  const dispatchQueuedMessage = useCallback(
    async (message: QueuedMessage): Promise<boolean> => {
      setDispatchingHeadId(message.id)
      setMessageQueue((current) => current.filter((candidate) => candidate.id !== message.id))
      const sent = await sendDirect(
        message.content,
        message.fileAttachments,
        message.contexts,
        message.id
      )
      if (!sent) {
        setMessageQueue((current) => [message, ...current.filter((item) => item.id !== message.id)])
      }
      setDispatchingHeadId(null)
      return sent
    },
    [sendDirect]
  )

  const drainQueue = useCallback(async () => {
    if (activeTurnRef.current || dispatchingHeadId || queueRef.current.length === 0) return
    const next = queueRef.current[0]
    if (next) await dispatchQueuedMessage(next)
  }, [dispatchQueuedMessage, dispatchingHeadId])
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

      const currentEditId = editingQueuedId
      if (currentEditId) {
        const edited: QueuedMessage = {
          id: currentEditId,
          content: content || 'Analyze the attached file(s).',
          fileAttachments,
          contexts,
        }
        setEditingQueuedId(null)
        setMessageQueue((current) => current.filter((item) => item.id !== currentEditId))
        if (activeTurnRef.current) {
          setMessageQueue((current) => [...current, edited])
          return
        }
        await sendDirect(
          edited.content,
          edited.fileAttachments,
          edited.contexts,
          edited.id
        )
        return
      }

      if (activeTurnRef.current) {
        const queued: QueuedMessage = {
          id: `lingxi-queued:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`,
          content: content || 'Analyze the attached file(s).',
          fileAttachments,
          contexts,
        }
        setMessageQueue((current) => [...current, queued])
        return
      }

      await sendDirect(content || 'Analyze the attached file(s).', fileAttachments, contexts)
    },
    [editingQueuedId, sendDirect]
  )

  const stopGeneration = useCallback(async () => {
    setLocallyStopped(true)
    activeTurnRef.current = false
    const taskId = resolvedChatIdRef.current
    const currentAdapter = adapterRef.current
    if (!taskId || !currentAdapter || currentAdapter.kind !== 'lingxigraph') return
    try {
      await currentAdapter.cancelTask(taskId)
      const refreshed = await currentAdapter.loadTask(taskId)
      setTask(refreshed)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [])

  const addResource = useCallback((_resource: MothershipResource) => true, [])
  const removeResource = useCallback(
    (_type: MothershipResourceType, resourceId: string) => {
      if (effectiveActiveResourceId === resourceId) setEffectiveActiveResourceId(null)
    },
    [effectiveActiveResourceId, setEffectiveActiveResourceId]
  )
  const reorderResources = useCallback((_next: MothershipResource[]) => {}, [])
  const removeFromQueue = useCallback((id: string) => {
    setMessageQueue((current) => current.filter((message) => message.id !== id))
    if (editingQueuedId === id) setEditingQueuedId(null)
  }, [editingQueuedId])

  const sendNow = useCallback(
    async (id: string) => {
      const message = queueRef.current.find((candidate) => candidate.id === id)
      if (!message || dispatchingHeadId) return
      if (activeTurnRef.current) await stopGeneration()
      await dispatchQueuedMessage(message)
    },
    [dispatchQueuedMessage, dispatchingHeadId, stopGeneration]
  )

  const editQueuedMessage = useCallback((id: string): QueuedMessage | undefined => {
    const message = queueRef.current.find((candidate) => candidate.id === id)
    if (!message) return undefined
    setEditingQueuedId(id)
    return message
  }, [])

  const cancelQueueEdit = useCallback(() => {
    setEditingQueuedId(null)
  }, [])

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
    lingxiRuntime: { task, events, workflowState },
    getCurrentRequestId: () => requestIdRef.current,
  }
}
