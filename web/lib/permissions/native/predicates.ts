/** Workspace permission level: read < write < admin. */
export type PermissionType = 'read' | 'write' | 'admin'

export const PERMISSION_RANK = { read: 1, write: 2, admin: 3 } as const satisfies Record<
  PermissionType,
  number
>

export function isPermissionType(value: unknown): value is PermissionType {
  return typeof value === 'string' && Object.hasOwn(PERMISSION_RANK, value)
}

export function permissionSatisfies(
  have: PermissionType | null | undefined,
  required: PermissionType
): boolean {
  return have != null && PERMISSION_RANK[have] >= PERMISSION_RANK[required]
}

export const ORG_ADMIN_ROLES = ['owner', 'admin'] as const

export function isOrgAdminRole(role: string | null | undefined): boolean {
  return role === 'owner' || role === 'admin'
}
