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
}))

import {
  formatFileType,
  MIME_TYPE_LABELS,
} from '@/app/workspace/[workspaceId]/files/lib/file-type-label'

describe('formatFileType', () => {
  it('labels well-known MIME types from the table', () => {
    expect(formatFileType('application/pdf', 'spec.pdf')).toBe('PDF')
    expect(formatFileType('text/markdown', 'notes.md')).toBe('Markdown')
    expect(
      formatFileType(
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'budget.xlsx'
      )
    ).toBe('Excel')
  })

  it('labels media from the effective type, so octet-stream uploads still read right', () => {
    expect(formatFileType('application/octet-stream', 'song.mp3')).toBe('Audio')
    expect(formatFileType('application/octet-stream', 'clip.mp4')).toBe('Video')
    expect(formatFileType('application/octet-stream', 'logo.png')).toBe('Image')
  })

  it('labels declared media types directly', () => {
    expect(formatFileType('audio/wav', 'recording.wav')).toBe('Audio')
    expect(formatFileType('image/jpeg', 'photo.jpg')).toBe('Image')
  })

  it('falls back to the uppercase extension for unknown types', () => {
    expect(formatFileType('application/x-custom', 'data.xyz')).toBe('XYZ')
  })

  it('falls back to the stored type, then "File", when nothing else identifies it', () => {
    expect(formatFileType('application/x-custom', 'noextension')).toBe('application/x-custom')
    expect(formatFileType(null, 'noextension')).toBe('File')
  })

  it('keeps the label table keyed by resolvable MIME types only', () => {
    for (const mimeType of Object.keys(MIME_TYPE_LABELS)) {
      expect(mimeType).toMatch(/^[a-z0-9.+-]+\/[a-z0-9.+-]+$/)
    }
  })
})
