import { ChipTag, cn } from '@/components/ui-kit'
import { FileText } from '@/components/ui-kit/icons'
import { FeatureGraphicShell } from '@/app/(landing)/enterprise/components/feature-graphics/feature-graphic-shell'
import styles from './learning-evidence-graphic.module.css'

export interface LearningEvidenceEntry {
  label: string
  detail: string
  time?: string
}

interface LearningEvidenceGraphicProps {
  title: string
  entries: readonly LearningEvidenceEntry[]
  statusLabel?: string
}

export function LearningEvidenceGraphic({
  title,
  entries,
  statusLabel = '可回看',
}: LearningEvidenceGraphicProps) {
  return (
    <FeatureGraphicShell>
      <div
        aria-hidden='true'
        className='absolute inset-0 flex items-center justify-center pr-8 max-lg:pr-6'
      >
        <div className='w-full max-w-[312px] sm:max-lg:[@container(min-width:500px)]:max-w-[400px]'>
          <div className='mb-4 flex items-center justify-between'>
            <span className='font-medium text-[var(--text-primary)] text-base'>{title}</span>
            <ChipTag variant='mono' className='bg-[var(--surface-6)]'>
              {statusLabel}
            </ChipTag>
          </div>

          <div className='flex flex-col gap-1.5 [mask-image:linear-gradient(to_bottom,black_55%,transparent_100%)]'>
            {entries.map((entry, index) => {
              const newest = index === 0
              return (
                <div
                  key={`${entry.label}-${entry.detail}`}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5',
                    newest &&
                      cn(
                        'rounded-xl border border-[var(--border-1)] bg-[var(--white)] shadow-sm',
                        styles.stampIn
                      )
                  )}
                >
                  <span
                    className={cn(
                      'flex size-7 shrink-0 items-center justify-center rounded-full border border-[var(--border-1)] bg-[var(--surface-2)] text-[var(--text-muted)]',
                      newest &&
                        cn('bg-[var(--surface-1)] text-[var(--text-primary)]', styles.sealPulse)
                    )}
                  >
                    <FileText className='size-[13px]' />
                  </span>
                  <span className='min-w-0 flex-1'>
                    <span
                      className={cn(
                        'block truncate font-medium text-small',
                        newest ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'
                      )}
                    >
                      {entry.label}
                    </span>
                    <span className='block truncate text-[var(--text-muted)] text-caption'>
                      {entry.detail}
                    </span>
                  </span>
                  {entry.time ? (
                    <span className='shrink-0 self-start pt-px text-[var(--text-muted)] text-caption'>
                      {entry.time}
                    </span>
                  ) : null}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </FeatureGraphicShell>
  )
}
