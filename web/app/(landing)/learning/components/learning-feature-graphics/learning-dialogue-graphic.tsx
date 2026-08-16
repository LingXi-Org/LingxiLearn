import { cn } from '@/components/ui-kit'
import { BookOpen } from '@/components/ui-kit/icons'
import { FeatureGraphicShell } from '@/app/(landing)/enterprise/components/feature-graphics/feature-graphic-shell'
import styles from './learning-dialogue-graphic.module.css'

interface LearningDialogueGraphicProps {
  question: string
  answer: string
  sourceLabel: string
  sourceDetail?: string
}

export function LearningDialogueGraphic({
  question,
  answer,
  sourceLabel,
  sourceDetail = '来自 LingXi 学习依据',
}: LearningDialogueGraphicProps) {
  return (
    <FeatureGraphicShell>
      <div
        aria-hidden='true'
        className='absolute inset-0 flex items-center justify-center pr-8 max-lg:pr-6'
      >
        <div className='flex w-full max-w-[312px] flex-col gap-3 sm:max-lg:[@container(min-width:500px)]:max-w-[400px]'>
          <div
            className={cn(
              'max-w-[85%] self-end rounded-lg border border-[var(--border-1)] bg-[var(--white)] px-3 py-2 text-[var(--text-primary)] text-caption leading-[1.5]',
              styles.stepQuestion
            )}
          >
            {question}
          </div>
          <p
            className={cn(
              'text-[var(--text-primary)] text-caption leading-[1.6]',
              styles.stepAnswer
            )}
          >
            {answer}
          </p>
          <div
            className={cn(
              'flex items-center gap-2.5 rounded-xl border border-[var(--border-1)] bg-[var(--white)] px-3 py-2.5 shadow-sm',
              styles.stepSource
            )}
          >
            <span
              className={cn(
                'flex size-6 shrink-0 items-center justify-center rounded-md border border-[var(--border-1)]',
                styles.sourcePulse
              )}
            >
              <BookOpen className='size-[14px] text-[var(--text-icon)]' />
            </span>
            <span className='min-w-0 flex-1'>
              <span className='block truncate font-medium text-[var(--text-primary)] text-small'>
                {sourceLabel}
              </span>
              <span className='block truncate text-[var(--text-muted)] text-caption'>
                {sourceDetail}
              </span>
            </span>
          </div>
        </div>
      </div>
    </FeatureGraphicShell>
  )
}
