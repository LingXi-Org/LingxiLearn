'use client'

import { createContext, type ReactNode, useContext } from 'react'
import type { LingxiWorkspaceHostContext } from '@/lib/lingxi/types'

const WorkspaceHostContextValue = createContext<LingxiWorkspaceHostContext | null>(null)

interface WorkspaceHostProviderProps {
  children: ReactNode
  workspaceId: string
  initialContext: LingxiWorkspaceHostContext
  /** Kept for source compatibility with Sim callers; Lingxi is static. */
  queryEnabled?: boolean
}

export function WorkspaceHostProvider({ children, initialContext }: WorkspaceHostProviderProps) {
  return (
    <WorkspaceHostContextValue.Provider value={initialContext}>
      {children}
    </WorkspaceHostContextValue.Provider>
  )
}

export function useWorkspaceHostContext(): LingxiWorkspaceHostContext {
  const context = useContext(WorkspaceHostContextValue)
  if (!context) throw new Error('useWorkspaceHostContext must be used within a WorkspaceHostProvider')
  return context
}

export function useOptionalWorkspaceHostContext(): LingxiWorkspaceHostContext | null {
  return useContext(WorkspaceHostContextValue)
}
