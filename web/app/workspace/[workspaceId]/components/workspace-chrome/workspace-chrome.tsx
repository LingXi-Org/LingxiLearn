'use client'

import { useEffect, useState } from 'react'
import { cn } from '@sim/emcn'
import { PanelLeft } from '@sim/emcn/icons'
import { usePathname } from 'next/navigation'
import { Sidebar, SidebarTooltip } from './lingxi-sidebar'

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
  const [isCollapsed, setIsCollapsed] = useState(initialSidebarCollapsed)
  const [isCompactViewport, setIsCompactViewport] = useState(false)
  const isFullscreen = pathname?.endsWith('/upgrade') ?? false

  useEffect(() => {
    const saved = window.localStorage.getItem('lingxi-workspace-sidebar-collapsed')
    if (saved !== null) setIsCollapsed(saved === 'true')
  }, [])

  useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 860px)')
    const updateViewportMode = () => setIsCompactViewport(mediaQuery.matches)
    updateViewportMode()
    mediaQuery.addEventListener('change', updateViewportMode)
    return () => mediaQuery.removeEventListener('change', updateViewportMode)
  }, [])

  const toggleSidebar = () => {
    setIsCollapsed((collapsed) => {
      const next = !collapsed
      window.localStorage.setItem('lingxi-workspace-sidebar-collapsed', String(next))
      return next
    })
  }

  const sidebarCollapsed = isCollapsed || isCompactViewport

  return (
    <div className='workspace-chrome relative flex min-h-0 min-w-0 flex-1'>
      {!isFullscreen && (
        <div
          className={cn(
            'workspace-sidebar-shell relative z-20 shrink-0 overflow-hidden transition-[width] duration-175 motion-reduce:transition-none',
            sidebarCollapsed
              ? 'w-[var(--sidebar-collapsed-width)]'
              : 'w-[var(--sidebar-expanded-width)]'
          )}
          data-collapsed={sidebarCollapsed || undefined}
        >
          <Sidebar isCollapsed={sidebarCollapsed} />
        </div>
      )}

      <div
        className={cn(
          'workspace-content-shell flex min-w-0 flex-1 flex-col p-2',
          sidebarCollapsed && 'data-sidebar-collapsed'
        )}
        data-sidebar-collapsed={sidebarCollapsed || undefined}
        data-content-fullscreen={isFullscreen || undefined}
      >
        <div
          className={cn(
            'workspace-content-window flex min-h-0 min-w-0 flex-1 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg)]',
            sidebarCollapsed &&
              '[[data-sim-desktop-title-bar=inset]_[data-sidebar-collapsed]_&]:rounded-none [[data-sim-desktop-title-bar=inset]_[data-sidebar-collapsed]_&]:border-0'
          )}
        >
          {children}
        </div>
      </div>

      {!isFullscreen && (
        <div className='absolute top-2 left-2 z-30'>
          <SidebarTooltip
            label={isCollapsed ? '展开侧栏' : '收起侧栏'}
            enabled={isCollapsed}
            side='right'
          >
            <button
              type='button'
              onClick={toggleSidebar}
              className={cn(
                'flex size-8 items-center justify-center rounded-lg text-[var(--text-icon)] transition-colors',
                'hover-hover:bg-[var(--surface-active)]',
                !sidebarCollapsed && 'opacity-0 hover-hover:opacity-100 focus-visible:opacity-100',
                isCompactViewport && 'hidden'
              )}
              aria-label={sidebarCollapsed ? '展开侧栏' : '收起侧栏'}
            >
              <PanelLeft className='size-4' />
            </button>
          </SidebarTooltip>
        </div>
      )}
    </div>
  )
}
