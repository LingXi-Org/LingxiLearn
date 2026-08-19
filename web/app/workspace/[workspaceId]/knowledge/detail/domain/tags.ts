/**
 * Knowledge detail tag domain primitives.
 *
 * Shared source of truth for the knowledge-base detail (document list rows +
 * tag filter panel) and the document detail (tags modal) so both sides map,
 * normalize, and format tag values identically instead of carrying a private
 * copy each.
 *
 * Pure functions only — no React, no query client, no URL state.
 */

import { formatDate } from '@sim/utils/formatting'
import { format } from 'date-fns'
import { ALL_TAG_SLOTS, type AllTagSlot, getFieldTypeForSlot } from '@/lib/knowledge/constants'
import {
  type FilterFieldType,
  getOperatorsForFieldType,
  type OperatorInfo,
} from '@/lib/knowledge/filters/types'
import type { DocumentTag } from '@/lib/knowledge/tags/types'
import type { DocumentData } from '@/lib/knowledge/types'

/**
 * Minimal structural contract the tag domain needs from a tag definition.
 * Satisfied by the query layer's `TagDefinition`; keeping it structural stops
 * the domain from depending on the hooks layer.
 */
export interface TagDefinitionShape {
  tagSlot: string
  displayName: string
  fieldType: string
}

/** A document tag rendered in the base detail document table. */
export interface DocumentTagValue {
  slot: AllTagSlot
  displayName: string
  value: string
}

/**
 * Format a raw slot value for the document-list tags cell. Dates render as
 * `MMM d, yyyy`, booleans as Yes/No, numbers localized; anything else is
 * stringified as-is.
 */
export function formatTagValueForList(raw: unknown, fieldType: string): string {
  if (fieldType === 'date') {
    try {
      return format(new Date(raw as string), 'MMM d, yyyy')
    } catch {
      return String(raw)
    }
  }
  if (fieldType === 'boolean') {
    return raw ? 'Yes' : 'No'
  }
  if (fieldType === 'number' && typeof raw === 'number') {
    return raw.toLocaleString()
  }
  return String(raw)
}

/**
 * Project a document's raw slot columns into display-ready tag values for the
 * list. Definitions are optional here: a slot without one falls back to the
 * slot-derived field type and the raw slot name, so an orphaned value still
 * renders instead of disappearing silently.
 */
export function getDocumentTagValues(
  doc: DocumentData,
  definitions: readonly TagDefinitionShape[]
): DocumentTagValue[] {
  const defsBySlot = new Map(definitions.map((d) => [d.tagSlot, d]))
  const result: DocumentTagValue[] = []

  for (const slot of ALL_TAG_SLOTS) {
    const raw = doc[slot]
    if (raw == null) continue

    const def = defsBySlot.get(slot)
    const fieldType = def?.fieldType || getFieldTypeForSlot(slot) || 'text'
    const value = formatTagValueForList(raw, fieldType)
    if (value) {
      result.push({ slot, displayName: def?.displayName || slot, value })
    }
  }

  return result
}

/**
 * Format a saved string value for the tags modal's existing-tag rows. Dates
 * arrive either as `YYYY-MM-DD` (rendered as a local calendar date) or as a
 * UTC timestamp (rendered from its UTC components so the displayed day does
 * not shift with the viewer's timezone).
 */
export function formatTagValueForModal(value: string, fieldType: string): string {
  if (!value) return ''
  switch (fieldType) {
    case 'boolean':
      return value === 'true' ? 'True' : 'False'
    case 'date': {
      try {
        const date = new Date(value)
        if (Number.isNaN(date.getTime())) return value
        if (value.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(value)) {
          return formatDate(new Date(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()))
        }
        return formatDate(date)
      } catch {
        return value
      }
    }
    default:
      return value
  }
}

/**
 * Rebuild the editable tag list of a document from its raw slot columns.
 * Editing works on definition+value pairs, so a slot without a definition is
 * skipped — unlike the list projection, which tolerates orphans.
 */
export function buildDocumentTags(
  docData: DocumentData,
  definitions: readonly TagDefinitionShape[]
): DocumentTag[] {
  const tags: DocumentTag[] = []

  for (const slot of ALL_TAG_SLOTS) {
    const rawValue = docData[slot]
    const definition = definitions.find((def) => def.tagSlot === slot)

    if (rawValue !== null && rawValue !== undefined && definition) {
      const stringValue = String(rawValue).trim()
      if (stringValue) {
        tags.push({
          slot,
          displayName: definition.displayName,
          fieldType: definition.fieldType,
          value: stringValue,
        })
      }
    }
  }

  return tags
}

/**
 * Build the `slot -> value` write payload for saving a document's tags. Every
 * slot is present; a tag without a value clears the slot with an empty string.
 */
export function buildTagSlotPayload(tags: readonly DocumentTag[]): Record<string, string> {
  const payload: Record<string, string> = {}
  for (const slot of ALL_TAG_SLOTS) {
    const tag = tags.find((t) => t.slot === slot)
    payload[slot] = tag?.value.trim() ? tag.value.trim() : ''
  }
  return payload
}

/**
 * Value carried over when the field type changes in the tag editor: kept when
 * the type is unchanged, cleared otherwise so the placeholder can show.
 */
export function getValueForFieldTypeChange(
  newFieldType: string,
  currentFieldType: string,
  currentValue: string
): string {
  return newFieldType === currentFieldType ? currentValue : ''
}

/**
 * Case-insensitive display-name conflict check across a document's tags,
 * ignoring the row currently being edited.
 */
export function hasTagNameConflict(
  tags: readonly DocumentTag[],
  name: string,
  editingIndex: number | null
): boolean {
  if (!name.trim()) return false
  return tags.some((tag, index) => {
    if (editingIndex !== null && index === editingIndex) return false
    return tag.displayName.toLowerCase() === name.trim().toLowerCase()
  })
}

/** Tag definitions still available to attach (not already used by the document). */
export function getAvailableTagDefinitions(
  definitions: readonly TagDefinitionShape[],
  tags: readonly DocumentTag[]
): TagDefinitionShape[] {
  return definitions.filter(
    (def) => !tags.some((tag) => tag.displayName.toLowerCase() === def.displayName.toLowerCase())
  )
}

/** One editable tag-filter row in the base detail filter panel. */
export interface TagFilterEntry {
  id: string
  tagName: string
  tagSlot: string
  fieldType: FilterFieldType
  operator: string
  value: string
  valueTo: string
}

/**
 * Create an empty filter row. The id is injected so this stays pure; callers
 * pass `generateId()`.
 */
export function createTagFilterEntry(id: string): TagFilterEntry {
  return {
    id,
    tagName: '',
    tagSlot: '',
    fieldType: 'text',
    operator: 'contains',
    value: '',
    valueTo: '',
  }
}

/**
 * Default operator when a tag is selected. Text filters default to `contains`
 * so typing part of a value finds matches (exact `equals` stays one click away
 * in the operator dropdown); other field types keep their first, equality
 * operator.
 */
export function getDefaultOperatorForFieldType(
  fieldType: FilterFieldType,
  operators: readonly OperatorInfo[]
): string {
  if (fieldType === 'text') return 'contains'
  return operators[0]?.value ?? 'eq'
}

/**
 * Resolve a filter row's tag selection to its definition-derived fields
 * (slot + field type + default operator), clearing any entered values.
 */
export function resolveTagFilterSelection(
  definitions: readonly TagDefinitionShape[],
  tagName: string
): Pick<TagFilterEntry, 'tagName' | 'tagSlot' | 'fieldType' | 'operator' | 'value' | 'valueTo'> {
  const def = definitions.find((t) => t.displayName === tagName)
  const fieldType = (def?.fieldType || 'text') as FilterFieldType
  return {
    tagName,
    tagSlot: def?.tagSlot || '',
    fieldType,
    operator: getDefaultOperatorForFieldType(fieldType, getOperatorsForFieldType(fieldType)),
    value: '',
    valueTo: '',
  }
}

/**
 * Wire projection of the editable rows toward the documents query. Structural
 * mirror of the query layer's `DocumentTagFilter` — kept structural so the
 * domain does not import the API contract layer.
 */
export interface ProjectedTagFilter {
  tagSlot: string
  fieldType: FilterFieldType
  operator: string
  value: string
  valueTo?: string
}

/**
 * Project editable rows into query filters. Rows without a slot or value are
 * dropped; a `between` filter applies only once both bounds are set — sending
 * it with just the lower bound would be rejected at the API boundary and break
 * the whole list while the user is still entering the range.
 */
export function projectTagFilters(entries: readonly TagFilterEntry[]): ProjectedTagFilter[] {
  return entries.reduce<ProjectedTagFilter[]>((acc, entry) => {
    if (!entry.tagSlot || !entry.value.trim()) return acc
    if (entry.operator === 'between' && !entry.valueTo.trim()) return acc
    acc.push({
      tagSlot: entry.tagSlot,
      fieldType: entry.fieldType,
      operator: entry.operator,
      value: entry.value,
      ...(entry.operator === 'between' ? { valueTo: entry.valueTo } : {}),
    })
    return acc
  }, [])
}

/** Rows that actively filter (slot chosen + value present). */
export function countActiveTagFilters(entries: readonly TagFilterEntry[]): number {
  return entries.filter((entry) => entry.tagSlot && entry.value.trim()).length
}

/** `Tag name: value` chip label for an active filter row. */
export function getTagFilterLabel(entry: TagFilterEntry): string {
  return `${entry.tagName}: ${entry.value}`
}
