'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import type { FilePreviewSession } from '@/lib/copilot/request/session/file-preview-session-contract'
import type { MothershipResource, MothershipResourceType } from '@/lib/copilot/resources/types'
import { api, type LingxiAttachmentRef } from '@/lib/lingxi/api'
import {
  type LingxiGraphChatAdapter,
  projectLingxiGraphEvents,
} from '@/lib/lingxi/lingxi-graph-adapter'
import type { AgentTaskEvent, AgentTaskSnapshot } from '@/lib/lingxi/types'
import { lingxiWorkflowId } from '@/lib/lingxi/components/lingxi-workflow'
import type { ChatContext } from '@/stores/panel'
import type {
  ChatMessage,
  FileAttachmentForApi,
  GenericResourceData,
  QueuedMessage,
} from '../types'
import type { SendMessageOptions, UseChatOptions, UseChatReturn } from './use-chat'

const TERMINAL_TASK_STATUSES = new Set(['handed_off', 'completed', 'partial', 'failed', 'cancelled'])

function taskIsTerminal(task: AgentTaskSnapshot | null): boolean {
  return task !== null && TERMINAL_TASK_STATUSES.has(task.status)
}

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
    contexts: contexts?.map(({ kind, label }) => ({ kind, label })),
    fileAttachments,
  }
}

function contextSuffix(contexts?: ChatContext[]): string {
  const labels = contexts?.map((context) => context.label.trim()).filter(Boolean) ?? []
  return labels.length > 0 ? `\n\n[Context: ${labels.join(', ')}]` : ''
}

function attachmentSuffix(attachments?: FileAttachmentForApi[]): string {
  const names = attachments?.map((file) => file.filename.trim()).filter(Boolean) ?? []
  return names.length > 0 ? `\n\n[附件: ${names.join(', ')}]` : ''
}

function attachmentRefs(attachments?: FileAttachmentForApi[]): LingxiAttachmentRef[] {
  return (attachments ?? [])
    .filter((file) => Boolean(file.key && file.filename))
    .map(({ key, path, filename, media_type, size }) => ({
      key,
      path,
      filename,
      media_type,
      size,
    }))
}

function parseNativeQuizAnswer(
  task: AgentTaskSnapshot,
  message: string
): Record<string, unknown> | null {
  const quiz = task.artifacts.quiz?.data
  if (!quiz || task.quiz_submission || task.status !== 'awaiting_user') return null
  const lines = message.split('\n')
  if (lines.length !== quiz.questions.length) return null

  const answers: Record<string, unknown> = {}
  for (const [index, question] of quiz.questions.entries()) {
    const prefix = `${question.prompt} — `
    if (!lines[index].startsWith(prefix)) return null
    const answer = lines[index].slice(prefix.length).trim()
    if (!answer) return null
    if (question.type === 'short_text') {
      answers[question.id] = answer
      continue
    }
    const labels = question.type === 'multi_choice' ? answer.split(', ').filter(Boolean) : [answer]
    const optionIds = labels.map(
      (label) => question.options.find((option) => option.label === label)?.id ?? label
    )
    answers[question.id] = question.type === 'multi_choice' ? optionIds : optionIds[0]
  }
  return answers
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
    {
      key: 'knowledge_graph',
      title: 'Lingxi 知识图谱',
      path: task.artifacts.knowledge_graph?.url,
    },
  ]
  return entries
    .filter(({ key }) => key === 'knowledge_graph' || Boolean(task.artifacts[key]?.available))
    .map(({ key, title, path }) => {
      const kind =
        key === 'lesson_intro'
          ? 'lesson-intro'
          : key === 'lecture_deck'
            ? 'lecture-deck'
            : key === 'knowledge_graph'
              ? 'knowledge-graph'
              : key
      return kind === 'knowledge-graph'
        ? { type: 'workflow' as const, id: lingxiWorkflowId(task.id), title }
        : { type: 'file' as const, id: `lingxi-artifact:${task.id}:${kind}`, title, path }
    })
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
  const [savedResources, setSavedResources] = useState<MothershipResource[]>([])
  const [events, setEvents] = useState<AgentTaskEvent[]>([])
  const [localUsers, setLocalUsers] = useState<ChatMessage[]>([])
  const [isSending, setIsSending] = useState(false)
  const [isReconnecting, setIsReconnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [locallyStopped, setLocallyStopped] = useState(false)
  const [subscriptionEpoch, setSubscriptionEpoch] = useState(0)
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
    setEvents([])
    setLocalUsers([])
    setSavedResources([])
    setError(null)
    setLocallyStopped(false)
  }, [initialChatId])

  useEffect(() => {
    const currentAdapter = adapterRef.current
    const taskId = resolvedChatId
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
      if (event.kind === 'artifact.ready' || event.kind === 'artifact.recovered') {
        const artifact = typeof event.payload.artifact === 'string' ? event.payload.artifact : ''
        if (artifact) {
          const resourceId =
            artifact === 'knowledge_graph'
              ? lingxiWorkflowId(taskId)
              : `lingxi-artifact:${taskId}:${artifact}`
          onResourceEventRef.current?.(resourceId)
        }
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
        setSavedResources((loaded.resources ?? []) as MothershipResource[])
        setLocalUsers((current) =>
          current.length > 0 ? current : [userMessage(`lingxi-user:${loaded.id}`, loaded.prompt)]
        )
        requestIdRef.current = loaded.id
        setIsReconnecting(false)
        unsubscribeRef.current = currentAdapter.subscribe(taskId, {
          onEvent: appendEvent,
          onEnd: async () => {
            try {
              const refreshed = await currentAdapter.loadTask(taskId)
              if (!cancelled) {
                setTask(refreshed)
                onStreamEndRef.current?.(taskId, messagesRef.current)
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
  const resources = useMemo(() => {
    const artifacts = artifactResources(task)
    const seen = new Set(artifacts.map((resource) => resource.id))
    return [...artifacts, ...savedResources.filter((resource) => !seen.has(resource.id))]
  }, [savedResources, task])
  const assistantStreaming = Boolean(task && !taskIsTerminal(task) && !locallyStopped && isSending)
  const messages = useMemo(() => {
    if (!task) return localUsers.length > 0 ? localUsers : []
    const currentProjection = projection ?? projectLingxiGraphEvents(task, events)
    const assistant: ChatMessage = {
      id: `lingxi-assistant:${task.id}`,
      role: 'assistant',
      content: currentProjection.assistantText || '正在连接学习智能体图…',
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

  const sendMessage = useCallback(
    async (
      message: string,
      _fileAttachments?: FileAttachmentForApi[],
      contexts?: ChatContext[],
      _sendOptions?: SendMessageOptions
    ) => {
      const currentAdapter = adapterRef.current
      if (!currentAdapter || currentAdapter.kind !== 'lingxigraph') return
      const content = message.trim()
      if (!content) return
      const refs = attachmentRefs(_fileAttachments)
      const requestMessage = `${content}${contextSuffix(contexts)}${attachmentSuffix(_fileAttachments)}`
      const userId = `lingxi-user:${Date.now()}`
      setIsSending(true)
      setError(null)
      setLocallyStopped(false)
      setSubscriptionEpoch((current) => current + 1)
      setLocalUsers((current) => [...current, userMessage(userId, content, contexts)])

      try {
        let taskId = resolvedChatId
        if (!taskId) {
          const created = await currentAdapter.createTask(requestMessage, refs)
          taskId = created.id
          requestIdRef.current = taskId
          setResolvedChatId(taskId)
          router.replace(`/workspace/${workspaceId}/chat/${taskId}`)
          onRequestStartedRef.current?.({ requestId: taskId, userMessageId: userId })
        } else {
          requestIdRef.current = taskId
          const currentTask = task
          const quizAnswers = currentTask ? parseNativeQuizAnswer(currentTask, content) : null
          if (quizAnswers) {
            await api.submitAgentQuiz(taskId, crypto.randomUUID(), quizAnswers)
          } else {
            await currentAdapter.sendMessage(taskId, requestMessage, refs)
          }
          const refreshed = await currentAdapter.loadTask(taskId)
          setTask(refreshed)
          onRequestStartedRef.current?.({ requestId: taskId, userMessageId: userId })
        }
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
      } finally {
        setIsSending(false)
      }
    },
    [resolvedChatId, router, task, workspaceId]
  )

  const stopGeneration = useCallback(async () => {
    setLocallyStopped(true)
    const taskId = resolvedChatId
    if (!taskId) return
    try {
      await adapterRef.current?.cancelTask(taskId)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [resolvedChatId])

  const persistResources = useCallback(
    (next: MothershipResource[]) => {
      setSavedResources(next)
      const taskId = resolvedChatId
      if (taskId) {
        void adapterRef.current?.updateTaskMetadata(taskId, {
          resources: next as Array<Record<string, unknown>>,
        })
      }
    },
    [resolvedChatId]
  )
  const addResource = useCallback(
    (resource: MothershipResource) => {
      const next = [...savedResources.filter((current) => current.id !== resource.id), resource]
      persistResources(next)
      return true
    },
    [persistResources, savedResources]
  )
  const removeResource = useCallback(
    (_type: MothershipResourceType, resourceId: string) => {
      if (effectiveActiveResourceId === resourceId) setEffectiveActiveResourceId(null)
      persistResources(savedResources.filter((resource) => resource.id !== resourceId))
    },
    [effectiveActiveResourceId, persistResources, savedResources, setEffectiveActiveResourceId]
  )
  const reorderResources = useCallback(
    (next: MothershipResource[]) => persistResources(next),
    [persistResources]
  )
  const noQueuedMessages = useMemo<QueuedMessage[]>(() => [], [])
  const noOp = useCallback(() => {}, [])
  const noOpAsync = useCallback(async () => {}, [])

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
    messageQueue: noQueuedMessages,
    removeFromQueue: noOp,
    sendNow: noOpAsync,
    editQueuedMessage: () => undefined,
    cancelQueueEdit: noOp,
    editingQueuedId: null,
    dispatchingHeadId: null,
    previewSession: null as FilePreviewSession | null,
    genericResourceData: null as GenericResourceData | null,
    getCurrentRequestId: () => requestIdRef.current,
  }
}
