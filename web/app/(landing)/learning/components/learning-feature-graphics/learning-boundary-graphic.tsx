import { ChipTag } from '@/components/ui-kit'
import { ShieldCheck } from '@/components/ui-kit/icons'
import { FeatureGraphicShell } from '@/app/(landing)/enterprise/components/feature-graphics/feature-graphic-shell'
import styles from './learning-boundary-graphic.module.css'

interface LearningBoundaryGraphicProps {
  title: string
  leftLabel: string
  rightLabel: string
  sealLabel: string
}

export function LearningBoundaryGraphic({
  title,
  leftLabel,
  rightLabel,
  sealLabel,
}: LearningBoundaryGraphicProps) {
  return (
    <FeatureGraphicShell>
      <div aria-hidden='true' className='absolute inset-0 pr-8 max-lg:pr-6'>
        <div className='absolute top-4 left-4 font-medium text-[var(--text-primary)] text-small'>
          {title}
        </div>
        <div className='relative mx-auto mt-4 h-[250px] w-[320px] max-w-full'>
          <div className='absolute top-[34px] left-[48px] size-[224px] rounded-full border border-[var(--border-1)] [mask-image:linear-gradient(to_bottom,black_30%,transparent_92%)]' />
          <div className='absolute top-[70px] left-[84px] size-[152px] rounded-full border border-[color:color-mix(in_srgb,var(--text-muted)_45%,transparent)]' />
          <svg
            className='absolute inset-0'
            fill='none'
            viewBox='0 0 320 250'
            width={320}
            height={250}
          >
            <path
              d='M 90 146.5 L 122 146.5'
              pathLength={1}
              stroke='color-mix(in srgb, var(--text-muted) 45%, transparent)'
              strokeWidth='1'
            />
            <path
              d='M 198 146.5 L 230 146.5'
              pathLength={1}
              stroke='color-mix(in srgb, var(--text-muted) 45%, transparent)'
              strokeWidth='1'
            />
          </svg>
          <span className='absolute top-[142px] left-[118px] size-2 rounded-full border border-[var(--text-muted)] bg-[var(--surface-3)]' />
          <span className='absolute top-[142px] left-[194px] size-2 rounded-full border border-[var(--text-muted)] bg-[var(--surface-3)]' />
          <div
            className={`absolute top-[108px] left-[122px] flex size-[76px] items-center justify-center rounded-full bg-[var(--text-primary)] shadow-sm ${styles.sealPulse}`}
          >
            <ShieldCheck className='size-7 text-[var(--text-inverse)]' />
          </div>
          <span className='-translate-x-full -translate-y-1/2 absolute top-[146px] left-[90px] whitespace-nowrap'>
            <ChipTag variant='mono'>{leftLabel}</ChipTag>
          </span>
          <span className='-translate-y-1/2 absolute top-[146px] left-[230px] whitespace-nowrap'>
            <ChipTag variant='mono'>{rightLabel}</ChipTag>
          </span>
          <span className='-translate-x-1/2 absolute top-[206px] left-1/2 flex h-5 items-center rounded-md bg-[var(--text-primary)] px-1.5 font-medium text-[var(--text-inverse)] text-caption'>
            {sealLabel}
          </span>
        </div>
      </div>
    </FeatureGraphicShell>
  )
}
