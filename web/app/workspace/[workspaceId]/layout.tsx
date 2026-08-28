import Image from 'next/image'
import Link from 'next/link'
import { IdentityBadge } from '@/features/auth/identity-badge'

export default async function WorkspaceLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = await params
  const base = `/workspace/${workspaceId}`
  return (
    <div className='workspace-shell'>
      <aside className='sidebar'>
        <Link className='brand-link' href='/'>
          <Image
            alt='LingxiLearn'
            height={32}
            src='/brand/lingxi/wordmark-on-dark.svg'
            width={150}
          />
        </Link>
        <nav>
          <Link href={`${base}/tasks`}>Tasks</Link>
          <Link href={`${base}/artifacts`}>Artifacts</Link>
          <Link href={`${base}/skills`}>Skills</Link>
        </nav>
        <IdentityBadge />
      </aside>
      <main className='workspace-main'>{children}</main>
    </div>
  )
}
