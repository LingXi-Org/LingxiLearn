import { cn } from '@/components/ui-kit'
import { CircleAlert } from '@/components/ui-kit/icons'
import { FeatureGraphicShell } from '@/app/(landing)/enterprise/components/feature-graphics/feature-graphic-shell'
import styles from './learning-feedback-graphic.module.css'

const OUTLINE_INK = 'border-[var(--border-1)]'

export interface LearningFeedbackRow {
  label: string
  detail?: string
}

interface LearningFeedbackGraphicProps {
  title: string
  rows: readonly LearningFeedbackRow[]
  action?: string
}

export function LearningFeedbackGraphic({
  title,
  rows,
  action = '继续判断',
}: LearningFeedbackGraphicProps) {
  return (
    <FeatureGraphicShell>
      <div
        aria-hidden='true'
        className='absolute inset-0 flex flex-col items-center pr-8 max-lg:pr-6'
      >
        <div
          className={cn(
            'mt-1 flex items-center gap-2 rounded-[10px] border bg-[var(--surface-1)] py-1.5 pr-1.5 pl-2.5',
            OUTLINE_INK,
            styles.runRow
          )}
        >
          <CircleAlert className='size-[13px] text-[var(--text-primary)]' />
          <span className='font-medium text-[var(--text-primary)] text-caption'>{title}</span>
          <span
            className={cn(
              'flex h-5 items-center rounded-md border px-1.5 font-medium text-[var(--text-muted)] text-caption',
              OUTLINE_INK
            )}
          >
            已分析
          </span>
        </div>

        <span
          className={cn(
            'relative mt-2 mb-2 min-h-4 w-px flex-1 overflow-hidden bg-[var(--border-1)]'
          )}
        >
          <span className={styles.sweep} />
        </span>

        <div
          className={cn(
            'relative w-full rounded-t-xl border border-b-0 bg-[var(--surface-1)]',
            OUTLINE_INK,
            styles.alertWindow
          )}
        >
          <div className={cn('flex h-11 items-center gap-2 border-b px-3', OUTLINE_INK)}>
            <span
              className={cn(
                'flex size-6 items-center justify-center rounded-md border',
                OUTLINE_INK
              )}
            >
              <span className='size-2 rounded-full bg-[var(--text-primary)]' />
            </span>
            <span className='min-w-0 flex-1 truncate font-medium text-[var(--text-primary)] text-small'>
              反馈判断
            </span>
            <span className='shrink-0 text-[var(--text-muted)] text-caption'>现在</span>
          </div>
          <div className='flex flex-col gap-2 px-3 pt-2.5 pb-3'>
            {rows.map((row, index) => (
              <div key={row.label} className='flex items-start gap-2'>
                <span className='mt-1 flex size-4 shrink-0 items-center justify-center rounded-full border border-[var(--border-1)] text-[10px] text-[var(--text-muted)]'>
                  {index + 1}
                </span>
                <span className='min-w-0 flex-1'>
                  <span className='block font-medium text-[var(--text-primary)] text-caption'>
                    {row.label}
                  </span>
                  {row.detail ? (
                    <span className='mt-0.5 block text-[var(--text-muted)] text-caption'>
                      {row.detail}
                    </span>
                  ) : null}
                </span>
              </div>
            ))}
            <span className='mt-1 rounded-md border border-[var(--border-1)] px-2 py-1.5 text-center font-medium text-[var(--text-primary)] text-caption'>
              {action}
            </span>
          </div>
        </div>
      </div>
    </FeatureGraphicShell>
  )
}
