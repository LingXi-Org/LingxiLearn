'use client'

import type { PermissionGroupConfig } from '@/lib/permission-groups/types'

interface PermissionData {
  config: PermissionGroupConfig
  permissionGroupId: string
}

export function useUserPermissionConfig(_workspaceId?: string): {
  data: PermissionData | undefined
  isLoading: boolean
} {
  return { data: undefined, isLoading: false }
}
