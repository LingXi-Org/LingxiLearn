import type { ReactNode } from 'react'

export default function InterfacesLayout({ children }: { children: ReactNode }) {
  return <div className='min-h-screen bg-[var(--bg)] text-[var(--text-primary)]'>{children}</div>
}
