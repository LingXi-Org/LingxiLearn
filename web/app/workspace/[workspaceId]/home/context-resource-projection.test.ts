import { describe, expect, it } from 'vitest'
import type { ChatContext } from '@/stores/panel'
import {
  isResourceReferencedByContexts,
  resourceFromContext,
  resourceTitleFromContext,
} from './context-resource-projection'

const context = (value: Partial<ChatContext> & Pick<ChatContext, 'kind' | 'label'>) =>
  value as ChatContext

describe('context resource projection', () => {
  it.each([
    [context({ kind: 'knowledge', label: 'Knowledge', knowledgeId: 'kb-1' }), 'knowledgebase', 'kb-1'],
    [context({ kind: 'table', label: 'Table', tableId: 't-1' }), 'table', 't-1'],
    [context({ kind: 'table_selection', label: 'Rows', tableId: 't-2' }), 'table', 't-2'],
    [context({ kind: 'file', label: 'File', fileId: 'f-1' }), 'file', 'f-1'],
    [context({ kind: 'file_selection', label: 'Lines', fileId: 'f-2' }), 'file', 'f-2'],
  ])('maps %s to its resource', (input, type, id) => {
    expect(resourceFromContext(input)).toEqual({ type, id })
  })

  it('returns null for contexts without an owned resource', () => {
    expect(resourceFromContext(context({ kind: 'workflow', label: 'Workflow' }))).toBeNull()
    expect(resourceFromContext(context({ kind: 'file', label: 'Missing' }))).toBeNull()
  })

  it('uses whole-resource titles for selection contexts', () => {
    expect(
      resourceTitleFromContext(
        context({ kind: 'file_selection', label: 'notes.md:12-40', fileName: 'notes.md' })
      )
    ).toBe('notes.md')
    expect(
      resourceTitleFromContext(
        context({ kind: 'table_selection', label: 'Sales (3 rows)', tableName: 'Sales' })
      )
    ).toBe('Sales')
  })

  it('keeps a shared tab until the last referencing context is removed', () => {
    const resource = { type: 'file' as const, id: 'f-1' }
    expect(
      isResourceReferencedByContexts(resource, [
        context({ kind: 'file', label: 'notes.md', fileId: 'f-1' }),
        context({ kind: 'file_selection', label: 'lines', fileId: 'f-1' }),
      ])
    ).toBe(true)
    expect(
      isResourceReferencedByContexts(resource, [
        context({ kind: 'file', label: 'other.md', fileId: 'f-2' }),
      ])
    ).toBe(false)
  })
})
