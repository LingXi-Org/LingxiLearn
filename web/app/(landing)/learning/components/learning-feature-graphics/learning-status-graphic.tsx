import { ChipTag, cn } from '@/components/ui-kit'
import { FeatureGraphicShell } from '@/app/(landing)/enterprise/components/feature-graphics/feature-graphic-shell'
import styles from './learning-status-graphic.module.css'

export interface LearningStatusField {
  label: string
  value: string
  variant?: 'strong' | 'chip' | 'mono'
}

interface LearningStatusGraphicProps {
  title: string
  statusLabel?: string
  fields: readonly LearningStatusField[]
  outputLabel?: string
  output?: string
}

function fieldValue(field: LearningStatusField) {
  if (field.variant === 'chip') {
    return (
      <ChipTag variant='mono' className='bg-[var(--surface-6)]'>
        {field.value}
      </ChipTag>
    )
  }
  if (field.variant === 'mono') {
    return (
      <span className='font-mono text-[var(--text-secondary)] text-caption'>{field.value}</span>
    )
  }
  return (
    <span className='truncate font-medium text-[var(--text-primary)] text-caption'>
      {field.value}
    </span>
  )
}

export function LearningStatusGraphic({
  title,
  statusLabel = '实时更新',
  fields,
  outputLabel = '下一步建议',
  output = '根据当前状态继续学习',
}: LearningStatusGraphicProps) {
  return (
    <FeatureGraphicShell>
      <div
        aria-hidden='true'
        className='absolute inset-0 flex items-center justify-center pr-8 max-lg:pr-6'
      >
        <div className='w-full max-w-[312px] sm:max-lg:[@container(min-width:500px)]:max-w-[400px]'>
          <div className='mb-1.5 flex items-center justify-between gap-2'>
            <span className='min-w-0 truncate font-medium text-[var(--text-primary)] text-base'>
              {title}
            </span>
            <span className='flex shrink-0 items-center gap-1.5'>
              <span
                className={cn('size-2 rounded-full bg-[var(--text-primary)]', styles.livePulse)}
              />
              <span className='text-[var(--text-muted)] text-caption'>{statusLabel}</span>
            </span>
          </div>

          {fields.map((field, index) => (
            <div
              key={field.label}
              className={cn(
                'flex h-9 items-center justify-between gap-3',
                index > 0 && 'border-[var(--border-1)] border-t'
              )}
            >
              <span className='shrink-0 text-[var(--text-muted)] text-caption'>{field.label}</span>
              {fieldValue(field)}
            </div>
          ))}

          <div className='mt-2'>
            <span className='block text-[var(--text-muted)] text-caption'>{outputLabel}</span>
            <div className='mt-1.5 rounded-xl border border-[var(--border-1)] bg-[var(--white)] px-3 py-2.5 shadow-sm'>
              <span className='block truncate font-medium text-[var(--text-primary)] text-caption'>
                {output}
              </span>
            </div>
          </div>
        </div>
      </div>
    </FeatureGraphicShell>
  )
}
