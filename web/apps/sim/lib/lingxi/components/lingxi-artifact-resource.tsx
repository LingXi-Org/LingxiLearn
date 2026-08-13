'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Button } from '@sim/emcn'
import { api } from '@/lib/lingxi/api'
import { KnowledgeGraphCanvas } from '@/lib/lingxi/components/knowledge-graph-canvas'
import { useAgentTask } from '@/lib/lingxi/hooks/use-agent-task'
import type { PublicQuizQuestion } from '@/lib/lingxi/types'
import { QuestionDisplay } from '@/app/workspace/[workspaceId]/home/components/message-content/components/question'
import type { QuestionItem } from '@/app/workspace/[workspaceId]/home/components/message-content/components/special-tags'

interface LingxiArtifactResourceProps {
  resourceId: string
}

type ArtifactKind = 'lesson-intro' | 'lecture-deck' | 'quiz' | 'visual' | 'knowledge-graph'

function parseResourceId(resourceId: string) {
  const [, taskId, kind] = resourceId.split(':')
  if (!taskId || !kind) return null
  if (!['lesson-intro', 'lecture-deck', 'quiz', 'visual', 'knowledge-graph'].includes(kind))
    return null
  return { taskId, kind: kind as ArtifactKind }
}

function toQuestionItem(question: PublicQuizQuestion): QuestionItem {
  return {
    type: question.type === 'multi_choice' ? 'multi_select' : 'single_select',
    prompt: question.prompt,
    options: question.options,
  }
}

function normalizeQuizAnswer(question: PublicQuizQuestion, answer: string): string | string[] {
  if (question.type === 'short_text') return answer

  const labels = question.type === 'multi_choice' ? answer.split(', ').filter(Boolean) : [answer]
  const ids = labels.map(
    (label) => question.options.find((option) => option.label === label)?.id ?? label
  )
  return question.type === 'multi_choice' ? ids : (ids[0] ?? '')
}

export function LingxiArtifactResource({ resourceId }: LingxiArtifactResourceProps) {
  const parsed = useMemo(() => parseResourceId(resourceId), [resourceId])
  const { task, loading, error, refresh } = useAgentTask(parsed?.taskId ?? '')
  const [submittedAnswers, setSubmittedAnswers] = useState<string[]>()
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [graph, setGraph] = useState<import('@/lib/lingxi/types').KnowledgeGraphData | null>(null)
  const [graphLoading, setGraphLoading] = useState(false)

  useEffect(() => {
    if (parsed?.kind !== 'knowledge-graph') return
    setGraphLoading(true)
    void api
      .agentKnowledgeGraph(parsed.taskId)
      .then(setGraph)
      .catch(() => setGraph(null))
      .finally(() => setGraphLoading(false))
  }, [parsed, task?.artifacts.knowledge_graph?.revision])

  useEffect(() => {
    if (parsed?.kind !== 'knowledge-graph' || task?.artifacts.knowledge_graph?.available) return
    if (task?.artifacts.knowledge_graph?.status === 'failed') return
    const timer = setInterval(() => {
      void api
        .agentKnowledgeGraph(parsed.taskId)
        .then(setGraph)
        .catch(() => {})
    }, 1800)
    return () => clearInterval(timer)
  }, [parsed, task?.artifacts.knowledge_graph?.available, task?.artifacts.knowledge_graph?.status])

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
            normalizeQuizAnswer(question, answers[index] ?? ''),
          ])
        )
        await api.submitAgentQuiz(parsed.taskId, crypto.randomUUID(), normalizedAnswers)
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

  if (parsed.kind === 'knowledge-graph') {
    if (graphLoading)
      return (
        <div className='p-6 text-[var(--text-secondary)] text-sm'>正在加载 Lingxi 知识图谱…</div>
      )
    if (!graph && task?.artifacts.knowledge_graph?.status === 'failed')
      return (
        <div className='flex h-full flex-col items-center justify-center gap-3 p-6 text-center'>
          <p className='text-[var(--text-secondary)] text-sm'>
            知识图谱后台生成失败，本次聊天和已有图谱不受影响。
          </p>
          <Button variant='outline' onClick={() => void refresh()}>
            重新加载任务
          </Button>
        </div>
      )
    if (!graph)
      return (
        <div className='flex h-full flex-col items-center justify-center gap-2 p-6 text-center'>
          <p className='text-[var(--text-secondary)] text-sm'>
            图谱正在后台生成，完成后会自动出现。
          </p>
          <p className='text-[var(--text-muted)] text-xs'>当前聊天可继续接收输入。</p>
        </div>
      )
    return <KnowledgeGraphCanvas graph={graph} />
  }

  if (parsed.kind !== 'quiz') {
    return (
      <iframe
        className='h-full w-full border-0 bg-white'
        src={api.agentArtifactUrl(parsed.taskId, parsed.kind)}
        title='LingxiGraph 学习产物'
        sandbox='allow-scripts allow-same-origin allow-forms allow-popups'
      />
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
  const questions = quiz.questions.map(toQuestionItem)
  const canSubmit = !task.quiz_submission && !submittedAnswers

  return (
    <div className='h-full overflow-y-auto bg-[var(--surface-1)] p-5 sm:p-7'>
      <div className='mx-auto max-w-2xl'>
        <QuestionDisplay
          data={questions}
          answers={submittedAnswers}
          onAnswersSubmit={canSubmit ? (answers) => void submitQuiz(answers) : undefined}
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
