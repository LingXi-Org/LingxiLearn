import { AuthAwareChipLink } from '@/lib/auth/auth-aware-link'
import type { SolutionsFooterCtaConfig } from '@/app/(landing)/components/solutions-page/types'
import { DEMO_HREF, SIGNUP_HREF } from '@/app/(landing)/constants'

/**
 * Landing pre-footer CTA - the page's final conversion band. A tall, centered
 * closing band with a large headline over two pill actions - a primary
 * "Get started" routing to sign-up and an outline "Contact sales" routing to
 * the demo-booking page.
 *
 * The band carries no vertical padding of its own: its spacious closing moment
 * comes from the uniform inter-section `gap` (owned by the `<main>` flex in
 * `landing.tsx`) above it and the `Footer`'s top margin below it. The headline
 * mirrors the hero `<h1>` exactly (48px / `leading-[1.1]` and the same responsive
 * ramp), so the page opens and closes on the same display size. Horizontal
 * padding (`px-20`) matches every section above, and the section is capped and
 * centered at the shared `max-w-[1460px]`.
 */
interface CtaProps extends Partial<SolutionsFooterCtaConfig> {}

export function Cta({
  heading = '今天就构建你的第一个智能体。',
  description,
  primary = { label: '立即开始', href: SIGNUP_HREF },
  secondary = { label: '联系销售', href: DEMO_HREF },
}: CtaProps = {}) {
  return (
    <section
      id='cta'
      aria-labelledby='cta-heading'
      className='mx-auto flex w-full max-w-[1460px] flex-col items-center gap-[22px] px-20 text-center max-sm:px-5 max-lg:px-8'
    >
      <h2
        id='cta-heading'
        className='max-w-[860px] text-balance text-[48px] text-[var(--text-primary)] leading-[1.1] max-sm:text-[32px] max-xl:text-[40px]'
      >
        {heading}
      </h2>
      {description ? (
        <p className='max-w-[640px] text-pretty text-[16px] text-[var(--text-muted)] leading-[1.6]'>
          {description}
        </p>
      ) : null}
      <div className='flex items-center gap-1'>
        <AuthAwareChipLink variant='primary' href={primary.href}>
          {primary.label}
        </AuthAwareChipLink>
        {secondary ? (
          <AuthAwareChipLink href={secondary.href} className='border border-[var(--border-1)]'>
            {secondary.label}
          </AuthAwareChipLink>
        ) : null}
      </div>
    </section>
  )
}
