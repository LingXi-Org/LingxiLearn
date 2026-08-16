import { Button, ChipTag, cn } from '@/components/ui-kit'
import { ArrowRight, CircleCheck } from '@/components/ui-kit/icons'
import { FeatureGraphicShell } from '@/app/(landing)/enterprise/components/feature-graphics/feature-graphic-shell'
import styles from './learning-transition-graphic.module.css'

interface LearningTransitionGraphicProps {
  title: string
  headerTag: string
  changeTag: string
  changeTitle: string
  checks: readonly [string, string, string]
  fromLabel: string
  toLabel: string
  actionLabel: string
}

export function LearningTransitionGraphic({
  title,
  headerTag,
  changeTag,
  changeTitle,
  checks,
  fromLabel,
  toLabel,
  actionLabel,
}: LearningTransitionGraphicProps) {
  return (
    <FeatureGraphicShell>
      <div
        aria-hidden='true'
        className='absolute inset-0 flex items-center justify-center pr-8 pb-8 max-lg:pr-6 max-lg:pb-6'
      >
        <div className='w-full max-w-[312px] rounded-xl border border-[var(--border-1)]'>
          <div className='flex h-10 items-center gap-2 border-[var(--border-1)] border-b px-4'>
            <span className='min-w-0 flex-1 truncate font-medium text-[var(--text-primary)] text-base'>
              {title}
            </span>
            <ChipTag variant='mono' className='bg-[var(--surface-6)]'>
              {headerTag}
            </ChipTag>
          </div>

          <div className='px-3 py-2.5'>
            <div className='rounded-lg border border-[var(--border-1)] bg-[var(--white)] px-3 py-2.5 shadow-sm'>
              <span className='flex items-center gap-2'>
                <ChipTag variant='mono'>{changeTag}</ChipTag>
                <span className='min-w-0 truncate font-medium text-[var(--text-primary)] text-small'>
                  {changeTitle}
                </span>
              </span>
            </div>
          </div>

          <div className='flex flex-col gap-2 border-[var(--border-1)] border-t px-4 py-2.5'>
            {checks.map((check) => (
              <span key={check} className='flex items-center gap-2'>
                <CircleCheck className='size-[13px] text-[var(--text-icon)]' />
                <span className='text-[var(--text-secondary)] text-caption'>{check}</span>
              </span>
            ))}
          </div>

          <div className='flex items-center justify-between gap-3 border-[var(--border-1)] border-t px-4 py-2.5'>
            <span className='hidden min-w-0 items-center gap-1.5 xl:flex'>
              <ChipTag variant='mono' className='bg-[var(--surface-6)]'>
                {fromLabel}
              </ChipTag>
              <ArrowRight className='size-[12px] shrink-0 text-[var(--text-icon)]' />
              <ChipTag variant='mono' className='bg-[var(--surface-6)]'>
                {toLabel}
              </ChipTag>
            </span>
            <Button
              variant='primary'
              size='sm'
              tabIndex={-1}
              className={cn('pointer-events-none ml-auto', styles.actionPulse)}
            >
              {actionLabel}
            </Button>
          </div>
        </div>
      </div>
    </FeatureGraphicShell>
  )
}
