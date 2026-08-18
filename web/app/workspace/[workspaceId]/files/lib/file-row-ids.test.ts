/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'
import { folderRowId } from '@/app/workspace/[workspaceId]/components/folders/folder-row-id'
import { fileRowId, parseFilesRowId } from '@/app/workspace/[workspaceId]/files/lib/file-row-ids'

describe('files row ids', () => {
  it('round-trips a file id through the file-prefixed row id', () => {
    expect(parseFilesRowId(fileRowId('f-1'))).toEqual({ kind: 'file', id: 'f-1' })
  })

  it('delegates folder rows to the shared foldered-row parser', () => {
    expect(parseFilesRowId(folderRowId('dir-1'))).toEqual({ kind: 'folder', id: 'dir-1' })
  })

  it('treats an unprefixed id as a file, so pre-prefix row ids still resolve', () => {
    expect(parseFilesRowId('file-legacy')).toEqual({ kind: 'file', id: 'file-legacy' })
  })

  it('does not mistake a file id that merely contains the prefix for a prefixed one', () => {
    expect(parseFilesRowId('x-file:1')).toEqual({ kind: 'file', id: 'x-file:1' })
  })

  it('keeps a file id containing a colon intact', () => {
    expect(parseFilesRowId(fileRowId('a:b'))).toEqual({ kind: 'file', id: 'a:b' })
  })
})
