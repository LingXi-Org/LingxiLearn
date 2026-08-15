import Link from 'next/link'
import { LingxiWordmark } from '@/app/(landing)/components/navbar/components'

const LINK_CLASS =
  'text-sm text-[var(--text-muted)] transition-colors hover:text-[var(--text-primary)]'

interface FooterItem {
  label: string
  href: string
}

const PRODUCT_LINKS: FooterItem[] = [
  { label: '开始学习', href: '/workspace/lingxi/home' },
  { label: '学习记录', href: '/workspace/lingxi/home' },
]

const TECHNOLOGY_LINKS: FooterItem[] = [
  { label: 'DeepSeek', href: 'https://platform.deepseek.com/api_keys' },
  { label: 'Coze', href: 'https://code.coze.cn/playground' },
  { label: '感谢 GOAI', href: 'https://www.goaihz.com/' },
]

const ABOUT_LINKS: FooterItem[] = [
  { label: '联系我们', href: '/contact' },
  { label: '隐私政策', href: '/privacy' },
  { label: '服务条款', href: '/terms' },
]

function FooterColumn({ title, items }: { title: string; items: FooterItem[] }) {
  return (
    <div>
      <h3 className='mb-5 text-sm text-[var(--text-primary)]'>{title}</h3>
      <div className='flex flex-col gap-3'>
        {items.map(({ label, href }) => (
          <Link key={label} href={href} className={LINK_CLASS}>
            {label}
          </Link>
        ))}
      </div>
    </div>
  )
}

export function Footer() {
  return (
    <footer className='mt-[120px] w-full border-[var(--border)] border-t max-sm:mt-16 max-lg:mt-[88px]'>
      <div className='mx-auto w-full max-w-[1460px] px-20 pt-16 pb-10 max-sm:px-5 max-lg:px-8 max-lg:pt-12'>
        <div className='grid grid-cols-[minmax(240px,1.7fr)_repeat(3,minmax(120px,1fr))] gap-x-12 gap-y-12 max-sm:grid-cols-2 max-sm:gap-x-8 max-sm:gap-y-10 max-lg:grid-cols-[minmax(220px,1.4fr)_repeat(3,minmax(100px,1fr))]'>
          <div className='max-sm:col-span-full'>
            <Link href='/' aria-label='LingXi 首页' className='inline-flex'>
              <LingxiWordmark />
            </Link>
            <p className='mt-4 max-w-[220px] text-sm leading-6 text-[var(--text-muted)]'>
              AI 学习，因你而变。
            </p>
          </div>

          <FooterColumn title='产品' items={PRODUCT_LINKS} />
          <FooterColumn title='技术' items={TECHNOLOGY_LINKS} />
          <FooterColumn title='关于' items={ABOUT_LINKS} />
        </div>

        <div className='mt-16 border-[var(--border)] border-t pt-6 max-sm:mt-12'>
          <p className='text-sm text-[var(--text-muted)]'>© 2026 LingXi</p>
          <p className='mt-3 max-w-[620px] text-sm leading-6 text-[var(--text-muted)]'>
            LingXi 灵犀智学
          </p>
        </div>
      </div>
    </footer>
  )
}
