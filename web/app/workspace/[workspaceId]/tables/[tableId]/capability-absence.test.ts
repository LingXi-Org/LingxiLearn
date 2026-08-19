/** @vitest-environment node */
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { LingxiCapabilityManifest } from '@/lib/lingxi/capabilities'

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return /\.(ts|tsx)$/.test(entry.name) && !entry.name.endsWith('.test.ts') ? [path] : []
  })
}

describe('Table Detail capability closure', () => {
  it('keeps the Lingxi table owner and rejects workflow identity', () => {
    expect(LingxiCapabilityManifest.tables).toMatchObject({
      status: 'integrated',
      backend: '/api/table',
      persistenceOwner: 'WorkspaceTable',
    })
    expect(LingxiCapabilityManifest.workflows).toMatchObject({
      status: 'not_integrated',
      backend: null,
      persistenceOwner: null,
    })
  })

  it('contains no Sim workflow, enrichment, run-column, or workflow-editor closure', () => {
    const source = sourceFiles(import.meta.dirname)
      .map((path) => readFileSync(path, 'utf8'))
      .join('\n')
    const unsupported = [
      ['Sim', 'Table'].join(''),
      ['Workflow', 'Group'].join(''),
      ['Workflow', 'Sidebar'].join(''),
      ['Enrichments', 'Sidebar'].join(''),
      ['RunStatus', 'Control'].join(''),
      ['run', '-column'].join(''),
      ['workflow', 'EditorPath'].join(''),
      ['workspace/', 'w/'].join(''),
      ['use', 'RunColumn'].join(''),
      ['use', 'CancelTableRuns'].join(''),
      ['Import', 'CsvDialog'].join(''),
      ['use', 'ExportTable'].join(''),
      ['Save', 'ViewModal'].join(''),
      ['selected', 'RunScope'].join(''),
    ]
    for (const identity of unsupported) expect(source).not.toContain(identity)
  })
})
