'use client'

import { useEffect, useState } from 'react'
import { ChipLink, cn } from '@sim/emcn'
import { Menu, X } from '@sim/emcn/icons'
import Link from 'next/link'
import { GithubOutlineIcon } from '@/components/icons'
import { NAV_MENUS } from '@/app/(landing)/components/navbar/components/nav-menu-chip'
import {
  NAVBAR_GLASS_SURFACE,
  useNavbarFrost,
} from '@/app/(landing)/components/navbar/components/navbar-shell'
import { SIGNUP_HREF } from '@/app/(landing)/constants'

/**
 * Mobile navigation - the `< lg` counterpart to the desktop nav clusters.
 *
 * Renders an always-visible "Sign up" chip plus a hamburger that toggles a
 * full-width slide-down sheet anchored under the bar (`top-full`). The sheet
 * expands the desktop mega-menus into grouped link sections plus the auth CTAs,
 * stacked on the shared {@link NAVBAR_GLASS_SURFACE} so it reads as one frosted
 * panel with the bar (which frosts in sync via {@link useNavbarFrost}). Only this
 * leaf hydrates; the desktop nav stays server-rendered.
 *
 * The sheet locks body scroll while open and closes on route change intent
 * (any link tap) and on `Escape`. With all three mega-menus expanded the
 * sections outgrow a phone viewport, so the sheet caps its height at the
 * space under the bar (`100dvh` minus the bar's 62px) and scrolls internally
 * (`overscroll-contain` keeps the locked page from rubber-banding behind it).
 * Motion is a short token-driven transform/opacity that collapses under
 * `prefers-reduced-motion`.
 */

/** Shared row chrome for every tappable text link in the sheet. */
const SHEET_ROW =
  'rounded-lg px-3 py-2.5 text-[15px] text-[var(--text-body)] transition-colors hover:bg-[var(--surface-hover)]'

export function MobileNav() {
  const frost = useNavbarFrost()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = ''
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  // Report open state to the shell so the sticky bar frosts in sync with the
  // sheet - the two then read as one continuous glass panel.
  useEffect(() => {
    frost?.setMenuOpen(open)
  }, [open, frost])

  return (
    <div className='ml-auto flex items-center gap-2 lg:hidden'>
      <ChipLink variant='primary' href={SIGNUP_HREF} prefetch={false}>
        立即体验
      </ChipLink>
      <button
        type='button'
        aria-label={open ? '关闭菜单' : '打开菜单'}
        aria-expanded={open}
        aria-controls='mobile-nav-sheet'
        onClick={() => setOpen((v) => !v)}
        className='flex size-[30px] items-center justify-center rounded-lg border border-[var(--border-1)] text-[var(--text-icon)] transition-colors hover:bg-[var(--surface-hover)]'
      >
        {open ? <X className='size-[18px]' /> : <Menu className='size-[18px]' />}
      </button>

      {open ? (
        <button
          type='button'
          aria-hidden='true'
          tabIndex={-1}
          onClick={() => setOpen(false)}
          className='fixed inset-0 top-full z-40 cursor-default bg-[color-mix(in_srgb,var(--text-primary)_8%,transparent)]'
        />
      ) : null}

      <div
        id='mobile-nav-sheet'
        className={cn(
          'absolute top-full right-0 left-0 z-50 max-h-[calc(100dvh-62px)] origin-top overflow-y-auto overscroll-contain border-[var(--border)] border-b transition-[opacity,transform,visibility] duration-200 motion-reduce:transition-none',
          NAVBAR_GLASS_SURFACE,
          open
            ? 'pointer-events-auto visible translate-y-0 opacity-100'
            : '-translate-y-2 pointer-events-none invisible opacity-0'
        )}
      >
        <div className='mx-auto flex w-full max-w-[1460px] flex-col gap-1 px-5 pt-2 pb-5'>
          {NAV_MENUS.map((menu) => (
            <div key={menu.label} className='flex flex-col'>
              <span className='px-3 pt-2.5 pb-1 text-[13px] text-[var(--text-muted)]'>
                {menu.label}
              </span>
              {menu.items.map((item) =>
                item.external ? (
                  <a
                    key={item.title}
                    href={item.href}
                    target='_blank'
                    rel='noopener noreferrer'
                    onClick={() => setOpen(false)}
                    className={SHEET_ROW}
                  >
                    {item.title}
                  </a>
                ) : (
                  <Link
                    key={item.title}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className={SHEET_ROW}
                  >
                    {item.title}
                  </Link>
                )
              )}
            </div>
          ))}

          <a
            href='https://github.com/simstudioai/sim'
            target='_blank'
            rel='noopener noreferrer'
            onClick={() => setOpen(false)}
            className={cn('flex items-center gap-2', SHEET_ROW)}
          >
            <GithubOutlineIcon className='size-[16px] text-[var(--text-icon)]' />
            <span>GitHub ↗</span>
          </a>

          <div className='mt-3 flex flex-col gap-2'>
            <ChipLink
              variant='primary'
              href={SIGNUP_HREF}
              fullWidth
              className='h-[40px] justify-center [&>span]:flex-none'
              onClick={() => setOpen(false)}
            >
              立即体验
            </ChipLink>
          </div>
        </div>
      </div>
    </div>
  )
}
