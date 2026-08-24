import type { WorkspaceFileRecord } from '@/lib/api/contracts/workspace-files'
import type { WorkspaceFileFolderApi } from '@/hooks/queries/workspace-file-folders'

/** A right-clicked row resolved to its record — what the row context menu acts on. */
export type FileResourceItem =
  | { kind: 'file'; id: string; file: WorkspaceFileRecord }
  | { kind: 'folder'; id: string; folder: WorkspaceFileFolderApi }
