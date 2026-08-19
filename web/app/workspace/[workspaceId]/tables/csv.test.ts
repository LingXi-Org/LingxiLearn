/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'
import { pickCsvFiles } from '@/app/workspace/[workspaceId]/tables/csv'

function file(name: string): File {
  return new File([''], name)
}

describe('pickCsvFiles', () => {
  it('keeps csv and tsv files, case-insensitively', () => {
    const picked = pickCsvFiles([file('a.csv'), file('b.TSV'), file('c.Csv')])
    expect(picked.map((f) => f.name)).toEqual(['a.csv', 'b.TSV', 'c.Csv'])
  })

  it('drops files with other extensions', () => {
    const picked = pickCsvFiles([file('notes.txt'), file('data.csv'), file('archive.csv.zip')])
    expect(picked.map((f) => f.name)).toEqual(['data.csv'])
  })

  it('drops extensionless files', () => {
    expect(pickCsvFiles([file('README')])).toEqual([])
  })

  it('returns an empty list for null, undefined, or empty input', () => {
    expect(pickCsvFiles(null)).toEqual([])
    expect(pickCsvFiles(undefined)).toEqual([])
    expect(pickCsvFiles([])).toEqual([])
  })
})
