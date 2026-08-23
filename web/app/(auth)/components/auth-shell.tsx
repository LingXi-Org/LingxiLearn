import Image from 'next/image'
import Link from 'next/link'
import { ChipLink } from '@/components/ui-kit'
import { LINGXI_BRAND_ASSETS } from '@/lib/branding/lingxi-assets'

export function AuthShell({
  children,
  footer,
}: {
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  return (
    <main className='light desktop-title-bar-page relative flex min-h-screen flex-col bg-[var(--bg)] text-[var(--text-primary)]'>
      <header>
        <nav className='mx-auto flex w-full max-w-[1446px] items-center px-12 py-4 max-sm:px-5 max-lg:px-8'>
          <Link href='/' aria-label='灵犀智学首页' className='flex h-[30px] items-center gap-2'>
            <Image src={LINGXI_BRAND_ASSETS.iconOnLight} alt='' width={22} height={22} priority />
            <Image
              src={LINGXI_BRAND_ASSETS.wordmarkOnLight}
              alt='灵犀智学'
              width={58}
              height={25}
              priority
              className='h-[22px] w-auto translate-y-[2px]'
            />
          </Link>
        </nav>
      </header>
      <div className='flex flex-1 items-center justify-center px-4 pb-16'>
        <div className='w-full max-w-[400px]'>{children}</div>
      </div>
      {footer}
    </main>
  )
}

export function AuthHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className='space-y-1 text-center'>
      <h1 className='text-balance text-[32px] text-[var(--text-primary)] leading-[1.2]'>{title}</h1>
      <p className='text-base text-[var(--text-muted)] leading-[1.5]'>{description}</p>
    </div>
  )
}

export function AuthLegalFooter({ action }: { action: string }) {
  return (
    <p className='text-center text-[var(--text-muted)] text-xs leading-relaxed'>
      {action}即表示你同意我们的{' '}
      <ChipLink
        href='/terms'
        className='inline-flex px-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
      >
        服务条款
      </ChipLink>{' '}
      和{' '}
      <ChipLink
        href='/privacy'
        className='inline-flex px-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
      >
        隐私政策
      </ChipLink>
    </p>
  )
}
