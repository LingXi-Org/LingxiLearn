'use client'

import { createLogger } from '@/lib/logger'
import { getQueryClient } from '@/app/_shell/providers/get-query-client'
import { environmentKeys } from '@/hooks/queries/environment'
import { useMothershipDraftsStore } from '@/stores/mothership-drafts/store'
import {
  clearMothershipQueueForLogout,
  useMothershipQueueStore,
} from '@/stores/mothership-queue/store'
import { resetWorkspaceClientState } from '@/stores/reset-workspace-client-state'
import { useWorkflowRegistry } from '@/stores/workflows/registry/store'
import { useSubBlockStore } from '@/stores/workflows/subblock/store'
import { useWorkflowStore } from '@/stores/workflows/workflow/store'

const logger = createLogger('Stores')

/** localStorage key for the admin recent-impersonations list; kept through clearUserData. */
export const RECENT_IMPERSONATIONS_STORAGE_KEY = 'recent-impersonations'

/**
 * Reset all Zustand stores and React Query caches to initial state.
 */
export const resetAllStores = () => {
  useWorkflowRegistry.setState({
    activeWorkflowId: null,
    error: null,
    hydration: {
      phase: 'idle',
      workspaceId: null,
      workflowId: null,
      requestId: null,
      error: null,
    },
  })
  useWorkflowStore.getState().clear()
  useSubBlockStore.getState().clear()
  getQueryClient().removeQueries({ queryKey: environmentKeys.all })
  useMothershipDraftsStore.setState({ drafts: {} })
  useMothershipQueueStore.getState().reset()
  resetWorkspaceClientState()
}

/**
 * Clear all user data when signing out.
 */
export async function clearUserData(): Promise<void> {
  if (typeof window === 'undefined') return

  try {
    resetAllStores()
    await clearMothershipQueueForLogout()

    const keysToKeep = ['next-favicon', 'theme', RECENT_IMPERSONATIONS_STORAGE_KEY]
    const keysToRemove = Object.keys(localStorage).filter((key) => !keysToKeep.includes(key))
    keysToRemove.forEach((key) => localStorage.removeItem(key))

    logger.info('User data cleared successfully')
  } catch (error) {
    logger.error('Error clearing user data:', { error })
  }
}
