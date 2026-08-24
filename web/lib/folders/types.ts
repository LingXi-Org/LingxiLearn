import type { FolderResourceType } from '@/lib/api/contracts/folders'

/** Canonical workspace folder row shared by workflow, file, knowledge, and table features. */
export interface WorkspaceFolder {
  id: string
  resourceType: FolderResourceType
  name: string
  userId: string
  workspaceId: string
  parentId: string | null
  /** Only meaningful for workflow folders. */
  locked: boolean
  sortOrder: number
  createdAt: Date
  updatedAt: Date
  deletedAt?: Date | null
}

export interface FolderTreeNode extends WorkspaceFolder {
  children: FolderTreeNode[]
  level: number
}
