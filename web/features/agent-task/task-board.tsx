'use client'

import Link from 'next/link'
import { useCallback, useEffect, useId, useState } from 'react'
import type { AgentTaskListItem } from '@/entities/agent-task/model'
import { agentTaskApi } from '@/shared/api/client'
import { EmptyState, ErrorState, LoadingState } from '@/shared/ui/async-state'

export function TaskBoard({ workspaceId }: { workspaceId: string }) {
  const [tasks, setTasks] = useState<AgentTaskListItem[] | null>(null)
  const [prompt, setPrompt] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const promptId = useId()

  const load = useCallback(async () => {
    try {
      const response = await agentTaskApi.list()
      setTasks(response.tasks ?? [])
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load tasks')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!prompt.trim()) return
    setCreating(true)
    try {
      const task = await agentTaskApi.create(prompt.trim())
      window.location.assign(`/workspace/${workspaceId}/tasks/${task.id}`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to start task')
      setCreating(false)
    }
  }

  return (
    <div className='stack-lg'>
      <form className='prompt-card' onSubmit={submit}>
        <span className='eyebrow'>New learning task</span>
        <label htmlFor={promptId}>What do you want to understand or create?</label>
        <textarea
          id={promptId}
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder='Build me a focused lesson on…'
          rows={4}
        />
        <button className='button primary' disabled={creating || !prompt.trim()} type='submit'>
          {creating ? 'Starting…' : 'Start with Lingxi'}
        </button>
      </form>
      {error && <ErrorState message={error} />}
      {tasks === null ? (
        <LoadingState label='Loading your tasks…' />
      ) : tasks.length === 0 ? (
        <EmptyState
          title='No tasks yet'
          description='Your next question becomes a durable learning task.'
        />
      ) : (
        <div className='card-grid'>
          {tasks.map((task) => (
            <Link
              className='data-card'
              href={`/workspace/${workspaceId}/tasks/${task.id}`}
              key={task.id}
            >
              <div className='card-heading'>
                <span className={`status-dot status-${task.status}`} />
                <span className='status-label'>{task.status}</span>
              </div>
              <h2>{task.title || task.prompt}</h2>
              <p>{task.prompt}</p>
              <time>
                {task.created_at ? new Date(task.created_at).toLocaleString() : 'Just now'}
              </time>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
