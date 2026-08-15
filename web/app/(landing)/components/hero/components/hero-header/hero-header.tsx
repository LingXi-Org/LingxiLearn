import type { ReactNode } from 'react'
import { cn } from '@/components/ui-kit'
import { HeroStat } from '@/app/(landing)/components/hero/components/hero-stat'
import { HeroCta } from '@/app/(landing)/components/hero-cta'
import { LANDING_HERO_CTA_GAP } from '@/app/(landing)/components/landing-layout'

interface LandingHeroHeaderProps {
  description: string
  eyebrow?: ReactNode
  heading: ReactNode
  headingId: string
  showStat?: boolean
  statValue?: string
  statLabel?: string
  statProgressClassName?: string
}

/**
 * Shared homepage hero header geometry. Marketing routes use this component so
 * the headline measure and CTA stack cannot drift. The optional stat remains
 * available to platform/solution pages while the homepage can omit it.
 */
export function LandingHeroHeader({
  description,
  eyebrow,
  heading,
  headingId,
  showStat = true,
  statValue,
  statLabel,
  statProgressClassName,
}: LandingHeroHeaderProps) {
  return (
    <div className='flex w-full items-end gap-8'>
      <div className='flex min-w-0 flex-1 flex-col items-start gap-[22px] text-left'>
        {eyebrow}

        <h1
          id={headingId}
          className='max-w-[1120px] text-balance text-[64px] text-[var(--text-primary)] leading-[1.05] tracking-[-0.01em] max-sm:text-[36px] max-xl:text-[52px] [&>br]:max-sm:hidden'
        >
          {heading}
        </h1>

        <p className='w-full min-w-0 max-w-[58ch] text-pretty text-[var(--text-muted)] text-base leading-[1.5]'>
          {description}
        </p>

        <div className={cn('max-sm:w-full', LANDING_HERO_CTA_GAP)}>
          <HeroCta />
        </div>
      </div>
      {showStat ? (
        <HeroStat
          value={statValue}
          label={statLabel}
          progressClassName={statProgressClassName}
        />
      ) : null}
    </div>
  )
}
