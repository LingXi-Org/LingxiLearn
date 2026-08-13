'use client'

import { useEffect, useState } from 'react'
import { cn } from '@sim/emcn'
import { usePathname } from 'next/navigation'
import { Sidebar } from '@/app/workspace/[workspaceId]/w/components/sidebar/sidebar'
import { useSidebarStore } from '@/stores/sidebar/store'

interface WorkspaceChromeProps {
  children: React.ReactNode
  initialSidebarCollapsed?: boolean
}

export function WorkspaceChrome({
  children,
  initialSidebarCollapsed = false,
}: WorkspaceChromeProps) {
  const pathname = usePathname()
  const storeIsCollapsed = useSidebarStore((state) => state.isCollapsed)
  const [isSidebarHydrated, setIsSidebarHydrated] = useState(false)
  const isFullscreen = pathname?.endsWith('/upgrade') ?? false
  const isCollapsed = isSidebarHydrated ? storeIsCollapsed : initialSidebarCollapsed

  useEffect(() => {
    useSidebarStore.persist.rehydrate()
    setIsSidebarHydrated(true)
  }, [])

  return (
    <div className='relative flex min-h-0 flex-1'>
      {!isFullscreen && (
        <div
          className={cn(
            'shrink-0 overflow-hidden transition-[width] duration-175 motion-reduce:transition-none',
            isCollapsed ? 'w-[var(--sidebar-collapsed-width)]' : 'w-[var(--sidebar-width)]'
          )}
        >
          <Sidebar isCollapsed={isCollapsed} />
        </div>
      )}

      <div className='flex min-w-0 flex-1 flex-col p-2'>
        <div className='flex min-h-0 flex-1 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg)]'>
          {children}
        </div>
      </div>

    </div>
  )
}
