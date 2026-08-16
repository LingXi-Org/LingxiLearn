import type { ReactNode } from 'react'
import Link from 'next/link'
import { ChipLink } from '@/components/ui-kit'
import { AuthAwareChipLink } from '@/lib/auth/auth-aware-link'
import {
  GitHubChip,
  LingxiWordmark,
  LogoMark,
  MobileNav,
  NAV_MENUS,
  NavbarShell,
  NavMenuChip,
} from '@/app/(landing)/components/navbar/components'
import { SIGNUP_HREF } from '@/app/(landing)/constants'

/**
 * Landing navbar.
 *
 * Sticky `<header><nav>` landmark with `SiteNavigationElement` schema.org
 * markup. Server Component - the dropdown triggers, GitHub chip, and the
 * {@link NavbarShell} (which frosts the bar to glass on scroll) are isolated
 * client leaves, so the wordmark and links stay zero-hydration, crawlable HTML.
 *
 * Every item is a bare emcn chip. Chips carry no margin of their own, so both
 * clusters' `gap-1` is the full 4px between pills, and the nav's own `gap-4`
 * is the full 16px between the wordmark and the first menu chip - twice the
 * inter-chip gap. Only that first gap is live: the trailing cluster is `ml-auto`.
 * Horizontal padding (`px-20`, 48px) matches every section's edge gutter,
 * and the bar content is capped and centered at the shared
 * `max-w-[1460px]` (1300px content + the two 80px gutters) so the wordmark
 * aligns with the contained section content on wide screens - the frosted
 * `<header>` shell stays full-bleed. Slightly taller vertical padding. Text
 * weight is the platform default (400).
 *
 * Layout (left → right): Sim wordmark (18px glyph centered in a
 * chip-height slot, chip-text color) → the {@link NAV_MENUS} mega-menus
 * (pure-CSS hover/focus dropdowns) → Pricing → GitHub stars. Right side: Log in
 * (default chip), Contact sales (outline chip), Sign up (filled chip).
 * Enterprise lives inside the Resources mega-menu, not as a standalone chip.
 */

interface NavbarProps {
  /**
   * Formatted GitHub star count (e.g. "28.8k"), fetched server-side at
   * build/revalidate time. Omitted by non-marketing shells that reuse this
   * navbar without a stars fetch (the GitHub chip is hidden when absent).
   */
  stars?: string
  /**
   * Render only the Sim wordmark - no nav menus, GitHub chip, auth chips, or
   * mobile sheet. Used by non-marketing shells (resume, public-file auth) that
   * want the brand header without the full marketing navigation.
   */
  logoOnly?: boolean
  /** Optional site-wide announcement rendered above the navigation in the same sticky header. */
  announcement?: ReactNode
}

export function Navbar({ logoOnly = false, announcement }: NavbarProps) {
  return (
    <NavbarShell announcement={announcement}>
      <nav
        aria-label='主导航'
        itemScope
        itemType='https://schema.org/SiteNavigationElement'
        className='relative mx-auto flex w-full max-w-[1460px] items-center gap-4 px-20 py-4 max-sm:px-5 max-lg:px-8'
      >
        <Link href='/' aria-label='Sim 首页' itemProp='url' className='flex h-[30px] items-center'>
          <span itemProp='name' className='sr-only'>
            Sim
          </span>
          <LogoMark>
            <LingxiWordmark />
          </LogoMark>
        </Link>

        {!logoOnly && (
          <>
            <div className='hidden items-center gap-1 lg:flex'>
              {NAV_MENUS.map((menu) => (
                <NavMenuChip key={menu.label} menu={menu} />
              ))}
              {/* 灵犀团队 - the one plain nav link: no dropdown, straight to the team contact page. */}
              <ChipLink href='/contact'>灵犀团队</ChipLink>
              <GitHubChip />
            </div>

            <div className='ml-auto hidden items-center gap-1 lg:flex'>
              <AuthAwareChipLink variant='primary' href={SIGNUP_HREF}>
                立即体验
              </AuthAwareChipLink>
            </div>

            <MobileNav />
          </>
        )}
      </nav>
    </NavbarShell>
  )
}
