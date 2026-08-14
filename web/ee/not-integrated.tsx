'use client'

export function NotIntegrated({ title }: { title: string }) {
  return (
    <main className='flex min-h-[240px] items-center justify-center p-8'>
      <p className='text-sm text-[var(--text-secondary)]'>{title}暂未开放。</p>
    </main>
  )
}
