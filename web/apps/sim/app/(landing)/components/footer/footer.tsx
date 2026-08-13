import Link from 'next/link'
import { LingxiWordmark } from '@/app/(landing)/components/navbar/components'

/**
 * Landing footer - the site link directory. Re-authored from the prior landing
 * footer's structure and link content, but on the platform's light tokens and
 * with no cross-import from `(home)`. Fully responsive like the rest of the page
 * - desktop is the baseline, scaled down via `max-*` overrides (7→3→2 columns).
 * The closing CTA lives in its own {@link Cta} section above; this is purely the
 * `<footer>` landmark.
 *
 * Carries `SiteNavigationElement` schema for crawlable footer nav. A top
 * hairline separates it from the page and spans the full viewport width
 * (edge-to-edge): the border lives on the full-width `<footer>` landmark while
 * an inner container caps and centers the content at the shared
 * `max-w-[1460px]` with the same `px-20` gutter as every section above.
 */

const LINK_CLASS =
  'text-sm text-[var(--text-muted)] transition-colors hover:text-[var(--text-primary)]'

interface FooterItem {
  label: string
  href: string
  external?: boolean
}

/**
 * Platform modules link to their local landing pages (internal link equity
 * stays on the ranking pages); docs-only surfaces (MCP, API, Self Hosting)
 * and Status remain external.
 */
const PRODUCT_LINKS: FooterItem[] = [
  { label: '企业版', href: '/enterprise' },
  { label: '对话', href: 'https://docs.sim.ai/mothership', external: true },
  { label: '工作流', href: '/workflows' },
  { label: '知识库', href: '/knowledge' },
  { label: '数据表', href: '/tables' },
  { label: '文件', href: '/files' },
  { label: '日志', href: '/logs' },
  { label: 'MCP', href: 'https://docs.sim.ai/agents/mcp', external: true },
  { label: 'API', href: 'https://docs.sim.ai/api-reference/getting-started', external: true },
  { label: '自托管', href: 'https://docs.sim.ai/platform/self-hosting', external: true },
  { label: '服务状态', href: 'https://status.sim.ai', external: true },
]

const RESOURCES_LINKS: FooterItem[] = [
  { label: '博客', href: '/blog' },
  { label: '文档', href: 'https://docs.sim.ai', external: true },
  { label: '资源库', href: '/library' },
  { label: '招聘', href: '/careers' },
  { label: '更新日志', href: '/changelog' },
  { label: '联系我们', href: '/contact' },
]

/** Top model providers, sourced from the catalog so labels/hrefs never drift. */
const MODEL_LINKS: FooterItem[] = [
  { label: '全部模型', href: '/models' },
  { label: '模型目录', href: '/models' },
  { label: 'LingxiGraph', href: '/workspace/lingxi/home' },
]

/** Top comparison pages, sourced from the competitor catalog so labels/hrefs never drift. */
const COMPARE_LINKS: FooterItem[] = [
  { label: '全部对比', href: '/comparisons' },
  { label: '平台说明', href: '/comparisons' },
]

const INTEGRATION_LINKS: FooterItem[] = [
  { label: '全部集成', href: '/integrations' },
  { label: 'Slack', href: 'https://docs.sim.ai/integrations/slack', external: true },
  { label: 'GitHub', href: 'https://docs.sim.ai/integrations/github', external: true },
  { label: 'Gmail', href: 'https://docs.sim.ai/integrations/gmail', external: true },
  { label: 'Notion', href: 'https://docs.sim.ai/integrations/notion', external: true },
  { label: 'Salesforce', href: 'https://docs.sim.ai/integrations/salesforce', external: true },
  { label: 'Jira', href: '/integrations/jira' },
  { label: 'Linear', href: 'https://docs.sim.ai/integrations/linear', external: true },
  { label: 'Supabase', href: 'https://docs.sim.ai/integrations/supabase', external: true },
  { label: 'Stripe', href: 'https://docs.sim.ai/integrations/stripe', external: true },
]

const SOCIAL_LINKS: FooterItem[] = [
  { label: 'X (Twitter)', href: 'https://x.com/simdotai', external: true },
  {
    label: 'LinkedIn',
    href: 'https://www.linkedin.com/company/simstudioai/',
    external: true,
  },
  {
    label: 'Slack',
    href: 'https://join.slack.com/t/sim-ott9864/shared_invite/zt-43lp8tc5v-0qrrqHGBKUsvQlpoouH~TA',
    external: true,
  },
  {
    label: 'GitHub',
    href: 'https://github.com/simstudioai/sim',
    external: true,
  },
]

const LEGAL_LINKS: FooterItem[] = [
  { label: '服务条款', href: '/terms' },
  { label: '隐私政策', href: '/privacy' },
]

function FooterColumn({ title, items }: { title: string; items: FooterItem[] }) {
  return (
    <div>
      <h3 className='mb-4 text-[var(--text-primary)] text-sm'>{title}</h3>
      <div className='flex flex-col gap-2.5'>
        {items.map(({ label, href, external }) =>
          external ? (
            <a
              key={label}
              href={href}
              target='_blank'
              rel='noopener noreferrer'
              className={LINK_CLASS}
            >
              {label}
            </a>
          ) : (
            <Link key={label} href={href} className={LINK_CLASS}>
              {label}
            </Link>
          )
        )}
      </div>
    </div>
  )
}

export function Footer() {
  return (
    <footer className='mt-[120px] w-full border-[var(--border)] border-t max-sm:mt-16 max-lg:mt-[88px]'>
      <div className='mx-auto w-full max-w-[1460px] px-20 pt-16 pb-16 max-sm:px-5 max-lg:px-8 max-lg:pt-12 max-lg:pb-12'>
        <nav
          aria-label='页脚导航'
          itemScope
          itemType='https://schema.org/SiteNavigationElement'
          className='grid grid-cols-8 gap-x-8 gap-y-10 max-sm:grid-cols-2 max-sm:gap-y-8 max-lg:grid-cols-3'
        >
          <Link
            href='/'
            aria-label='Sim 首页'
            className='flex h-[18px] items-center max-lg:col-span-full max-lg:mb-2'
          >
            <LingxiWordmark />
          </Link>

          <FooterColumn title='产品' items={PRODUCT_LINKS} />
          <FooterColumn title='资源' items={RESOURCES_LINKS} />
          <FooterColumn title='对比' items={COMPARE_LINKS} />
          <FooterColumn title='集成' items={INTEGRATION_LINKS} />
          <FooterColumn title='模型' items={MODEL_LINKS} />
          <FooterColumn title='社交' items={SOCIAL_LINKS} />
          <FooterColumn title='法律' items={LEGAL_LINKS} />
        </nav>

        <p className='mt-16 text-[var(--text-muted)] text-sm'>© 2026 Sim。保留所有权利。</p>
      </div>
    </footer>
  )
}
