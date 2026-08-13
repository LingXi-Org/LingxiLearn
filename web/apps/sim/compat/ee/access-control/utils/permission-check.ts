import { DEFAULT_PERMISSION_GROUP_CONFIG } from '@/lib/permission-groups/types'

export async function resolveWorkspaceGroup(
  _userId: string,
  _organizationId: string,
  _workspaceId: string
) {
  return null
}

export async function getUserPermissionConfig() {
  return { config: DEFAULT_PERMISSION_GROUP_CONFIG, permissionGroupId: null }
}

export function validateModelProvider() {
  return true
}

export function validateBlockType() {
  return true
}

export function validateInvitationsAllowed() {
  return true
}

export function validateMcpToolsAllowed() {
  return true
}

export function assertPermissionsAllowed() {
  return true
}
