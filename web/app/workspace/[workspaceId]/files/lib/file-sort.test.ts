/**
 * @vitest-environment node
 */
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/uploads/utils/file-utils', () => ({
  getFileExtension: (filename: string): string => {
    const lastDot = filename.lastIndexOf('.')
    return lastDot !== -1 ? filename.slice(lastDot + 1).toLowerCase() : ''
  },
  resolveEffectiveMimeType: (declared: string | null | undefined): string =>
    declared?.trim() || 'application/octet-stream',
}))

import type { WorkspaceFileFolderApi } from '@/hooks/queries/workspace-file-folders'
import type { WorkspaceMember } from '@/hooks/queries/workspace'
import type { WorkspaceFileRecord } from '@/lib/uploads/contexts/workspace'
import {
  buildSortableFileEntries,
  FOLDER_TYPE_LABEL,
  sortKeyForFile,
  sortKeyForFolder,
  type FileSortContext,
} from '@/app/workspace/[workspaceId]/files/lib/file-sort'

function makeFile(overrides: Partial<WorkspaceFileRecord> = {}): WorkspaceFileRecord {
  return {
    id: 'file-1',
    workspaceId: 'ws-1',
    name: 'notes.md',
    key: 'ws-1/file-1',
    path: '/workspace/ws-1/file-1',
    size: 1024,
    type: 'text/markdown',
    uploadedBy: 'u-1',
    folderId: null,
    uploadedAt: new Date('2026-01-01T00:00:00.000Z'),
    updatedAt: new Date('2026-01-02T00:00:00.000Z'),
    ...overrides,
  }
}

function makeFolder(
  id: string,
  overrides: Partial<WorkspaceFileFolderApi> = {}
): WorkspaceFileFolderApi {
  return {
    id,
    workspaceId: 'ws-1',
    userId: 'u-1',
    name: id,
    parentId: null,
    path: `/${id}`,
    sortOrder: 0,
    deletedAt: null,
    createdAt: new Date('2026-01-01T00:00:00.000Z'),
    updatedAt: new Date('2026-01-03T00:00:00.000Z'),
    ...overrides,
  }
}

const MEMBERS: WorkspaceMember[] = [
  { userId: 'u-1', name: 'Alice', image: null },
  { userId: 'u-2', name: 'Bob', image: null },
]

function makeCtx(overrides: Partial<FileSortContext> = {}): FileSortContext {
  return {
    membersById: new Map(MEMBERS.map((member) => [member.userId, member])),
    folderSizeMap: new Map(),
    ...overrides,
  }
}

describe('sortKeyForFolder', () => {
  const folder = makeFolder('dir-1', { name: 'Docs', userId: 'u-2' })

  it('uses the rolled-up folder size, defaulting to zero', () => {
    const ctx = makeCtx({ folderSizeMap: new Map([['dir-1', 2048]]) })
    expect(sortKeyForFolder(folder, 'size', ctx)).toBe(2048)
    expect(sortKeyForFolder(folder, 'size', makeCtx())).toBe(0)
  })

  it('sorts folders under the constant "Folder" type label', () => {
    expect(sortKeyForFolder(folder, 'type', makeCtx())).toBe(FOLDER_TYPE_LABEL)
  })

  it('resolves created/updated to timestamps and owner to the member name', () => {
    const ctx = makeCtx()
    expect(sortKeyForFolder(folder, 'created', ctx)).toBe(folder.createdAt.getTime())
    expect(sortKeyForFolder(folder, 'updated', ctx)).toBe(folder.updatedAt.getTime())
    expect(sortKeyForFolder(folder, 'owner', ctx)).toBe('Bob')
  })

  it('falls back to the folder name for the name column', () => {
    expect(sortKeyForFolder(folder, 'name', makeCtx())).toBe('Docs')
  })

  it('yields a null owner when the member is unknown', () => {
    const ctx = makeCtx({ membersById: new Map() })
    expect(sortKeyForFolder(folder, 'owner', ctx)).toBeNull()
  })
})

describe('sortKeyForFile', () => {
  const file = makeFile({ name: 'spec.pdf', type: 'application/pdf', uploadedBy: 'u-1' })

  it('uses the file size, the formatted type label, and the member name', () => {
    const ctx = makeCtx()
    expect(sortKeyForFile(file, 'size', ctx)).toBe(1024)
    expect(sortKeyForFile(file, 'type', ctx)).toBe('PDF')
    expect(sortKeyForFile(file, 'owner', ctx)).toBe('Alice')
  })

  it('resolves created from uploadedAt and updated from updatedAt', () => {
    const ctx = makeCtx()
    expect(sortKeyForFile(file, 'created', ctx)).toBe(file.uploadedAt.getTime())
    expect(sortKeyForFile(file, 'updated', ctx)).toBe(file.updatedAt.getTime())
  })
})

describe('buildSortableFileEntries', () => {
  it('decorates folders and files into one sortable list with precomputed keys', () => {
    const folder = makeFolder('dir-1', { name: 'Docs' })
    const file = makeFile({ id: 'file-1', name: 'notes.md' })
    const entries = buildSortableFileEntries({
      visibleFolders: [folder],
      filteredFiles: [file],
      sortColumn: 'name',
      pinnedFolderIds: new Set(['dir-1']),
      pinnedFileIds: new Set<string>(),
      ctx: makeCtx(),
    })

    expect(entries).toEqual([
      { item: { kind: 'folder', folder }, pinned: true, name: 'Docs', key: 'Docs' },
      { item: { kind: 'file', file }, pinned: false, name: 'notes.md', key: 'notes.md' },
    ])
  })

  it('marks pinned files from the pinned id set', () => {
    const file = makeFile({ id: 'file-1' })
    const entries = buildSortableFileEntries({
      visibleFolders: [],
      filteredFiles: [file],
      sortColumn: 'updated',
      pinnedFolderIds: new Set<string>(),
      pinnedFileIds: new Set(['file-1']),
      ctx: makeCtx(),
    })
    expect(entries[0]?.pinned).toBe(true)
    expect(entries[0]?.key).toBe(file.updatedAt.getTime())
  })
})
