/**
 * @vitest-environment node
 */
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/uploads/utils/file-utils', () => ({
  getFileExtension: (filename: string): string => {
    const lastDot = filename.lastIndexOf('.')
    return lastDot !== -1 ? filename.slice(lastDot + 1).toLowerCase() : ''
  },
}))

vi.mock('@/lib/uploads/utils/validation', () => ({
  SUPPORTED_DOCUMENT_EXTENSIONS: ['pdf', 'md'],
  SUPPORTED_CODE_EXTENSIONS: ['ts'],
  SUPPORTED_AUDIO_EXTENSIONS: ['mp3'],
  SUPPORTED_VIDEO_EXTENSIONS: ['mp4'],
  SUPPORTED_IMAGE_EXTENSIONS: ['png'],
}))

import { MAX_WORKSPACE_FILE_SIZE } from '@/lib/uploads/shared/types'
import {
  FILES_ACCEPT_ATTR,
  partitionUploadCandidates,
  SUPPORTED_EXTENSIONS,
} from '@/app/workspace/[workspaceId]/files/lib/file-upload-policy'

/** partitionUploadCandidates only reads `name` and `size`, so a plain object suffices. */
function makeCandidate(name: string, size: number): File {
  return { name, size } as unknown as File
}

describe('SUPPORTED_EXTENSIONS / FILES_ACCEPT_ATTR', () => {
  it('merges every category into one allowlist', () => {
    expect(SUPPORTED_EXTENSIONS).toEqual(['pdf', 'md', 'ts', 'mp3', 'mp4', 'png'])
  })

  it('derives the file input accept attribute from the allowlist', () => {
    expect(FILES_ACCEPT_ATTR).toBe('.pdf,.md,.ts,.mp3,.mp4,.png')
  })
})

describe('partitionUploadCandidates', () => {
  it('keeps allowed files in their original order', () => {
    const candidates = [makeCandidate('b.md', 10), makeCandidate('a.pdf', 20)]
    const { allowed, oversized, unsupported } = partitionUploadCandidates(candidates)
    expect(allowed.map((file) => file.name)).toEqual(['b.md', 'a.pdf'])
    expect(oversized).toEqual([])
    expect(unsupported).toEqual([])
  })

  it('rejects files above the workspace size cap', () => {
    const { allowed, oversized } = partitionUploadCandidates([
      makeCandidate('ok.pdf', MAX_WORKSPACE_FILE_SIZE),
      makeCandidate('big.pdf', MAX_WORKSPACE_FILE_SIZE + 1),
    ])
    expect(allowed.map((file) => file.name)).toEqual(['ok.pdf'])
    expect(oversized).toEqual(['big.pdf'])
  })

  it('rejects unsupported extensions', () => {
    const { allowed, unsupported } = partitionUploadCandidates([
      makeCandidate('notes.md', 10),
      makeCandidate('virus.exe', 10),
      makeCandidate('noextension', 10),
    ])
    expect(allowed.map((file) => file.name)).toEqual(['notes.md'])
    expect(unsupported).toEqual(['virus.exe', 'noextension'])
  })

  it('checks the size cap before the extension, so a huge exe is oversized', () => {
    const { oversized, unsupported } = partitionUploadCandidates([
      makeCandidate('huge.exe', MAX_WORKSPACE_FILE_SIZE + 1),
    ])
    expect(oversized).toEqual(['huge.exe'])
    expect(unsupported).toEqual([])
  })
})
