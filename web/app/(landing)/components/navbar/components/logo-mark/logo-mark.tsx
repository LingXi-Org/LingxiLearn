'use client'

import { type CSSProperties, type ReactNode, useState } from 'react'
import { LingxiLogoMorph } from '@/components/ui'
import { cn } from '@/components/ui-kit'

interface LogoMarkProps {
  /** Server-rendered Sim wordmark, shown by default. */
  children: ReactNode
}

/** Keep the animated arc ink aligned with the resting wordmark. */
const MORPH_INK = {
  '--llm-ink': 'var(--text-body)',
} as CSSProperties

/**
 * Navbar logo with a hover easter egg: the static mark hands off to three
 * phase-shifted arc trails that accelerate around the center, then decelerate
 * and restore the production logo. The server-rendered wordmark remains the
 * resting state; the animated SVG is mounted only while the shell is active.
 */
export function LogoMark({ children }: LogoMarkProps) {
  const [hovered, setHovered] = useState(false)

  return (
    <span
      className='relative inline-flex items-center'
      // Transform + its transition are inline on purpose: Tailwind's
      // `transition-transform` utility (its var-based transform composition)
      // prevents the scale from applying on this element, so the transition is
      // declared directly. This is the sanctioned dynamic, state-driven-value
      // exception - do not move it back to a `transition-transform`/`scale-*`
      // class.
      style={{
        transition: 'transform 150ms cubic-bezier(0.23, 1, 0.32, 1)',
        transform: hovered ? 'scale(1.08)' : undefined,
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <span
        className={cn(
          'relative z-10 transition-opacity duration-100 [transition-timing-function:cubic-bezier(0.23,1,0.32,1)]',
          hovered && 'opacity-0'
        )}
      >
        {children}
      </span>
      {hovered ? (
        <span aria-hidden className='absolute inset-0 z-0 flex items-center justify-center'>
          <LingxiLogoMorph size={28} style={MORPH_INK} />
        </span>
      ) : null}
    </span>
  )
}
