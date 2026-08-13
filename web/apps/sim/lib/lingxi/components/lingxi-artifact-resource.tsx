'use client'

import { useCallback, useMemo, useState } from 'react'
import { Button } from '@sim/emcn'
import { api } from '@/lib/lingxi/api'
import { LingxiWorkflow } from '@/lib/lingxi/components/lingxi-workflow'
import { useAgentArtifact } from '@/lib/lingxi/hooks/use-agent-artifact'
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
  const fileKind = parsed?.kind === 'lesson-intro' || parsed?.kind === 'lecture-deck' || parsed?.kind === 'visual'
    ? parsed.kind
    : 'lesson-intro'
  const artifactAvailable = Boolean(
    parsed && parsed.kind !== 'quiz' && parsed.kind !== 'knowledge-graph' &&
      task?.artifacts[
        parsed.kind === 'lesson-intro'
          ? 'lesson_intro'
          : parsed.kind === 'lecture-deck'
            ? 'lecture_deck'
            : 'visual'
      ]?.available,
  )
  const artifact = useAgentArtifact(
    parsed?.taskId,
    fileKind,
    artifactAvailable,
    task?.updated_at,
  )
  const [submittedAnswers, setSubmittedAnswers] = useState<string[]>()
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

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
    return <LingxiWorkflow taskId={parsed.taskId} />
  }

  if (parsed.kind !== 'quiz') {
    if (loading && !task) {
      return <div className='p-6 text-[var(--text-secondary)] text-sm'>正在加载学习产物…</div>
    }
    if (error) {
      return (
        <div className='flex h-full flex-col items-center justify-center gap-3 p-6 text-center'>
          <p className='text-[var(--text-secondary)] text-sm'>{error}</p>
          <Button variant='outline' onClick={() => void refresh()}>重新加载</Button>
        </div>
      )
    }
    if (!artifactAvailable) {
      return (
        <div className='flex h-full flex-col items-center justify-center gap-3 p-6 text-center'>
          <p className='text-[var(--text-secondary)] text-sm'>产物正在生成，请稍候。</p>
          <Button variant='outline' onClick={() => void refresh()}>刷新状态</Button>
        </div>
      )
    }
    if (artifact.loading && !artifact.content) {
      return <div className='p-6 text-[var(--text-secondary)] text-sm'>正在打开学习产物…</div>
    }
    if (artifact.error || !artifact.content) {
      return (
        <div className='flex h-full flex-col items-center justify-center gap-3 p-6 text-center'>
          <p className='text-[var(--text-secondary)] text-sm'>{artifact.error || '产物暂时无法打开。'}</p>
          <Button variant='outline' onClick={() => void refresh()}>重新加载</Button>
        </div>
      )
    }
    return (
      <iframe
        key={artifact.content}
        src={artifact.content}
        title={`${parsed.kind} 学习产物`}
        className='block h-full min-h-0 w-full border-0'
        sandbox='allow-scripts'
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
