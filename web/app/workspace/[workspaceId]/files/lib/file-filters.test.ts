/**
 * @vitest-environment node
 */
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/uploads/utils/file-utils', () => ({
  getFileExtension: (filename: string): string => {
    const lastDot = filename.lastIndexOf('.')
    return lastDot !== -1 ? filename.slice(lastDot + 1).toLowerCase() : ''
  },
  resolveEffectiveMimeType: (declared: string | null | undefined, filename: string): string => {
    const trimmed = declared?.trim()
    if (trimmed && trimmed !== 'application/octet-stream') return trimmed
    const lastDot = filename.lastIndexOf('.')
    const ext = lastDot !== -1 ? filename.slice(lastDot + 1).toLowerCase() : ''
    const known: Record<string, string> = {
      mp3: 'audio/mpeg',
      mp4: 'video/mp4',
      png: 'image/png',
      md: 'text/markdown',
    }
    return known[ext] ?? 'application/octet-stream'
  },
  isAudioFileType: (type: string): boolean => type.startsWith('audio/'),
  isVideoFileType: (type: string): boolean => type.startsWith('video/'),
}))

vi.mock('@/lib/uploads/utils/validation', () => ({
  isSupportedExtension: (ext: string): boolean => ['pdf', 'md', 'txt'].includes(ext),
}))

import type { WorkspaceFileFolderApi } from '@/hooks/queries/workspace-file-folders'
import type { WorkspaceFileRecord } from '@/lib/uploads/contexts/workspace'
import {
  fileMatchesFilters,
  listFolderFiles,
  listFolderSiblings,
  toSearchNeedle,
  type FilesListFilters,
} from '@/app/workspace/[workspaceId]/files/lib/file-filters'

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
    updatedAt: new Date('2026-01-01T00:00:00.000Z'),
    ...overrides,
  }
}

function makeFolder(
  id: string,
  parentId: string | null = null,
  overrides: Partial<WorkspaceFileFolderApi> = {}
): WorkspaceFileFolderApi {
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
    ...overrides,
  }
}

const NO_FILTERS: FilesListFilters = { type: [], size: [], uploadedBy: [] }

describe('toSearchNeedle', () => {
  it('trims and lowercases the raw input', () => {
    expect(toSearchNeedle('  ReadMe ')).toBe('readme')
  })

  it('collapses whitespace-only input to an empty needle', () => {
    expect(toSearchNeedle('   ')).toBe('')
  })
})

describe('listFolderSiblings', () => {
  const folders = [
    makeFolder('root-a', null, { name: 'Design' }),
    makeFolder('root-b', null, { name: 'Docs' }),
    makeFolder('child-a', 'root-a', { name: 'Assets' }),
  ]

  it('lists only the direct children of the current folder', () => {
    expect(listFolderSiblings(folders, null, '').map((f) => f.id)).toEqual(['root-a', 'root-b'])
    expect(listFolderSiblings(folders, 'root-a', '').map((f) => f.id)).toEqual(['child-a'])
  })

  it('narrows siblings by the search needle, case-insensitively', () => {
    expect(listFolderSiblings(folders, null, 'des').map((f) => f.id)).toEqual(['root-a'])
  })

  it('treats a missing parentId as the root level', () => {
    const orphan = makeFolder('orphan', undefined as unknown as null)
    expect(listFolderSiblings([orphan], null, '').map((f) => f.id)).toEqual(['orphan'])
  })
})

describe('fileMatchesFilters', () => {
  it('passes everything when no filter is active', () => {
    expect(fileMatchesFilters(makeFile(), NO_FILTERS)).toBe(true)
  })

  it('matches documents by their supported extension', () => {
    const filters: FilesListFilters = { ...NO_FILTERS, type: ['document'] }
    expect(fileMatchesFilters(makeFile({ name: 'spec.pdf', type: 'application/pdf' }), filters)).toBe(true)
    expect(fileMatchesFilters(makeFile({ name: 'song.mp3', type: 'application/octet-stream' }), filters)).toBe(false)
  })

  it('matches audio/video/image by the effective MIME type, not the stored one', () => {
    const audio: FilesListFilters = { ...NO_FILTERS, type: ['audio'] }
    const video: FilesListFilters = { ...NO_FILTERS, type: ['video'] }
    const image: FilesListFilters = { ...NO_FILTERS, type: ['image'] }
    // A browser upload stored as octet-stream still resolves from its extension.
    expect(
      fileMatchesFilters(makeFile({ name: 'song.mp3', type: 'application/octet-stream' }), audio)
    ).toBe(true)
    expect(
      fileMatchesFilters(makeFile({ name: 'clip.mp4', type: 'application/octet-stream' }), video)
    ).toBe(true)
    expect(
      fileMatchesFilters(makeFile({ name: 'logo.png', type: 'application/octet-stream' }), image)
    ).toBe(true)
    expect(fileMatchesFilters(makeFile({ name: 'notes.md' }), audio)).toBe(false)
  })

  it('accepts a file matching ANY of the selected type filters', () => {
    const filters: FilesListFilters = { ...NO_FILTERS, type: ['image', 'document'] }
    expect(fileMatchesFilters(makeFile({ name: 'logo.png', type: 'image/png' }), filters)).toBe(true)
    expect(fileMatchesFilters(makeFile({ name: 'spec.pdf', type: 'application/pdf' }), filters)).toBe(true)
    expect(
      fileMatchesFilters(makeFile({ name: 'song.mp3', type: 'application/octet-stream' }), filters)
    ).toBe(false)
  })

  it('buckets sizes at the 1 MB / 10 MB boundaries', () => {
    const small: FilesListFilters = { ...NO_FILTERS, size: ['small'] }
    const medium: FilesListFilters = { ...NO_FILTERS, size: ['medium'] }
    const large: FilesListFilters = { ...NO_FILTERS, size: ['large'] }
    expect(fileMatchesFilters(makeFile({ size: 1_048_575 }), small)).toBe(true)
    expect(fileMatchesFilters(makeFile({ size: 1_048_576 }), small)).toBe(false)
    expect(fileMatchesFilters(makeFile({ size: 1_048_576 }), medium)).toBe(true)
    expect(fileMatchesFilters(makeFile({ size: 10_485_760 }), medium)).toBe(true)
    expect(fileMatchesFilters(makeFile({ size: 10_485_761 }), large)).toBe(true)
    expect(fileMatchesFilters(makeFile({ size: 10_485_760 }), large)).toBe(false)
  })

  it('matches the uploader membership', () => {
    const filters: FilesListFilters = { ...NO_FILTERS, uploadedBy: ['u-2'] }
    expect(fileMatchesFilters(makeFile({ uploadedBy: 'u-2' }), filters)).toBe(true)
    expect(fileMatchesFilters(makeFile({ uploadedBy: 'u-1' }), filters)).toBe(false)
  })
})

describe('listFolderFiles', () => {
  const files = [
    makeFile({ id: 'a', name: 'Alpha.md', folderId: null }),
    makeFile({ id: 'b', name: 'beta.pdf', folderId: 'dir-1', type: 'application/pdf' }),
    makeFile({ id: 'c', name: 'Gamma.md', folderId: 'dir-1' }),
    makeFile({ id: 'd', name: 'delta.md', folderId: 'dir-2' }),
  ]

  it('lists only the files directly inside the folder', () => {
    expect(listFolderFiles(files, 'dir-1', '', NO_FILTERS).map((f) => f.id)).toEqual(['b', 'c'])
  })

  it('treats a missing folderId as the root level', () => {
    const rootless = makeFile({ id: 'r', folderId: undefined })
    expect(listFolderFiles([rootless], null, '', NO_FILTERS).map((f) => f.id)).toEqual(['r'])
  })

  it('combines the needle with the URL filters', () => {
    const documentOnly: FilesListFilters = { ...NO_FILTERS, type: ['document'] }
    expect(listFolderFiles(files, 'dir-1', 'gamma', documentOnly).map((f) => f.id)).toEqual(['c'])
    // pdf is a document too, but the needle rules it out
    expect(listFolderFiles(files, 'dir-1', 'gamma', NO_FILTERS).map((f) => f.id)).toEqual(['c'])
    expect(listFolderFiles(files, 'dir-1', 'beta', documentOnly).map((f) => f.id)).toEqual(['b'])
  })
})
