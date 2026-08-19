/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'
import {
  buildDocumentTags,
  buildTagSlotPayload,
  countActiveTagFilters,
  createTagFilterEntry,
  formatTagValueForList,
  formatTagValueForModal,
  getAvailableTagDefinitions,
  getDefaultOperatorForFieldType,
  getDocumentTagValues,
  getTagFilterLabel,
  getValueForFieldTypeChange,
  hasTagNameConflict,
  projectTagFilters,
  resolveTagFilterSelection,
  type TagDefinitionShape,
  type TagFilterEntry,
} from '@/app/workspace/[workspaceId]/knowledge/detail/domain/tags'
import { ALL_TAG_SLOTS } from '@/lib/knowledge/constants'
import type { DocumentTag } from '@/lib/knowledge/tags/types'
import type { DocumentData } from '@/lib/knowledge/types'

function makeDoc(overrides: Partial<DocumentData> = {}): DocumentData {
  return {
    id: 'doc-1',
    knowledgeBaseId: 'kb-1',
    filename: 'doc.pdf',
    fileUrl: 'data:application/pdf;base64,',
    fileSize: 100,
    mimeType: 'application/pdf',
    chunkCount: 1,
    tokenCount: 25,
    characterCount: 100,
    processingStatus: 'completed',
    enabled: true,
    uploadedAt: '2026-01-01T00:00:00.000Z',
    ...overrides,
  }
}

const DEFINITIONS: TagDefinitionShape[] = [
  { tagSlot: 'tag1', displayName: 'Author', fieldType: 'text' },
  { tagSlot: 'number1', displayName: 'Pages', fieldType: 'number' },
  { tagSlot: 'date1', displayName: 'Published', fieldType: 'date' },
  { tagSlot: 'boolean1', displayName: 'Reviewed', fieldType: 'boolean' },
]

describe('formatTagValueForList', () => {
  it('formats dates as MMM d, yyyy', () => {
    expect(formatTagValueForList('2026-04-21', 'date')).toBe('Apr 21, 2026')
  })

  it('returns the raw string for unparseable dates', () => {
    expect(formatTagValueForList('not-a-date', 'date')).toBe('not-a-date')
  })

  it('formats booleans as Yes/No', () => {
    expect(formatTagValueForList(true, 'boolean')).toBe('Yes')
    expect(formatTagValueForList(false, 'boolean')).toBe('No')
  })

  it('localizes numbers and stringifies the rest', () => {
    expect(formatTagValueForList(1234567, 'number')).toBe((1234567).toLocaleString())
    expect(formatTagValueForList('plain', 'text')).toBe('plain')
  })
})

describe('getDocumentTagValues (list projection)', () => {
  it('maps raw slots through definitions in slot order', () => {
    const doc = makeDoc({ tag1: 'Ada', number1: 42, boolean1: true })
    const values = getDocumentTagValues(doc, DEFINITIONS)
    expect(values).toEqual([
      { slot: 'tag1', displayName: 'Author', value: 'Ada' },
      { slot: 'number1', displayName: 'Pages', value: (42).toLocaleString() },
      { slot: 'boolean1', displayName: 'Reviewed', value: 'Yes' },
    ])
  })

  it('skips nullish slots', () => {
    expect(getDocumentTagValues(makeDoc(), DEFINITIONS)).toEqual([])
  })

  it('falls back to the slot-derived field type and raw slot name without a definition', () => {
    const doc = makeDoc({ boolean2: false })
    expect(getDocumentTagValues(doc, [])).toEqual([
      { slot: 'boolean2', displayName: 'boolean2', value: 'No' },
    ])
  })
})

describe('formatTagValueForModal', () => {
  it('renders booleans as True/False', () => {
    expect(formatTagValueForModal('true', 'boolean')).toBe('True')
    expect(formatTagValueForModal('false', 'boolean')).toBe('False')
  })

  it('renders date-only values as local calendar dates', () => {
    expect(formatTagValueForModal('2026-04-21', 'date')).toBeTruthy()
    expect(formatTagValueForModal('not-a-date', 'date')).toBe('not-a-date')
  })

  it('keeps non-date values and empty strings untouched', () => {
    expect(formatTagValueForModal('hello', 'text')).toBe('hello')
    expect(formatTagValueForModal('', 'text')).toBe('')
  })
})

describe('buildDocumentTags (editor projection)', () => {
  it('builds editable tags only for slots with a definition', () => {
    const doc = makeDoc({ tag1: '  Ada  ', tag2: 'orphan' })
    const tags = buildDocumentTags(doc, DEFINITIONS)
    expect(tags).toEqual([
      { slot: 'tag1', displayName: 'Author', fieldType: 'text', value: 'Ada' },
    ])
  })

  it('skips blank values', () => {
    const doc = makeDoc({ tag1: '   ' })
    expect(buildDocumentTags(doc, DEFINITIONS)).toEqual([])
  })
})

describe('buildTagSlotPayload', () => {
  it('covers every slot and clears missing values with an empty string', () => {
    const tags: DocumentTag[] = [
      { slot: 'tag1', displayName: 'Author', fieldType: 'text', value: ' Ada ' },
    ]
    const payload = buildTagSlotPayload(tags)
    expect(Object.keys(payload).sort()).toEqual([...ALL_TAG_SLOTS].sort())
    expect(payload.tag1).toBe('Ada')
    expect(payload.tag2).toBe('')
    expect(payload.boolean3).toBe('')
  })
})

describe('tag editor helpers', () => {
  const tags: DocumentTag[] = [
    { slot: 'tag1', displayName: 'Author', fieldType: 'text', value: 'Ada' },
    { slot: 'tag2', displayName: 'Year', fieldType: 'text', value: '2026' },
  ]

  it('keeps the value when the field type is unchanged and clears it otherwise', () => {
    expect(getValueForFieldTypeChange('text', 'text', 'keep')).toBe('keep')
    expect(getValueForFieldTypeChange('number', 'text', 'keep')).toBe('')
  })

  it('detects name conflicts case-insensitively, ignoring the edited row', () => {
    expect(hasTagNameConflict(tags, 'author', null)).toBe(true)
    expect(hasTagNameConflict(tags, 'author', 0)).toBe(false)
    expect(hasTagNameConflict(tags, 'Fresh', null)).toBe(false)
    expect(hasTagNameConflict(tags, '   ', null)).toBe(false)
  })

  it('lists definitions not already used by the document', () => {
    expect(getAvailableTagDefinitions(DEFINITIONS, tags).map((d) => d.tagSlot)).toEqual([
      'number1',
      'date1',
      'boolean1',
    ])
  })
})

describe('tag filter entries', () => {
  it('creates an empty entry with the injected id', () => {
    expect(createTagFilterEntry('id-1')).toEqual({
      id: 'id-1',
      tagName: '',
      tagSlot: '',
      fieldType: 'text',
      operator: 'contains',
      value: '',
      valueTo: '',
    })
  })

  it('defaults text filters to contains and others to their first operator', () => {
    expect(getDefaultOperatorForFieldType('text', [])).toBe('contains')
    expect(
      getDefaultOperatorForFieldType('number', [{ value: 'eq', label: 'equals' }])
    ).toBe('eq')
    expect(getDefaultOperatorForFieldType('date', [])).toBe('eq')
  })

  it('resolves a selection from its definition and clears values', () => {
    expect(resolveTagFilterSelection(DEFINITIONS, 'Pages')).toEqual({
      tagName: 'Pages',
      tagSlot: 'number1',
      fieldType: 'number',
      operator: 'eq',
      value: '',
      valueTo: '',
    })
  })

  it('falls back to a text filter for an unknown tag name', () => {
    const resolved = resolveTagFilterSelection(DEFINITIONS, 'Nope')
    expect(resolved.tagSlot).toBe('')
    expect(resolved.fieldType).toBe('text')
    expect(resolved.operator).toBe('contains')
  })
})

describe('projectTagFilters', () => {
  const entry = (overrides: Partial<TagFilterEntry>): TagFilterEntry => ({
    ...createTagFilterEntry('id'),
    ...overrides,
  })

  it('drops rows without a slot or a trimmed value', () => {
    const entries = [
      entry({ id: 'a', tagSlot: '', value: 'x' }),
      entry({ id: 'b', tagSlot: 'tag1', value: '   ' }),
      entry({ id: 'c', tagSlot: 'tag1', tagName: 'Author', value: 'Ada' }),
    ]
    expect(projectTagFilters(entries)).toEqual([
      { tagSlot: 'tag1', fieldType: 'text', operator: 'contains', value: 'Ada' },
    ])
  })

  it('applies a between filter only once both bounds are set', () => {
    const incomplete = [
      entry({ id: 'a', tagSlot: 'number1', fieldType: 'number', operator: 'between', value: '1' }),
    ]
    expect(projectTagFilters(incomplete)).toEqual([])

    const complete = [
      entry({
        id: 'a',
        tagSlot: 'number1',
        fieldType: 'number',
        operator: 'between',
        value: '1',
        valueTo: '5',
      }),
    ]
    expect(projectTagFilters(complete)).toEqual([
      { tagSlot: 'number1', fieldType: 'number', operator: 'between', value: '1', valueTo: '5' },
    ])
  })

  it('never emits valueTo for non-between operators', () => {
    const entries = [
      entry({
        id: 'a',
        tagSlot: 'date1',
        fieldType: 'date',
        operator: 'gte',
        value: '2026-01-01',
        valueTo: '2026-12-31',
      }),
    ]
    expect(projectTagFilters(entries)).toEqual([
      { tagSlot: 'date1', fieldType: 'date', operator: 'gte', value: '2026-01-01' },
    ])
  })

  it('counts active rows and builds chip labels', () => {
    const entries = [
      entry({ id: 'a', tagSlot: 'tag1', tagName: 'Author', value: 'Ada' }),
      entry({ id: 'b', tagSlot: '', value: 'x' }),
    ]
    expect(countActiveTagFilters(entries)).toBe(1)
    expect(getTagFilterLabel(entries[0])).toBe('Author: Ada')
  })
})
