'use client'

import type { PermissionGroupConfig } from '@/lib/permission-groups/types'

export function useUserPermissionConfig(_workspaceId?: string): {
  data: { config: PermissionGroupConfig; permissionGroupId: string | null } | undefined
  isLoading: boolean
} {
  return { data: undefined, isLoading: false }
}
