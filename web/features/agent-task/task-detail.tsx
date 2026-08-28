'use client'

import { useCallback, useEffect, useState } from 'react'
import type { AgentTaskSnapshot } from '@/entities/agent-task/model'
import { agentTaskApi } from '@/shared/api/client'
import { ErrorState, LoadingState } from '@/shared/ui/async-state'

export function TaskDetail({ taskId }: { taskId: string }) {
  const [task, setTask] = useState<AgentTaskSnapshot | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setTask(await agentTaskApi.get(taskId))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load task')
    }
  }, [taskId])

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => void load(), 4000)
    return () => window.clearInterval(timer)
  }, [load])

  async function send(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!message.trim()) return
    try {
      await agentTaskApi.sendMessage(taskId, message.trim())
      setMessage('')
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to send message')
    }
  }

  if (!task && !error) return <LoadingState label='Opening task…' />

  return (
    <div className='stack-lg'>
      {error && <ErrorState message={error} />}
      {task && (
        <>
          <section className='hero-card compact'>
            <span className='eyebrow'>Agent task · {task.status}</span>
            <h1>{task.title || task.prompt}</h1>
            <p>{task.prompt}</p>
          </section>
          <div className='metric-grid'>
            <article>
              <span>Plan</span>
              <strong>{task.workItems?.length ?? 0} steps</strong>
            </article>
            <article>
              <span>Artifacts</span>
              <strong>{availableArtifacts(task)} ready</strong>
            </article>
            <article>
              <span>Decisions</span>
              <strong>{task.decisions?.length ?? 0} logged</strong>
            </article>
          </div>
          <section className='data-card wide'>
            <span className='eyebrow'>Delivery</span>
            <h2>{task.runtime_status || 'Lingxi is working through the task.'}</h2>
            {task.error && <ErrorState message={task.error} />}
          </section>
          <form className='inline-form' onSubmit={send}>
            <input
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder='Add direction or ask a follow-up'
            />
            <button className='button primary' type='submit'>
              Send
            </button>
          </form>
        </>
      )}
    </div>
  )
}

function availableArtifacts(task: AgentTaskSnapshot) {
  return Object.values(task.artifacts).filter((artifact) => artifact.available).length
}
