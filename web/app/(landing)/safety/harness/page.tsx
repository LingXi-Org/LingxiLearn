import fs from 'node:fs/promises'
import path from 'node:path'
import { compileMDX } from 'next-mdx-remote/rsc'
import rehypeAutolinkHeadings from 'rehype-autolink-headings'
import rehypeSlug from 'rehype-slug'
import remarkGfm from 'remark-gfm'
import { mdxComponents } from '@/lib/content/mdx'
import { buildLandingMetadata } from '@/lib/landing/seo'
import { ProseHero, ProseShell } from '@/app/(landing)/components/prose-page/components'

export const revalidate = 3600

export const metadata = buildLandingMetadata({
  title: 'LingxiHarness 运行时架构 | LingXi 灵犀智学',
  description: 'LingxiHarness 面向有状态自主智能体的 Skill-Native、证据驱动与受约束运行时架构。',
  path: '/safety/harness',
})

const DOCUMENT_SECTIONS = [
  { href: '#摘要', label: '摘要' },
  { href: '#1-引言', label: '1. 引言' },
  { href: '#2-lingxiharness-总体架构', label: '2. 总体架构' },
  { href: '#3-state-driven-orchestration', label: '3. 状态驱动编排' },
  { href: '#4-skill-native-capability-composition', label: '4. Skill-Native 能力组合' },
  { href: '#5-evidence-grounded-constrained-autonomy', label: '5. 证据驱动的受约束自治' },
  { href: '#6-可观测的-replanning', label: '6. 可观测的重新规划' },
  { href: '#7-lingxilearn个性化作为-runtime-行为', label: '7. LingxiLearn 中的个性化' },
  { href: '#8-设计定位', label: '8. 设计定位' },
  { href: '#9-结论', label: '9. 结论' },
  { href: '#references', label: '参考文献' },
] as const

export default async function Page() {
  const documentPath = path.join(
    process.cwd(),
    'app',
    '(landing)',
    'safety',
    'harness',
    'content.md'
  )
  const markdown = await fs.readFile(documentPath, 'utf8')
  const body = markdown.replace(/^# .+\r?\n/, '').replace(/^# /gm, '## ')
  const { content } = await compileMDX({
    source: body,
    components: mdxComponents,
    options: {
      parseFrontmatter: false,
      mdxOptions: {
        remarkPlugins: [remarkGfm],
        rehypePlugins: [
          rehypeSlug,
          [rehypeAutolinkHeadings, { behavior: 'wrap', properties: { className: 'anchor' } }],
        ],
      },
    },
  })

  return (
    <ProseShell>
      <ProseHero
        title='LingxiHarness：面向有状态自主智能体的 Skill-Native 运行时架构'
        meta='Architecture document · 2026年8月16日'
        lead='以状态驱动编排、Skill-Native 能力组合和证据约束自治为核心的 Agent Runtime 设计。'
      />
      <div className='grid gap-12 lg:grid-cols-[210px_minmax(0,1fr)] lg:gap-16'>
        <nav
          aria-label='文章目录'
          className='border-[var(--border)] border-b pb-6 lg:sticky lg:top-28 lg:h-fit lg:border-b-0 lg:border-l lg:pb-0 lg:pl-5'
        >
          <p className='mb-3 text-[var(--text-muted)] text-xs tracking-[0.08em]'>文档目录</p>
          <ol className='grid gap-2 text-[13px] text-[var(--text-body)] leading-[1.4]'>
            {DOCUMENT_SECTIONS.map((section) => (
              <li key={section.href}>
                <a
                  href={section.href}
                  className='transition-colors hover:text-[var(--text-primary)] focus-visible:rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--text-primary)] focus-visible:outline-offset-2'
                >
                  {section.label}
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <article className='prose prose-lg max-w-none prose-blockquote:border-[var(--border-1)] prose-hr:border-[var(--border)] prose-headings:scroll-mt-32 prose-headings:text-[var(--text-primary)] prose-li:text-[var(--text-body)] prose-p:text-[var(--text-body)] prose-strong:text-[var(--text-primary)]'>
          {content}
        </article>
      </div>
    </ProseShell>
  )
}
