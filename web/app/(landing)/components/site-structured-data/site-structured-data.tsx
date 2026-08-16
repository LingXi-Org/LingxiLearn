import { LINGXI_BRAND_ASSETS } from '@/lib/branding/lingxi-assets'
import { SITE_URL } from '@/lib/urls'
import { JsonLd } from '@/app/(landing)/components/json-ld'

const SITE_JSON_LD = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Organization',
      '@id': `${SITE_URL}#organization`,
      name: '灵犀智学',
      alternateName: 'LingXi',
      legalName: '灵犀智学',
      description:
        'LingXi 灵犀智学是面向学习任务的 AI 学习工作台，基于学习状态组织讲解、图解、练习和复习。',
      url: SITE_URL,
      foundingDate: '2025',
      address: {
        '@type': 'PostalAddress',
        streetAddress: '80 Langton St',
        addressLocality: 'San Francisco',
        addressRegion: 'CA',
        postalCode: '94103',
        addressCountry: 'US',
      },
      logo: {
        '@type': 'ImageObject',
        '@id': `${SITE_URL}#logo`,
        url: `${SITE_URL}${LINGXI_BRAND_ASSETS.wordmarkOnLight}`,
        contentUrl: `${SITE_URL}${LINGXI_BRAND_ASSETS.wordmarkOnLight}`,
        width: 5064,
        height: 2169,
        caption: '灵犀智学标志',
      },
      image: { '@id': `${SITE_URL}#logo` },
      brand: { '@type': 'Brand', name: '灵犀智学' },
      sameAs: [
        'https://github.com/LingXi-Org',
        'https://github.com/LingXi-Org/LingxiLearn',
        'https://docs.lingxilearn.cn/docs/zh/',
      ],
      contactPoint: [
        {
          '@type': 'ContactPoint',
          contactType: 'customer support',
          url: `${SITE_URL}/contact`,
          availableLanguage: ['zh-CN'],
        },
        {
          '@type': 'ContactPoint',
          contactType: 'sales',
          url: `${SITE_URL}/contact`,
          availableLanguage: ['zh-CN'],
        },
      ],
    },
    {
      '@type': 'WebSite',
      '@id': `${SITE_URL}#website`,
      url: SITE_URL,
      name: '灵犀智学｜面向学习任务的智能工作台',
      description: '灵犀智学基于 LingxiGraph，为学习任务提供连续对话、课程资源和知识检测。',
      publisher: { '@id': `${SITE_URL}#organization` },
      inLanguage: 'zh-CN',
    },
  ],
}

/**
 * Site-wide JSON-LD - the `Organization` and `WebSite` entities that are true on
 * every landing-family page. Rendered once by the shared landing layout (via
 * {@link LandingShell}), server-side before any visible content, so crawlers and
 * AI answer engines read the canonical site graph first.
 *
 * Page-specific schema (WebPage, BreadcrumbList, Article, Product, FAQ, …) lives
 * on each page and references these entities by `@id`. The canonical `@id` form
 * is `${SITE_URL}#organization` / `${SITE_URL}#website` (no slash before the
 * fragment) - every per-page emitter (platform, solutions, pricing, home) points
 * `isPartOf`/`publisher`/`about` at these exact ids, so the graph resolves.
 *
 * Maintenance: `sameAs` must match the Footer social links. `legalName`
 * matches the entity named throughout `apps/sim/app/(landing)/terms`.
 */
export function SiteStructuredData() {
  return <JsonLd data={SITE_JSON_LD} />
}
