import { DEFAULT_PERMISSION_GROUP_CONFIG } from '@/lib/permission-groups/types'

export async function resolveWorkspaceGroup(..._args: any[]) {
  return null
}

export async function getUserPermissionConfig(..._args: any[]) {
  return { config: DEFAULT_PERMISSION_GROUP_CONFIG, permissionGroupId: null }
}

export function validateModelProvider(..._args: any[]) { return true }
export function validateBlockType(..._args: any[]) { return true }
export function validateInvitationsAllowed(..._args: any[]) { return true }
export function validateMcpToolsAllowed(..._args: any[]) { return true }
export function validateCustomToolsAllowed(..._args: any[]) { return true }
export function validateSkillsAllowed(..._args: any[]) { return true }
export function validatePublicApiAllowed(..._args: any[]) { return true }
export function validatePublicFileSharing(..._args: any[]) { return true }
export function validateChatDeployAuth(..._args: any[]) { return true }
export function assertPermissionsAllowed(..._args: any[]) { return true }

export class InvitationsNotAllowedError extends Error {}
export class PublicApiNotAllowedError extends Error {}
export class PublicFileSharingNotAllowedError extends Error {}
export class ChatDeployAuthNotAllowedError extends Error {}

export class ToolNotAllowedError extends Error {
  constructor(message = 'Tool is not allowed') {
    super(message)
    this.name = 'ToolNotAllowedError'
  }
}
