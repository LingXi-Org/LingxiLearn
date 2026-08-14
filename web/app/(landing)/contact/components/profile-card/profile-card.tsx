'use client'

import { useCallback, useEffect, useMemo, useRef } from 'react'
import './profile-card.css'

const ANIMATION_CONFIG = {
  INITIAL_DURATION: 1200,
  INITIAL_X_OFFSET: 70,
  INITIAL_Y_OFFSET: 60,
  ENTER_TRANSITION_MS: 180,
}

const clamp = (value: number, min = 0, max = 100) => Math.min(Math.max(value, min), max)
const round = (value: number, precision = 3) => Number(value.toFixed(precision))
const adjust = (value: number, fromMin: number, fromMax: number, toMin: number, toMax: number) =>
  round(toMin + ((toMax - toMin) * (value - fromMin)) / (fromMax - fromMin))

type CardStyle = React.CSSProperties & Record<`--${string}`, string>

interface ProfileCardProps {
  name: string
  title: string
  handle: string
  status?: string
  contactText?: string
  contactHref?: string
  avatarUrl?: string
  miniAvatarUrl?: string
  iconUrl?: string
  grainUrl?: string
  innerGradient?: string
  behindGlowEnabled?: boolean
  behindGlowColor?: string
  behindGlowSize?: string
  enableTilt?: boolean
  className?: string
  onContactClick?: () => void
}

export function ProfileCard({
  name,
  title,
  handle,
  status = 'LingXi Team',
  contactText = '联系我们',
  contactHref,
  avatarUrl,
  miniAvatarUrl,
  iconUrl,
  grainUrl,
  innerGradient = 'linear-gradient(145deg, rgba(255,255,255,0.16) 0%, rgba(148,163,184,0.16) 100%)',
  behindGlowEnabled = true,
  behindGlowColor = 'rgba(148, 163, 184, 0.42)',
  behindGlowSize = '50%',
  enableTilt = true,
  className = '',
  onContactClick,
}: ProfileCardProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const shellRef = useRef<HTMLDivElement>(null)
  const enterTimerRef = useRef<number | null>(null)
  const leaveRafRef = useRef<number | null>(null)

  const tiltEngine = useMemo(() => {
    if (!enableTilt) return null

    let rafId: number | null = null
    let running = false
    let lastTimestamp = 0
    let currentX = 0
    let currentY = 0
    let targetX = 0
    let targetY = 0
    let initialUntil = 0

    const setVarsFromXY = (x: number, y: number) => {
      const shell = shellRef.current
      const wrap = wrapRef.current
      if (!shell || !wrap) return

      const width = shell.clientWidth || 1
      const height = shell.clientHeight || 1
      const percentX = clamp((100 / width) * x)
      const percentY = clamp((100 / height) * y)
      const centerX = percentX - 50
      const centerY = percentY - 50
      const properties: Record<string, string> = {
        '--pointer-x': `${percentX}%`,
        '--pointer-y': `${percentY}%`,
        '--background-x': `${adjust(percentX, 0, 100, 35, 65)}%`,
        '--background-y': `${adjust(percentY, 0, 100, 35, 65)}%`,
        '--pointer-from-center': `${clamp(Math.hypot(percentY - 50, percentX - 50) / 50, 0, 1)}`,
        '--pointer-from-top': `${percentY / 100}`,
        '--pointer-from-left': `${percentX / 100}`,
        '--rotate-x': `${round(-(centerX / 5))}deg`,
        '--rotate-y': `${round(centerY / 4)}deg`,
      }

      Object.entries(properties).forEach(([key, value]) => wrap.style.setProperty(key, value))
    }

    const step = (timestamp: number) => {
      if (!running) return
      if (lastTimestamp === 0) lastTimestamp = timestamp
      const delta = (timestamp - lastTimestamp) / 1000
      lastTimestamp = timestamp
      const tau = timestamp < initialUntil ? 0.6 : 0.14
      const progress = 1 - Math.exp(-delta / tau)
      currentX += (targetX - currentX) * progress
      currentY += (targetY - currentY) * progress
      setVarsFromXY(currentX, currentY)

      if (Math.abs(targetX - currentX) > 0.05 || Math.abs(targetY - currentY) > 0.05 || document.hasFocus()) {
        rafId = requestAnimationFrame(step)
      } else {
        running = false
        lastTimestamp = 0
        rafId = null
      }
    }

    const start = () => {
      if (running) return
      running = true
      lastTimestamp = 0
      rafId = requestAnimationFrame(step)
    }

    return {
      setTarget(x: number, y: number) {
        targetX = x
        targetY = y
        start()
      },
      toCenter() {
        const shell = shellRef.current
        if (shell) this.setTarget(shell.clientWidth / 2, shell.clientHeight / 2)
      },
      beginInitial(duration: number) {
        initialUntil = performance.now() + duration
        start()
      },
      cancel() {
        if (rafId !== null) cancelAnimationFrame(rafId)
        rafId = null
        running = false
        lastTimestamp = 0
      },
    }
  }, [enableTilt])

  const getOffsets = (event: PointerEvent, element: HTMLDivElement) => {
    const rect = element.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }

  const handlePointerMove = useCallback(
    (event: PointerEvent) => {
      const shell = shellRef.current
      if (!shell || !tiltEngine) return
      const { x, y } = getOffsets(event, shell)
      tiltEngine.setTarget(x, y)
    },
    [tiltEngine]
  )

  const handlePointerEnter = useCallback(
    (event: PointerEvent) => {
      const shell = shellRef.current
      if (!shell || !tiltEngine) return
      shell.classList.add('active', 'entering')
      if (enterTimerRef.current !== null) window.clearTimeout(enterTimerRef.current)
      enterTimerRef.current = window.setTimeout(
        () => shell.classList.remove('entering'),
        ANIMATION_CONFIG.ENTER_TRANSITION_MS
      )
      const { x, y } = getOffsets(event, shell)
      tiltEngine.setTarget(x, y)
    },
    [tiltEngine]
  )

  const handlePointerLeave = useCallback(() => {
    const shell = shellRef.current
    if (!shell || !tiltEngine) return
    tiltEngine.toCenter()

    const checkSettle = () => {
      if (!shellRef.current) return
      if (leaveRafRef.current === null) return
      leaveRafRef.current = requestAnimationFrame(checkSettle)
      shell.classList.remove('active')
      cancelAnimationFrame(leaveRafRef.current)
      leaveRafRef.current = null
    }

    if (leaveRafRef.current !== null) cancelAnimationFrame(leaveRafRef.current)
    leaveRafRef.current = requestAnimationFrame(checkSettle)
  }, [tiltEngine])

  useEffect(() => {
    if (!enableTilt || !tiltEngine) return
    const shell = shellRef.current
    if (!shell) return

    shell.addEventListener('pointerenter', handlePointerEnter)
    shell.addEventListener('pointermove', handlePointerMove)
    shell.addEventListener('pointerleave', handlePointerLeave)

    const initialX = (shell.clientWidth || 0) - ANIMATION_CONFIG.INITIAL_X_OFFSET
    tiltEngine.setTarget(initialX, ANIMATION_CONFIG.INITIAL_Y_OFFSET)
    tiltEngine.toCenter()
    tiltEngine.beginInitial(ANIMATION_CONFIG.INITIAL_DURATION)

    return () => {
      shell.removeEventListener('pointerenter', handlePointerEnter)
      shell.removeEventListener('pointermove', handlePointerMove)
      shell.removeEventListener('pointerleave', handlePointerLeave)
      if (enterTimerRef.current !== null) window.clearTimeout(enterTimerRef.current)
      if (leaveRafRef.current !== null) cancelAnimationFrame(leaveRafRef.current)
      tiltEngine.cancel()
    }
  }, [enableTilt, handlePointerEnter, handlePointerLeave, handlePointerMove, tiltEngine])

  const cardStyle = useMemo<CardStyle>(
    () => ({
      '--icon': iconUrl ? `url(${iconUrl})` : 'none',
      '--grain': grainUrl ? `url(${grainUrl})` : 'none',
      '--inner-gradient': innerGradient,
      '--behind-glow-color': behindGlowColor,
      '--behind-glow-size': behindGlowSize,
    }),
    [behindGlowColor, behindGlowSize, grainUrl, iconUrl, innerGradient]
  )

  return (
    <div ref={wrapRef} className={`pc-card-wrapper ${className}`.trim()} style={cardStyle}>
      {behindGlowEnabled && <div className='pc-behind' aria-hidden='true' />}
      <div ref={shellRef} className='pc-card-shell'>
        <section className='pc-card' aria-label={`${name}，${title}`}>
          <div className='pc-inside'>
            <div className='pc-shine' aria-hidden='true' />
            <div className='pc-glare' aria-hidden='true' />
            <div className='pc-content pc-avatar-content'>
              {avatarUrl ? (
                <img className='avatar' src={avatarUrl} alt={`${name}头像`} loading='lazy' />
              ) : (
                <div className='pc-avatar-placeholder' aria-label={`${name}头像占位`}>
                  <span>{name.slice(0, 1)}</span>
                </div>
              )}

              <div className='pc-user-info'>
                <div className='pc-user-details'>
                  <div className='pc-mini-avatar'>
                    {miniAvatarUrl || avatarUrl ? (
                      <img src={miniAvatarUrl || avatarUrl} alt='' loading='lazy' />
                    ) : (
                      <span aria-hidden='true'>{name.slice(0, 1)}</span>
                    )}
                  </div>
                  <div className='pc-user-text'>
                    <div className='pc-handle'>@{handle}</div>
                    <div className='pc-status'>{status}</div>
                  </div>
                </div>
                {contactHref ? (
                  <a className='pc-contact-btn' href={contactHref}>
                    {contactText}
                  </a>
                ) : (
                  <button className='pc-contact-btn' onClick={onContactClick} type='button'>
                    {contactText}
                  </button>
                )}
              </div>
            </div>
            <div className='pc-content'>
              <div className='pc-details'>
                <h3>{name}</h3>
                <p>{title}</p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
