'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui-kit'
import { api } from '@/lib/lingxi/api'
import { useAgentTask } from '@/lib/lingxi/hooks/use-agent-task'
import type { PublicQuizQuestion } from '@/lib/lingxi/types'

interface LingxiArtifactResourceProps {
  resourceId: string
}

type ArtifactKind = 'lesson-intro' | 'lecture-deck' | 'quiz' | 'visual'
type WorkspaceResourceKind = 'workspace-tables' | 'workspace-files' | 'runtime-logs'
type ParsedTaskResource = { taskId: string; kind: ArtifactKind }
type ParsedResource = { workspaceKind: WorkspaceResourceKind } | ParsedTaskResource | null

function localizedStatus(value: unknown): string {
  const labels: Record<string, string> = {
    pending: '等待中',
    queued: '排队中',
    running: '运行中',
    executing: '执行中',
    completed: '已完成',
    success: '成功',
    failed: '失败',
    error: '错误',
    cancelled: '已取消',
    paused: '已暂停',
    partial: '部分完成',
  }
  const text = String(value ?? '')
  return labels[text] ?? text
}

function parseResourceId(resourceId: string): ParsedResource {
  if (resourceId === 'lingxi-workspace:tables')
    return { workspaceKind: 'workspace-tables' as const }
  if (resourceId === 'lingxi-workspace:files') return { workspaceKind: 'workspace-files' as const }
  if (resourceId === 'lingxi-workspace:logs') return { workspaceKind: 'runtime-logs' as const }
  const parts = resourceId.split(':')
  const taskId = parts.slice(1, -1).join(':')
  const rawKind = parts.at(-1)
  const kind =
    rawKind === 'lesson_intro'
      ? 'lesson-intro'
      : rawKind === 'lecture_deck'
        ? 'lecture-deck'
        : rawKind
  if (!taskId || !kind) return null
  if (!['lesson-intro', 'lecture-deck', 'quiz', 'visual'].includes(kind)) return null
  return { taskId, kind: kind as ArtifactKind }
}

function WorkspaceResource({ kind }: { kind: WorkspaceResourceKind }) {
  const [state, setState] = useState<{ loading: boolean; error: string | null; data: unknown[] }>({
    loading: true,
    error: null,
    data: [],
  })

  useEffect(() => {
    let disposed = false
    const load = async () => {
      try {
        const data =
          kind === 'workspace-tables'
            ? ((await api.workspaceTables()).tables ?? [])
            : kind === 'workspace-files'
              ? ((await api.workspaceFiles('active')).files ?? [])
              : ((await api.logs()).data ?? [])
        if (!disposed) setState({ loading: false, error: null, data })
      } catch (cause) {
        if (!disposed) {
          setState({
            loading: false,
            error: cause instanceof Error ? cause.message : String(cause),
            data: [],
          })
        }
      }
    }
    void load()
    return () => {
      disposed = true
    }
  }, [kind])

  if (state.loading)
    return <div className='p-6 text-[var(--text-secondary)] text-sm'>正在加载运行资源…</div>
  if (state.error) return <div className='p-6 text-[var(--text-error)] text-sm'>{state.error}</div>
  if (state.data.length === 0)
    return (
      <div className='p-6 text-[var(--text-secondary)] text-sm'>
        运行过程中暂时没有可展示的数据。
      </div>
    )

  return (
    <div className='h-full overflow-y-auto p-4'>
      <div className='space-y-2'>
        {state.data.map((item, index) => {
          const row = item as Record<string, unknown>
          const id = String(row.id ?? index)
          const title = String(row.name ?? row.title ?? row.taskId ?? row.id ?? '运行记录')
          const href =
            kind === 'workspace-tables'
              ? `/workspace/lingxi/tables/${id}`
              : kind === 'workspace-files'
                ? `/workspace/lingxi/files/${id}`
                : `/workspace/lingxi/logs`
          return (
            <Link
              key={id}
              href={href}
              className='block rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 hover:bg-[var(--surface-hover)]'
            >
              <p className='truncate text-[var(--text-primary)] text-sm'>{title}</p>
              <p className='mt-1 truncate text-[var(--text-muted)] text-[11px]'>
                {kind === 'workspace-tables'
                  ? `${String(row.totalRows ?? row.rowCount ?? 0)} 行`
                  : kind === 'workspace-files'
                    ? `${String(row.mimeType ?? row.type ?? '文件')} · ${String(row.size ?? 0)} 字节`
                    : `${localizedStatus(row.status ?? '运行记录')} · ${String(row.startedAt ?? row.createdAt ?? '')}`}
              </p>
            </Link>
          )
        })}
      </div>
    </div>
  )
}

function normalizeAnswer(question: PublicQuizQuestion, answer: string): string | string[] {
  if (question.type === 'short_text') return answer.trim()
  const labels = question.type === 'multi_choice' ? answer.split(' · ').filter(Boolean) : [answer]
  const ids = labels.map(
    (label) => question.options.find((option) => option.label === label)?.id ?? label
  )
  return question.type === 'multi_choice' ? ids : (ids[0] ?? '')
}

function QuizQuestionList({
  questions,
  disabled,
  onSubmit,
}: {
  questions: PublicQuizQuestion[]
  disabled: boolean
  onSubmit: (answers: string[]) => void
}) {
  const [answers, setAnswers] = useState<string[]>(() => questions.map(() => ''))

  const setAnswer = (index: number, value: string, multi: boolean) => {
    setAnswers((current) => {
      const next = [...current]
      if (!multi) {
        next[index] = value
        return next
      }
      const selected = next[index] ? next[index].split(' · ') : []
      next[index] = selected.includes(value)
        ? selected.filter((item) => item !== value).join(' · ')
        : [...selected, value].join(' · ')
      return next
    })
  }

  return (
    <div className='space-y-4'>
      {questions.map((question, index) => {
        const selected = answers[index]?.split(' · ').filter(Boolean) ?? []
        return (
          <section
            key={question.id}
            className='rounded-2xl border border-[var(--border-1)] bg-[var(--surface-2)] p-4'
          >
            <div className='flex items-start justify-between gap-4'>
              <h3 className='font-medium text-[var(--text-primary)] text-sm'>
                {index + 1}. {question.prompt}
              </h3>
              <span className='shrink-0 text-[var(--text-muted)] text-xs'>
                {question.points} 分
              </span>
            </div>
            {question.type === 'short_text' ? (
              <input
                className='mt-3 w-full rounded-xl border border-[var(--border-1)] bg-[var(--surface-1)] px-3 py-2 text-[var(--text-body)] text-sm outline-none focus:border-[var(--text-primary)]'
                value={answers[index] ?? ''}
                disabled={disabled}
                onChange={(event) => setAnswer(index, event.target.value, false)}
                placeholder='输入你的答案'
              />
            ) : (
              <div className='relative z-10 mt-3 space-y-2 pointer-events-auto'>
                {question.options.map((option) => {
                  const checked = selected.includes(option.label)
                  return (
                    <button
                      key={option.id}
                      type='button'
                      disabled={disabled}
                      aria-pressed={checked}
                      onClick={() =>
                        setAnswer(index, option.label, question.type === 'multi_choice')
                      }
                      className={`pointer-events-auto flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left text-sm transition-colors ${
                        checked
                          ? 'border-[var(--text-primary)] bg-[var(--surface-4)] text-[var(--text-primary)]'
                          : 'border-[var(--border-1)] bg-[var(--surface-1)] text-[var(--text-body)] hover:bg-[var(--surface-4)]'
                      }`}
                    >
                      <span
                        aria-hidden='true'
                        className={`flex size-4 shrink-0 items-center justify-center border text-[10px] ${
                          question.type === 'multi_choice' ? 'rounded-[4px]' : 'rounded-full'
                        } ${
                          checked
                            ? 'border-[var(--text-primary)] bg-[var(--text-primary)] text-[var(--text-inverse)]'
                            : 'border-[var(--border-1)]'
                        }`}
                      >
                        {checked ? '✓' : ''}
                      </span>
                      <span className='min-w-0 flex-1'>{option.label}</span>
                    </button>
                  )
                })}
              </div>
            )}
          </section>
        )
      })}
      <Button
        className='w-full'
        variant='primary'
        disabled={disabled || answers.some((answer) => !answer.trim())}
        onClick={() => onSubmit(answers)}
      >
        提交检测
      </Button>
    </div>
  )
}

export function LingxiArtifactResource({ resourceId }: LingxiArtifactResourceProps) {
  const parsed = useMemo(() => parseResourceId(resourceId), [resourceId])
  if (parsed && 'workspaceKind' in parsed) return <WorkspaceResource kind={parsed.workspaceKind} />
  return <LingxiTaskArtifactResource parsed={parsed} />
}

function LingxiTaskArtifactResource({ parsed }: { parsed: ParsedTaskResource | null }) {
  const { task, loading, error, refresh } = useAgentTask(parsed?.taskId ?? '')
  const [submittedAnswers, setSubmittedAnswers] = useState<string[] | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [artifactUrl, setArtifactUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!parsed || parsed.kind === 'quiz') return
    let disposed = false
    let objectUrl: string | null = null
    void api
      .fetchArtifact(api.agentArtifactUrl(parsed.taskId, parsed.kind))
      .then((blob) => {
        if (disposed) return
        objectUrl = URL.createObjectURL(blob)
        setArtifactUrl(objectUrl)
      })
      .catch(() => setArtifactUrl(null))
    return () => {
      disposed = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
      setArtifactUrl(null)
    }
  }, [parsed])

  const submitQuiz = useCallback(
    async (answers: string[]) => {
      if (!parsed || parsed.kind !== 'quiz' || !task?.artifacts.quiz.data) return

      setSubmitting(true)
      setSubmitError(null)
      try {
        const quiz = task.artifacts.quiz.data
        const normalizedAnswers = Object.fromEntries(
          quiz.questions.map((question, index) => [
            question.id,
            normalizeAnswer(question, answers[index] ?? ''),
          ])
        )
        await api.submitAgentQuiz(parsed.taskId, crypto.randomUUID(), normalizedAnswers)
        await api.ackAgentDelivery(parsed.taskId, 'quiz')
        setSubmittedAnswers(answers)
        await refresh()
      } catch (cause) {
        setSubmitError(cause instanceof Error ? cause.message : String(cause))
      } finally {
        setSubmitting(false)
      }
    },
    [parsed, refresh, task]
  )

  if (!parsed) return <div className='p-6 text-[var(--text-secondary)] text-sm'>产物地址无效。</div>

  if (parsed.kind !== 'quiz') {
    if (!artifactUrl)
      return <div className='p-6 text-[var(--text-secondary)] text-sm'>正在加载学习产物…</div>
    return (
      <div className='flex h-full flex-col'>
        <iframe
          className='min-h-0 flex-1 w-full border-0 bg-white'
          src={artifactUrl}
          title='LingxiGraph 学习产物'
          sandbox='allow-scripts allow-same-origin allow-forms allow-popups'
        />
        {task?.delivery.queue.some((item) => item.artifact === parsed.kind && item.state === 'unlocked') && (
          <Button
            className='m-3'
            variant='primary'
            onClick={() => void api.ackAgentDelivery(parsed.taskId, parsed.kind).then(() => refresh())}
          >
            继续下一步
          </Button>
        )}
      </div>
    )
  }

  if (loading && !task) {
    return <div className='p-6 text-[var(--text-secondary)] text-sm'>正在加载知识点检测…</div>
  }
  if (error || !task?.artifacts.quiz.data) {
    return (
      <div className='flex h-full flex-col items-center justify-center gap-3 p-6 text-center'>
        <p className='text-[var(--text-secondary)] text-sm'>{error || '检测题尚未生成。'}</p>
        <Button variant='outline' onClick={() => void refresh()}>
          重新加载
        </Button>
      </div>
    )
  }

  const quiz = task.artifacts.quiz.data
  return (
    <div className='h-full overflow-y-auto bg-[var(--surface-1)] p-5 sm:p-7'>
      <div className='mx-auto max-w-2xl'>
        <div className='mb-5'>
          <p className='font-medium text-[var(--text-primary)]'>{quiz.title}</p>
          <p className='mt-1 text-[var(--text-muted)] text-sm'>{quiz.instructions}</p>
        </div>
        <QuizQuestionList
          questions={quiz.questions}
          disabled={Boolean(task.quiz_submission || submittedAnswers || submitting)}
          onSubmit={(answers) => void submitQuiz(answers)}
        />
        {task.quiz_submission && (
          <p className='mt-4 text-[var(--text-secondary)] text-sm'>
            得分：{task.quiz_submission.total_score} / {task.quiz_submission.total_points}
          </p>
        )}
        {submitting && <p className='mt-4 text-[var(--text-secondary)] text-sm'>正在提交…</p>}
        {submitError && <p className='mt-4 text-[var(--text-error)] text-sm'>{submitError}</p>}
      </div>
    </div>
  )
}
