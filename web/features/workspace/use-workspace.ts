'use client'

import { useCallback, useEffect, useState } from 'react'
import type { Workspace } from '@/entities/workspace/model'
import { workspaceApi } from '@/shared/api/client'

export function useWorkspace(workspaceId: string) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const response = await workspaceApi.get(workspaceId)
      setWorkspace(response.workspace)
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load workspace')
    }
  }, [workspaceId])

  useEffect(() => {
    void load()
  }, [load])

  return { workspace, error, reload: load }
}
