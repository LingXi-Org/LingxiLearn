import Link from 'next/link'

const RESOURCES = [
  {
    eyebrow: '运行时架构',
    title: 'LingxiHarness',
    description: '阅读 Skill-Native、有状态、受约束自主智能体运行时的完整架构文档。',
    href: '/safety/harness',
  },
  {
    eyebrow: '数据治理',
    title: '数据来源与合规说明',
    description: '了解数据来源、授权与脱敏方式、权限和删除机制，以及教育场景的安全边界。',
    href: '/safety/data-compliance',
  },
  {
    eyebrow: '个人信息',
    title: '隐私政策',
    description: '查看账户、学习任务、知识资源和智能体运行信息的处理方式与用户权利。',
    href: '/privacy',
  },
  {
    eyebrow: '使用规则',
    title: '服务条款',
    description: '查看 LingXi 学习工作台、智能体任务、知识库及相关服务的使用约定。',
    href: '/terms',
  },
  {
    eyebrow: '能力开放',
    title: 'LingxiSkills 文档库',
    description: '浏览可发现、可组合、可复用的 Skill 能力注册表与开发文档。',
    href: 'https://skills.lingxilearn.cn/',
    external: true,
  },
  {
    eyebrow: '开发文档',
    title: 'LingxiGraph 文档',
    description: '查看 Agent Graph Runtime 的架构、接口、部署和开发说明。',
    href: 'https://docs.lingxilearn.cn/docs/zh/',
    external: true,
  },
] as const

/** Safety and openness hub: six first-party policy, architecture, and developer resources. */
export default function Safety() {
  return (
    <main id='main-content'>
      <section
        aria-labelledby='safety-heading'
        className='mx-auto w-full max-w-[1460px] px-20 pt-[112px] pb-24 max-sm:px-5 max-sm:pt-20 max-sm:pb-16 max-lg:px-8'
      >
        <div className='flex max-w-[760px] flex-col gap-5'>
          <p className='text-[var(--text-muted)] text-sm'>安全、合规与开放资源</p>
          <h1
            id='safety-heading'
            className='text-balance text-[40px] text-[var(--text-primary)] leading-[1.1] max-sm:text-[32px]'
          >
            安全与开放
          </h1>
          <p className='max-w-[680px] text-[20px] text-[var(--text-body)] leading-[1.5] max-sm:text-[17px]'>
            从数据合规和教育边界，到可追溯的智能体运行时、开放 Skills 与开发文档，集中查看 LingXi
            如何建立可信、可验证、可复现的学习基础设施。
          </p>
        </div>

        <div className='mt-16 grid grid-cols-2 border-[var(--border)] border-t border-l max-md:grid-cols-1 max-sm:mt-10'>
          {RESOURCES.map((resource) => {
            const content = (
              <>
                <span className='text-[var(--text-muted)] text-xs tracking-[0.08em]'>
                  {resource.eyebrow}
                </span>
                <span className='mt-5 flex items-center justify-between gap-4'>
                  <h2 className='text-[22px] text-[var(--text-primary)] leading-tight'>
                    {resource.title}
                  </h2>
                  <span aria-hidden='true' className='text-[var(--text-muted)] text-lg'>
                    {'external' in resource ? '↗' : '→'}
                  </span>
                </span>
                <span className='mt-3 max-w-[54ch] text-[var(--text-body)] text-sm leading-[1.6]'>
                  {resource.description}
                </span>
              </>
            )

            const className =
              'flex min-h-[210px] flex-col border-[var(--border)] border-r border-b p-7 transition-colors hover:bg-[var(--surface-hover)] max-sm:min-h-0 max-sm:p-5'

            return 'external' in resource ? (
              <a
                key={resource.title}
                href={resource.href}
                target='_blank'
                rel='noopener noreferrer'
                className={className}
              >
                {content}
              </a>
            ) : (
              <Link key={resource.title} href={resource.href} className={className}>
                {content}
              </Link>
            )
          })}
        </div>
      </section>
    </main>
  )
}
