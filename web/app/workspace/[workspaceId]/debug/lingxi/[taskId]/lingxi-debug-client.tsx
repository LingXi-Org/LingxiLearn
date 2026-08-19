'use client'

import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { api } from '@/lib/lingxi/api'
import type { AgentTaskEvent, AgentTaskSnapshot } from '@/lib/lingxi/types'

type RuntimeGraph = Awaited<ReturnType<typeof api.runtimeGraph>>

export function LingxiDebugClient() {
  const { taskId } = useParams<{ taskId: string }>()
  const [task, setTask] = useState<AgentTaskSnapshot | null>(null)
  const [events, setEvents] = useState<AgentTaskEvent[]>([])
  const [runtimeGraph, setRuntimeGraph] = useState<RuntimeGraph | null>(null)
  const [decisions, setDecisions] = useState<Array<Record<string, unknown>>>([])
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [nextTask, nextEvents, nextGraph, nextDecisions] = await Promise.all([
        api.agentTask(taskId),
        api.agentTaskEvents(taskId),
        api.runtimeGraph(taskId),
        api.agentTaskDecisions(taskId),
      ])
      setTask(nextTask)
      setEvents(nextEvents.events.sort((left, right) => left.sequence - right.sequence))
      setRuntimeGraph(nextGraph)
      setDecisions(nextDecisions.decisions)
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [taskId])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(), 2000)
    return () => window.clearInterval(timer)
  }, [refresh])

  return (
    <main className='min-h-screen bg-neutral-950 p-6 font-mono text-xs text-neutral-200'>
      <div className='mx-auto max-w-7xl space-y-4'>
        <header className='flex items-center justify-between border-b border-neutral-800 pb-4'>
          <div>
            <h1 className='text-lg font-semibold text-white'>Lingxi 临时可观测调试页</h1>
            <p className='mt-1 text-neutral-400'>task: {taskId} · 每 2 秒刷新</p>
          </div>
          <button
            type='button'
            className='rounded border border-neutral-700 px-3 py-2 text-neutral-200 hover:bg-neutral-800'
            onClick={() => void refresh()}
          >
            立即刷新
          </button>
        </header>
        {error ? (
          <pre className='rounded border border-red-900 bg-red-950/40 p-3 text-red-300'>
            {error}
          </pre>
        ) : null}
        <section className='grid gap-4 md:grid-cols-4'>
          {[
            ['任务状态', task?.status ?? 'loading'],
            ['运行状态', task?.turnStatus ?? task?.goalStatus ?? task?.status ?? '—'],
            ['执行 ID', task?.latest_execution_id ?? '—'],
            ['事件数', String(events.length)],
          ].map(([label, value]) => (
            <div key={label} className='rounded border border-neutral-800 bg-neutral-900 p-3'>
              <div className='text-neutral-500'>{label}</div>
              <div className='mt-2 break-all text-white'>{value}</div>
            </div>
          ))}
        </section>
        <section className='grid gap-4 lg:grid-cols-2'>
          <div className='rounded border border-neutral-800 bg-neutral-900 p-4'>
            <h2 className='mb-3 text-sm font-semibold text-white'>产物与交付队列</h2>
            <pre className='max-h-80 overflow-auto whitespace-pre-wrap text-emerald-300'>
              {JSON.stringify({ artifacts: task?.artifacts, delivery: task?.delivery }, null, 2)}
            </pre>
          </div>
          <div className='rounded border border-neutral-800 bg-neutral-900 p-4'>
            <h2 className='mb-3 text-sm font-semibold text-white'>当前运行图状态</h2>
            <pre className='max-h-80 overflow-auto whitespace-pre-wrap text-sky-300'>
              {JSON.stringify(runtimeGraph, null, 2)}
            </pre>
          </div>
        </section>
        <section className='rounded border border-neutral-800 bg-neutral-900 p-4'>
          <h2 className='mb-3 text-sm font-semibold text-white'>事件日志（按序列）</h2>
          <div className='max-h-[32rem] overflow-auto'>
            <table className='w-full border-collapse text-left'>
              <thead className='sticky top-0 bg-neutral-900 text-neutral-500'>
                <tr>
                  <th className='p-2'>#</th>
                  <th className='p-2'>kind</th>
                  <th className='p-2'>agent</th>
                  <th className='p-2'>payload</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr
                    key={`${event.sequence}-${event.kind}`}
                    className='border-t border-neutral-800 align-top'
                  >
                    <td className='p-2 text-neutral-500'>{event.sequence}</td>
                    <td className='p-2 text-amber-300'>{event.kind}</td>
                    <td className='p-2 text-violet-300'>{event.agent ?? '—'}</td>
                    <td className='whitespace-pre-wrap break-all p-2 text-neutral-300'>
                      {JSON.stringify(event.payload)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <details className='rounded border border-neutral-800 bg-neutral-900 p-4'>
          <summary className='cursor-pointer text-sm font-semibold text-white'>
            编排决策 JSON
          </summary>
          <pre className='mt-3 max-h-96 overflow-auto whitespace-pre-wrap text-fuchsia-300'>
            {JSON.stringify(decisions, null, 2)}
          </pre>
        </details>
      </div>
    </main>
  )
}
