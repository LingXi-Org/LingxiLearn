'use client'

/**
 * LingxiLearn has one private personal workspace and no organization or
 * integration permission service. Keep the few capability decisions consumed
 * by native resource views local and explicit instead of querying Sim-era
 * placeholder endpoints.
 */
const LINGXI_PERMISSION_CONFIG = {
  hideFilesTab: false,
  hideTablesTab: false,
  hideKnowledgeBaseTab: false,
  hideTraceSpans: false,
  disablePublicFileSharing: true,
  allowedFileShareAuthTypes: ['private'],
}

export function usePermissionConfig() {
  return {
    config: LINGXI_PERMISSION_CONFIG,
    isInvitationsDisabled: true,
  }
}
