/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'
import { getFilesCommandAvailability } from '@/app/workspace/[workspaceId]/files/lib/files-command-matrix'

describe('getFilesCommandAvailability', () => {
  it('grants every command to an editor', () => {
    expect(getFilesCommandAvailability(true)).toEqual({
      open: true,
      download: true,
      togglePin: true,
      upload: true,
      createFile: true,
      createFolder: true,
      rename: true,
      move: true,
      delete: true,
      share: true,
    })
  })

  it('keeps reading and view preferences open but gates every mutation for viewers', () => {
    expect(getFilesCommandAvailability(false)).toEqual({
      open: true,
      download: true,
      togglePin: true,
      upload: false,
      createFile: false,
      createFolder: false,
      rename: false,
      move: false,
      delete: false,
      share: false,
    })
  })
})
