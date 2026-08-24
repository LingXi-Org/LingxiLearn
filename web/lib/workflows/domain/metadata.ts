/** Canonical workflow list metadata returned by workspace queries. */
export interface WorkflowMetadata {
  id: string
  name: string
  lastModified: Date
  createdAt: Date
  description?: string
  workspaceId?: string
  folderId?: string | null
  sortOrder: number
  archivedAt?: Date | null
  locked?: boolean
  forkSyncExcluded?: boolean
  isDeployed?: boolean
}
