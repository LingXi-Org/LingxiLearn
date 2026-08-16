import { ChipTag, cn } from '@/components/ui-kit'
import { Clock } from '@/components/ui-kit/icons'
import { FeatureGraphicShell } from '@/app/(landing)/enterprise/components/feature-graphics/feature-graphic-shell'
import styles from './learning-path-graphic.module.css'

export interface LearningPathStep {
  label: string
  title: string
  detail: string
  state?: 'current' | 'next' | 'past'
}

interface LearningPathGraphicProps {
  title: string
  statusLabel?: string
  steps: readonly LearningPathStep[]
}

export function LearningPathGraphic({
  title,
  statusLabel = '进行中',
  steps,
}: LearningPathGraphicProps) {
  return (
    <FeatureGraphicShell>
      <div
        aria-hidden='true'
        className='absolute top-5 right-0 bottom-0 left-0 rounded-tl-xl border-[var(--border-1)] border-t border-l'
      >
        <div className='flex h-12 items-center gap-2 border-[var(--border-1)] border-b px-4'>
          <span className='flex size-6 items-center justify-center rounded-md border border-[var(--border-1)]'>
            <Clock className='size-[14px] text-[var(--text-icon)]' />
          </span>
          <span className='min-w-0 flex-1 truncate font-medium text-[var(--text-primary)] text-base'>
            {title}
          </span>
          <ChipTag variant='mono' className='shrink-0 bg-[var(--surface-6)]'>
            {statusLabel}
          </ChipTag>
        </div>

        <div className='flex flex-col p-4 [mask-image:linear-gradient(to_bottom,black_45%,transparent_98%)]'>
          {steps.map((step, index) => {
            const state = step.state ?? (index === 0 ? 'current' : index === 1 ? 'next' : 'past')

            return (
              <div key={`${step.label}-${step.title}`} className='flex flex-col'>
                {index > 0 ? (
                  <div className='flex gap-3'>
                    <span className='flex w-2.5 justify-center'>
                      <span className='h-7 w-px bg-[color:color-mix(in_srgb,var(--text-muted)_35%,transparent)]' />
                    </span>
                  </div>
                ) : null}
                <div className='flex items-center gap-3'>
                  <span className='flex w-2.5 justify-center'>
                    <span
                      className={cn(
                        'size-2 rounded-full border bg-[var(--surface-3)]',
                        state === 'current'
                          ? cn(
                              'border-[var(--text-primary)] bg-[var(--text-primary)]',
                              styles.livePulse
                            )
                          : state === 'next'
                            ? 'border-[var(--text-muted)]'
                            : 'border-[color:color-mix(in_srgb,var(--text-muted)_60%,transparent)]'
                      )}
                    />
                  </span>
                  <span className='flex min-w-0 flex-1 flex-col gap-1'>
                    <span className='flex items-center gap-2'>
                      <span
                        className={cn(
                          'truncate font-medium text-small',
                          state === 'current'
                            ? 'text-[var(--text-primary)]'
                            : state === 'next'
                              ? 'text-[var(--text-secondary)]'
                              : 'text-[var(--text-muted)]'
                        )}
                      >
                        {step.label}　{step.title}
                      </span>
                      {state === 'current' ? <ChipTag variant='solid'>当前</ChipTag> : null}
                      {state === 'next' ? (
                        <ChipTag variant='mono' className='bg-[var(--surface-6)]'>
                          下一步
                        </ChipTag>
                      ) : null}
                    </span>
                    <span className='truncate text-[var(--text-muted)] text-caption'>
                      {step.detail}
                    </span>
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </FeatureGraphicShell>
  )
}
