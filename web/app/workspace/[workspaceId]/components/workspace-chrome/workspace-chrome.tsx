'use client'

import { useState } from 'react'
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
  const isFullscreen = pathname?.endsWith('/upgrade') ?? false

  return (
    <div className='relative flex min-h-0 flex-1'>
      {!isFullscreen && (
        <div
          className={cn(
            'shrink-0 overflow-hidden transition-[width] duration-175 motion-reduce:transition-none',
            isCollapsed ? 'w-[52px]' : 'w-[var(--sidebar-width)]'
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

      {!isFullscreen && (
        <div className='absolute top-2 left-2 z-30'>
          <SidebarTooltip
            label={isCollapsed ? '展开侧栏' : '收起侧栏'}
            enabled={isCollapsed}
            side='right'
          >
            <button
              type='button'
              onClick={() => setIsCollapsed((collapsed) => !collapsed)}
              className={cn(
                'flex size-8 items-center justify-center rounded-lg text-[var(--text-icon)] transition-colors',
                'hover-hover:bg-[var(--surface-active)]',
                !isCollapsed && 'opacity-0 hover-hover:opacity-100 focus-visible:opacity-100'
              )}
              aria-label={isCollapsed ? '展开侧栏' : '收起侧栏'}
            >
              <PanelLeft className='size-4' />
            </button>
          </SidebarTooltip>
        </div>
      )}
    </div>
  )
}
