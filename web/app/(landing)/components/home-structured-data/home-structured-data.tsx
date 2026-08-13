import { SITE_URL } from '@/lib/urls'
import { JsonLd } from '@/app/(landing)/components/json-ld'

/**
 * Home-page JSON-LD - the entities specific to `/`: the `WebPage`, its
 * `BreadcrumbList`, the product `WebApplication` (`#software`, with offers /
 * featureList / reviews), and the `SoftwareSourceCode`.
 *
 * Rendered only by the landing root (`landing.tsx`), server-side before visible
 * content. The site-wide `Organization` / `WebSite` entities live in
 * {@link SiteStructuredData} (emitted by the shared layout on every page); the
 * nodes here reference them by `@id` (`${SITE_URL}#website` / `#organization`).
 *
 * Maintenance:
 * - Offer prices must match the Pricing component exactly.
 * - All claims must also appear as visible text on the page.
 * - Do not add `aggregateRating` without real, verifiable review data.
 */
/**
 * The home page's canonical description - the single string shared by the
 * `<meta name="description">`, OG/Twitter cards (`page.tsx`), and the JSON-LD
 * `WebPage.description` below, so the three surfaces never drift.
 */
export const HOME_PAGE_DESCRIPTION =
  'Sim 是一个开源 AI 工作空间，帮助团队通过 1,000+ 个集成和所有主流 LLM，以可视化或代码方式构建、部署和管理 AI 智能体。'

/**
 * The home page's canonical title - the single string shared by the
 * `<title>`, OG/Twitter titles (`page.tsx`), and the JSON-LD `WebPage.name`
 * below, so the title surfaces never drift.
 */
export const HOME_PAGE_TITLE = 'AI 工作空间｜构建、部署和管理 AI 智能体｜Sim'

const HOME_JSON_LD = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'WebPage',
      '@id': `${SITE_URL}#webpage`,
      url: SITE_URL,
      name: HOME_PAGE_TITLE,
      isPartOf: { '@id': `${SITE_URL}#website` },
      about: { '@id': `${SITE_URL}#software` },
      datePublished: '2024-01-01T00:00:00+00:00',
      description: HOME_PAGE_DESCRIPTION,
      breadcrumb: { '@id': `${SITE_URL}#breadcrumb` },
      inLanguage: 'zh-CN',
      speakable: {
        '@type': 'SpeakableSpecification',
        cssSelector: ['#hero-heading', '[id="hero"] p'],
      },
      potentialAction: [{ '@type': 'ReadAction', target: [SITE_URL] }],
    },
    {
      '@type': 'BreadcrumbList',
      '@id': `${SITE_URL}#breadcrumb`,
      itemListElement: [{ '@type': 'ListItem', position: 1, name: '首页', item: SITE_URL }],
    },
    {
      '@type': 'WebApplication',
      '@id': `${SITE_URL}#software`,
      url: SITE_URL,
      name: 'Sim，AI 工作空间',
      description:
        'Sim 是一个开源 AI 工作空间，帮助团队构建、部署和管理 AI 智能体。连接 1,000+ 个集成和所有主流 LLM，以可视化、对话式或代码方式创建能自动处理真实工作的智能体。已有超过 100,000 名构建者信赖，符合 SOC2 要求。',
      applicationCategory: 'BusinessApplication',
      applicationSubCategory: 'AI Workspace',
      operatingSystem: 'Web',
      browserRequirements: 'Requires a modern browser with JavaScript enabled',
      installUrl: `${SITE_URL}/signup`,
      offers: [
        {
          '@type': 'Offer',
          name: '社区版：包含 1,000 点额度',
          price: '0',
          priceCurrency: 'USD',
          availability: 'https://schema.org/InStock',
        },
        {
          '@type': 'Offer',
          name: '专业版：每月 6,000 点额度',
          price: '25',
          priceCurrency: 'USD',
          priceSpecification: {
            '@type': 'UnitPriceSpecification',
            price: '25',
            priceCurrency: 'USD',
            unitText: 'MONTH',
            billingIncrement: 1,
          },
          availability: 'https://schema.org/InStock',
        },
        {
          '@type': 'Offer',
          name: 'Max 版：每月 25,000 点额度',
          price: '100',
          priceCurrency: 'USD',
          priceSpecification: {
            '@type': 'UnitPriceSpecification',
            price: '100',
            priceCurrency: 'USD',
            unitText: 'MONTH',
            billingIncrement: 1,
          },
          availability: 'https://schema.org/InStock',
        },
      ],
      featureList: [
        '面向团队的 AI 工作空间',
        '对话：用自然语言构建和管理智能体',
        '可视化工作流构建器',
        '1,000+ 个集成',
        'LLM 编排（OpenAI、Anthropic、Google、xAI、Mistral、Perplexity）',
        '知识库创建',
        '数据表创建',
        '文档创建',
        'API 访问',
        '自定义函数',
        '定时工作流',
        '事件触发器',
      ],
      review: [
        {
          '@type': 'Review',
          author: { '@type': 'Person', name: 'Hasan Toor' },
          reviewBody:
            'This startup just dropped the fastest way to build AI agents. This Figma-like canvas to build agents will blow your mind.',
          url: 'https://x.com/hasantoxr/status/1912909502036525271',
        },
        {
          '@type': 'Review',
          author: { '@type': 'Person', name: 'nizzy' },
          reviewBody:
            'This is the zapier of agent building. I always believed that building agents and using AI should not be limited to technical people. I think this solves just that.',
          url: 'https://x.com/nizzyabi/status/1907864421227180368',
        },
        {
          '@type': 'Review',
          author: { '@type': 'Organization', name: 'xyflow' },
          reviewBody: 'A very good looking agent workflow builder and open source!',
          url: 'https://x.com/xyflowdev/status/1909501499719438670',
        },
      ],
    },
    {
      '@type': 'SoftwareSourceCode',
      '@id': `${SITE_URL}#source`,
      codeRepository: 'https://github.com/simstudioai/sim',
      programmingLanguage: ['TypeScript', 'Python'],
      runtimePlatform: 'Node.js',
      license: 'https://opensource.org/licenses/Apache-2.0',
      isPartOf: { '@id': `${SITE_URL}#software` },
    },
  ],
}

export function HomeStructuredData() {
  return <JsonLd data={HOME_JSON_LD} />
}
