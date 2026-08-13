import { type CSSProperties, useId } from 'react'
import { cn } from '@/components/ui-kit'
import styles from './lingxi-logo-morph.module.css'

const CRESCENT_PATH =
  'M 24 22 C 45 6 72 12 85 31 C 98 50 91 75 70 88 C 79 73 79 56 70 42 C 60 26 42 20 24 22 Z'
const ARC_CONFIGS = [
  { depth: '0px', phase: '0deg', pitch: '0deg', yaw: '-10deg' },
  { depth: '8px', phase: '120deg', pitch: '10deg', yaw: '12deg' },
  { depth: '-8px', phase: '240deg', pitch: '-10deg', yaw: '12deg' },
] as const

interface LingxiLogoMorphProps {
  /** Rendered square size in px. */
  size?: number
  /** Layout-only classes for the SVG frame. */
  className?: string
  /** Optional CSS variable overrides for the mark ink. */
  style?: CSSProperties
}

/**
 * Replaces the Lingxi mark with three phase-shifted arc trails. The arcs use
 * the production mark as their return state, so the loop always closes on the
 * real logo instead of swapping between unrelated loader silhouettes.
 */
export function LingxiLogoMorph({ size = 28, className, style }: LingxiLogoMorphProps) {
  const gradientId = `llm-gradient-${useId().replace(/[^a-zA-Z0-9-]/g, '')}`

  return (
    <svg
      aria-hidden='true'
      className={cn(styles.frame, className)}
      focusable='false'
      height={size}
      viewBox='0 0 100 100'
      width={size}
      style={{ '--llm-size': `${size}px`, ...style } as CSSProperties}
    >
      <g className={styles.logoStage}>
        <g transform='translate(-30 -34) scale(1.020408 1.162791)'>
          <path d='M44.73 40.05H41.59L35.32 88.28a.07.07 0 0 0 0 0c-.17 1.19-3.61 22 10.5 25.56a15.78 15.78 0 0 0 3.29.35c5.52-.06 20-1.49 38.4-13.14L80.54 90S59.15 102.17 54 87.74a14.5 14.5 0 0 1-.59-7.1l4.93-32.12s1.73-7.46-3.87-8.41Z' />
          <path d='m65.61 55.09 34.7 54.57s2.46 4.66 9.42 4.58l12.73-.43-35-52.58S81.6 52.33 65.61 55.09Z' />
          <path d='M88.6 54s9.14-17.25 25.54-14c0 0 9.51 1.61 7.08 15.51 0 0-4.52 18.86-11.54 25.08a1.72 1.72 0 0 1-2.58-.33l-5.85-8.76a1.42 1.42 0 0 1-.07-1.45c.29-.54.76-1.48 1.48-3.13C102.66 66.91 108.37 46 88.6 54Z' />
        </g>
      </g>

      <g className={styles.arcStage}>
        <defs>
          <linearGradient id={gradientId} x1='0.12' x2='0.86' y1='0.1' y2='0.9'>
            <stop className={styles.shadeDeep} offset='0' />
            <stop className={styles.shadeBody} offset='0.46' />
            <stop className={styles.shadeLight} offset='0.72' />
            <stop className={styles.shadeDeep} offset='1' />
          </linearGradient>
        </defs>
        {ARC_CONFIGS.map((config) => (
          <g
            className={styles.arcOrbit}
            key={config.phase}
            style={
              {
                '--llm-phase': config.phase,
                '--llm-pitch': config.pitch,
                '--llm-yaw': config.yaw,
                '--llm-depth': config.depth,
              } as CSSProperties
            }
          >
            <path className={styles.arcTrail} d={CRESCENT_PATH} fill={`url(#${gradientId})`} />
            <path className={styles.arcCore} d={CRESCENT_PATH} fill={`url(#${gradientId})`} />
            <path className={styles.arcRim} d={CRESCENT_PATH} fill='none' stroke='currentColor' />
          </g>
        ))}
      </g>
    </svg>
  )
}
