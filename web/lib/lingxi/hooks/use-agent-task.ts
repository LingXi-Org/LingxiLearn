'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { api, subscribeAgentEvents } from '@/lib/lingxi/api'
import type { AgentTaskEvent, AgentTaskSnapshot } from '@/lib/lingxi/types'

export function useAgentTask(taskId: string) {
  const [task, setTask] = useState<AgentTaskSnapshot | null>(null)
  const [events, setEvents] = useState<AgentTaskEvent[]>([])
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(Boolean(taskId))
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const refresh = useCallback(async () => {
    if (!taskId) return
    try {
      setLoading(true)
      setTask(await api.agentTask(taskId))
      setError(undefined)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setLoading(false)
    }
  }, [taskId])

  useEffect(() => {
    setTask(null)
    setEvents([])
    setError(undefined)
    setLoading(Boolean(taskId))
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (!taskId) return
    return subscribeAgentEvents(
      taskId,
      (event) => {
        setEvents((current) =>
          current.some((item) => item.sequence === event.sequence)
            ? current
            : [...current, event].sort((a, b) => a.sequence - b.sequence)
        )
        if (refreshTimer.current) clearTimeout(refreshTimer.current)
        refreshTimer.current = setTimeout(() => void refresh(), 160)
      },
      { onEnd: () => void refresh() }
    )
  }, [taskId, refresh])

  useEffect(() => {
    if (!task || (task.status !== 'queued' && task.status !== 'running')) return
    const timer = setInterval(() => void refresh(), 1800)
    return () => clearInterval(timer)
  }, [refresh, task])

  useEffect(
    () => () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current)
    },
    []
  )

  return { task, events, error, loading, refresh }
}
