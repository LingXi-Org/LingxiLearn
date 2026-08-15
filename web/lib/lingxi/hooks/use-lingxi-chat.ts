'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api, subscribeAgentEvents } from '@/lib/lingxi/api'
import type { LingxiChatMessage } from '@/lib/lingxi/chat-types'
import { projectLingxiGraphEvents } from '@/lib/lingxi/lingxi-graph-adapter'
import {
  type AgentTaskEvent,
  type AgentTaskSnapshot,
  isAgentTaskTerminal,
} from '@/lib/lingxi/types'

export type LingxiArtifactKind =
  | 'lesson-intro'
  | 'lecture-deck'
  | 'quiz'
  | 'visual'

export type LingxiWorkspaceResourceKind = 'workspace-tables' | 'workspace-files' | 'runtime-logs'

export type LingxiResourceKind = LingxiArtifactKind | LingxiWorkspaceResourceKind

export interface LingxiArtifactResourceDescriptor {
  id: string
  kind: LingxiResourceKind
  title: string
  available: boolean
}

function isTerminal(task: AgentTaskSnapshot | null): boolean {
  return isAgentTaskTerminal(task)
}

function artifactResources(task: AgentTaskSnapshot | null): LingxiArtifactResourceDescriptor[] {
  if (!task) return []
  const resources: Array<{
    kind: LingxiArtifactKind
    title: string
    available: boolean
  }> = [
    {
      kind: 'lesson-intro',
      title: '课程引入',
      available: Boolean(task.artifacts.lesson_intro?.available),
    },
    {
      kind: 'lecture-deck',
      title: '交互式讲义',
      available: Boolean(task.artifacts.lecture_deck?.available),
    },
    {
      kind: 'quiz',
      title: '知识检测',
      available: Boolean(task.artifacts.quiz?.available),
    },
    {
      kind: 'visual',
      title: '可视化讲解',
      available: Boolean(task.artifacts.visual?.available),
    },
  ]
  const unlocked = new Set(
    (task.delivery?.queue ?? [])
      .filter((item) => item.state === 'unlocked' || item.state === 'consumed')
      .map((item) => item.artifact)
  )
  const hasDeliveryGate = (task.delivery?.queue ?? []).length > 0
  const artifactDescriptors = resources
    .filter((resource) => resource.available && (!hasDeliveryGate || unlocked.has(resource.kind)))
    .sort((left, right) => (task.delivery?.order ?? []).indexOf(left.kind) - (task.delivery?.order ?? []).indexOf(right.kind))
    .map((resource) => ({ ...resource, id: `lingxi-artifact:${task.id}:${resource.kind}` }))
  return [
    ...artifactDescriptors,
    { id: 'lingxi-workspace:tables', kind: 'workspace-tables', title: '运行表格', available: true },
    { id: 'lingxi-workspace:files', kind: 'workspace-files', title: '运行文件', available: true },
    { id: 'lingxi-workspace:logs', kind: 'runtime-logs', title: '运行日志', available: true },
  ]
}

export function useLingxiChat(workspaceId: string, initialTaskId?: string) {
  const router = useRouter()
  const [taskId, setTaskId] = useState(initialTaskId)
  const [task, setTask] = useState<AgentTaskSnapshot | null>(null)
  const [events, setEvents] = useState<AgentTaskEvent[]>([])
  const [userMessages, setUserMessages] = useState<LingxiChatMessage[]>([])
  const [isSending, setIsSending] = useState(false)
  const [isReconnecting, setIsReconnecting] = useState(Boolean(initialTaskId))
  const [error, setError] = useState<string | null>(null)
  const [locallyStopped, setLocallyStopped] = useState(false)
  const taskIdRef = useRef(taskId)
  const lastSequenceRef = useRef(0)

  useEffect(() => {
    taskIdRef.current = taskId
  }, [taskId])

  useEffect(() => {
    setTaskId(initialTaskId)
    setTask(null)
    setEvents([])
    setUserMessages([])
    setError(null)
    setLocallyStopped(false)
    setIsReconnecting(Boolean(initialTaskId))
  }, [initialTaskId])

  useEffect(() => {
    if (!taskId) {
      setIsReconnecting(false)
      return
    }

    let cancelled = false
    let refreshTimer: ReturnType<typeof setTimeout> | null = null
    lastSequenceRef.current = 0
    setIsReconnecting(true)
    setError(null)

    const refresh = async () => {
      try {
        const nextTask = await api.agentTask(taskId)
        if (cancelled) return
        setTask(nextTask)
        setUserMessages((current) =>
          current.length > 0
            ? current
            : [{ id: `lingxi-user:${nextTask.id}`, role: 'user', content: nextTask.prompt }]
        )
        setIsReconnecting(false)
      } catch (cause) {
        if (!cancelled) {
          setIsReconnecting(false)
          setError(cause instanceof Error ? cause.message : String(cause))
        }
      }
    }

    const hydrate = async () => {
      await refresh()
      try {
        const history = await api.agentTaskEvents(taskId)
        if (cancelled) return
        const replay = history.events.sort((left, right) => left.sequence - right.sequence)
        setEvents(replay)
        lastSequenceRef.current = replay.at(-1)?.sequence ?? 0
      } catch {
        // The live subscription below remains the fallback for older servers.
      }
    }

    let unsubscribe = () => {}
    const start = async () => {
      await hydrate()
      if (cancelled) return
      unsubscribe = subscribeAgentEvents(
        taskId,
        (event) => {
          if (cancelled) return
          lastSequenceRef.current = Math.max(lastSequenceRef.current, event.sequence)
          setEvents((current) =>
            current.some((candidate) => candidate.sequence === event.sequence)
              ? current
              : [...current, event].sort((a, b) => a.sequence - b.sequence)
          )
          if (refreshTimer) clearTimeout(refreshTimer)
          refreshTimer = setTimeout(() => void refresh(), 180)
        },
        { from: lastSequenceRef.current, onEnd: () => void refresh() }
      )
    }
    void start()

    return () => {
      cancelled = true
      unsubscribe()
      if (refreshTimer) clearTimeout(refreshTimer)
    }
  }, [taskId])

  const projection = useMemo(
    () => (task ? projectLingxiGraphEvents(task, events) : null),
    [events, task]
  )

  const messages = useMemo<LingxiChatMessage[]>(() => {
    if (!task || !projection) return userMessages
    return [
      ...(userMessages.length > 0
        ? userMessages
        : [{ id: `lingxi-user:${task.id}`, role: 'user' as const, content: task.prompt }]),
      {
        id: `lingxi-assistant:${task.id}`,
        role: 'assistant',
        content: projection.assistantText || '正在连接 LingxiGraph…',
        contentBlocks: [
          ...projection.blocks,
          ...(locallyStopped && !projection.isTerminal ? [{ type: 'stopped' as const }] : []),
        ],
        requestId: task.id,
      },
    ]
  }, [locallyStopped, projection, task, userMessages])

  const sendMessage = useCallback(
    async (message: string) => {
      const content = message.trim()
      if (!content || isSending) return
      const userMessage: LingxiChatMessage = {
        id: `lingxi-user:${Date.now()}`,
        role: 'user',
        content,
      }
      setUserMessages((current) => [...current, userMessage])
      setIsSending(true)
      setLocallyStopped(false)
      setError(null)

      try {
        let currentTaskId = taskIdRef.current
        if (!currentTaskId) {
          const created = await api.createAgentTask(content)
          currentTaskId = created.id
          taskIdRef.current = currentTaskId
          setTaskId(currentTaskId)
          router.replace(`/workspace/${workspaceId}/chat/${currentTaskId}`)
        } else {
          await api.agentMessage(currentTaskId, content)
        }
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause))
      } finally {
        setIsSending(false)
      }
    },
    [isSending, router, workspaceId]
  )

  const stopGeneration = useCallback(() => {
    setLocallyStopped(true)
  }, [])

  const reconnect = useCallback(() => {
    if (!taskIdRef.current) return
    setError(null)
    setIsReconnecting(true)
    setTask(null)
  }, [])

  return {
    task,
    events,
    messages,
    resources: artifactResources(task),
    taskId,
    isSending,
    isReconnecting,
    error,
    sendMessage,
    stopGeneration,
    reconnect,
    isTerminal: isTerminal(task),
  }
}
