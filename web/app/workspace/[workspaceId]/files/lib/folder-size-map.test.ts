/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'
import type { WorkspaceFileFolderApi } from '@/hooks/queries/workspace-file-folders'
import type { WorkspaceFileRecord } from '@/lib/uploads/contexts/workspace'
import { buildFolderSizeMap } from '@/app/workspace/[workspaceId]/files/lib/folder-size-map'

function makeFile(folderId: string | null, size: number, id = `f-${size}`): WorkspaceFileRecord {
  return {
    id,
    workspaceId: 'ws-1',
    name: `${id}.bin`,
    key: `ws-1/${id}`,
    path: `/workspace/ws-1/${id}`,
    size,
    type: 'application/octet-stream',
    uploadedBy: 'u-1',
    folderId,
    uploadedAt: new Date('2026-01-01T00:00:00.000Z'),
    updatedAt: new Date('2026-01-01T00:00:00.000Z'),
  }
}

function makeFolder(id: string, parentId: string | null = null): WorkspaceFileFolderApi {
  return {
    id,
    workspaceId: 'ws-1',
    userId: 'u-1',
    name: id,
    parentId,
    path: `/${id}`,
    sortOrder: 0,
    deletedAt: null,
    createdAt: new Date('2026-01-01T00:00:00.000Z'),
    updatedAt: new Date('2026-01-01T00:00:00.000Z'),
  }
}

describe('buildFolderSizeMap', () => {
  it('sums the sizes of each folder\'s own files', () => {
    const map = buildFolderSizeMap(
      [makeFile('dir-1', 100), makeFile('dir-1', 50), makeFile('dir-2', 7)],
      [makeFolder('dir-1'), makeFolder('dir-2')]
    )
    expect(map.get('dir-1')).toBe(150)
    expect(map.get('dir-2')).toBe(7)
  })

  it('rolls descendant folder sizes up into every ancestor', () => {
    const map = buildFolderSizeMap(
      [makeFile('root', 10), makeFile('mid', 20), makeFile('leaf', 30)],
      [makeFolder('root'), makeFolder('mid', 'root'), makeFolder('leaf', 'mid')]
    )
    expect(map.get('leaf')).toBe(30)
    expect(map.get('mid')).toBe(50)
    expect(map.get('root')).toBe(60)
  })

  it('counts root-level files nowhere', () => {
    const map = buildFolderSizeMap([makeFile(null, 99)], [makeFolder('dir-1')])
    expect(map.get('dir-1')).toBe(0)
  })

  it('reports zero for an empty folder', () => {
    const map = buildFolderSizeMap([], [makeFolder('dir-1')])
    expect(map.get('dir-1')).toBe(0)
  })

  it('terminates on a parent/child cycle the optimistic move write can produce', () => {
    const map = buildFolderSizeMap(
      [makeFile('a', 5), makeFile('b', 7)],
      [makeFolder('a', 'b'), makeFolder('b', 'a')]
    )
    // The cycle edge contributes zero instead of recursing forever; both entries exist.
    expect(map.size).toBe(2)
    expect(map.get('a')).toBeLessThanOrEqual(12)
    expect(map.get('b')).toBeLessThanOrEqual(12)
  })
})
