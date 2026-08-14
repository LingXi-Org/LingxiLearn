'use client'

import { useEffect, useState } from 'react'
import { cn } from '@sim/emcn'
import { usePathname } from 'next/navigation'
import { useSidebarStore } from '@/stores/sidebar/store'
import { SimSidebar } from './sim-sidebar'

interface WorkspaceChromeProps {
  children: React.ReactNode
  initialSidebarCollapsed?: boolean
}

/**
 * Sim's workspace frame, backed by Lingxi's local task sidebar. The original
 * chrome depends on Sim stores, desktop IPC and the search/workflow graph;
 * those are intentionally outside this static LingxiGraph build. Keeping the
 * frame here preserves Sim's proportions and responsive behavior without
 * making an unsupported API request.
 */
export function WorkspaceChrome({
  children,
  initialSidebarCollapsed = false,
}: WorkspaceChromeProps) {
  const pathname = usePathname()
  const isCollapsed = useSidebarStore((state) => state.isCollapsed)
  const syncWidth = useSidebarStore((state) => state.syncWidth)
  // The persisted store is intentionally hydrated after mount. Until then,
  // render from the server-readable cookie so the server and the first client
  // render use the same sidebar geometry and logo variant.
  const [storeReady, setStoreReady] = useState(false)
  const isFullscreen = pathname?.endsWith('/upgrade') ?? false

  useEffect(() => {
    // Sim keeps the collapsed state in a server-readable cookie and the width in
    // its persisted sidebar store. Reapply both after hydration and soft resize.
    useSidebarStore.setState({ isCollapsed: initialSidebarCollapsed })
    void useSidebarStore.persist.rehydrate()
    setStoreReady(true)
    syncWidth()
    const onResize = () => syncWidth()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [initialSidebarCollapsed, syncWidth])

  const sidebarCollapsed = storeReady ? isCollapsed : initialSidebarCollapsed

  return (
    <div className='workspace-chrome relative flex min-h-0 w-full min-w-0 max-w-none flex-1'>
      {!isFullscreen && (
        <div
          className={cn(
            'sidebar-shell-outer workspace-sidebar-shell relative z-20 shrink-0 overflow-hidden transition-[width] duration-175 motion-reduce:transition-none',
            sidebarCollapsed
              ? 'w-[var(--sidebar-collapsed-width)]'
              : 'w-[var(--sidebar-expanded-width)]'
          )}
          data-collapsed={sidebarCollapsed || undefined}
        >
          <div className='sidebar-shell-inner relative h-full min-h-0'>
            <SimSidebar isCollapsed={sidebarCollapsed} />
          </div>
        </div>
      )}

      <div
        className={cn(
          'workspace-content-shell flex min-h-0 w-full min-w-0 max-w-none flex-1 flex-col p-2',
          sidebarCollapsed && 'data-sidebar-collapsed'
        )}
        data-sidebar-collapsed={sidebarCollapsed || undefined}
        data-content-fullscreen={isFullscreen || undefined}
      >
        <div
          className={cn(
            'workspace-content-window flex min-h-0 w-full min-w-0 max-w-none flex-1 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg)]',
            sidebarCollapsed &&
              '[[data-sim-desktop-title-bar=inset]_[data-sidebar-collapsed]_&]:rounded-none [[data-sim-desktop-title-bar=inset]_[data-sidebar-collapsed]_&]:border-0'
          )}
        >
          {children}
        </div>
      </div>
    </div>
  )
}
