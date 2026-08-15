import type { LogTraceSpan } from '@/lib/api/contracts/logs'

export interface TrajectoryEntry {
  id: string
  sourceId: string
  span: LogTraceSpan
  depth: number
  path: number[]
  parentId: string | null
  parentIds: string[]
  startMs: number
  endMs: number
  durationMs: number
  offsetMs: number
}

export interface TrajectoryModel {
  entries: TrajectoryEntry[]
  runStartMs: number
  runEndMs: number
  totalDurationMs: number
  maxDepth: number
}

export interface TrajectorySummary {
  spanCount: number
  maxDepth: number
  toolCount: number
  failureCount: number
  tokenCount: number
}

interface VisibleEntryOptions {
  searchQuery: string
  type: string
  collapsedIds: ReadonlySet<string>
}

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function parseTimestamp(value: string | undefined): number | null {
  if (!value) return null
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : null
}

function spanRecord(span: LogTraceSpan): Record<string, unknown> {
  return span as unknown as Record<string, unknown>
}

function orderingValue(span: LogTraceSpan): number {
  return (
    parseTimestamp(span.startTime) ??
    finiteNumber(span.relativeStartMs) ??
    finiteNumber(spanRecord(span).executionOrder) ??
    Number.POSITIVE_INFINITY
  )
}

/**
 * Returns persisted children plus legacy tool-call records projected as child spans.
 */
export function getTrajectoryChildren(span: LogTraceSpan): LogTraceSpan[] {
  const children = span.children?.length
    ? [...span.children]
    : (span.toolCalls ?? []).map((toolCall, index) => ({
        id: toolCall.id ?? `${span.id}-tool-${index}`,
        name: toolCall.name ?? 'Tool call',
        type: 'tool',
        durationMs: finiteNumber(toolCall.duration) ?? 0,
        startTime: toolCall.startTime,
        endTime: toolCall.endTime,
        status: toolCall.error ? 'error' : 'success',
        errorMessage: toolCall.error,
        input: toolCall.arguments,
        output: toolCall.result,
      }))

  return children.sort((left, right) => orderingValue(left) - orderingValue(right))
}

function collectAbsoluteStartTimes(spans: LogTraceSpan[]): number[] {
  const values: number[] = []
  const walk = (items: LogTraceSpan[]) => {
    for (const span of items) {
      const start = parseTimestamp(span.startTime)
      if (start !== null) values.push(start)
      const children = getTrajectoryChildren(span)
      if (children.length > 0) walk(children)
    }
  }
  walk(spans)
  return values
}

function resolveDuration(span: LogTraceSpan, startMs: number): number {
  const explicit = finiteNumber(span.durationMs) ?? finiteNumber(span.duration)
  if (explicit !== null) return Math.max(0, explicit)

  const end = parseTimestamp(span.endTime)
  return end !== null ? Math.max(0, end - startMs) : 0
}

/**
 * Converts recursive execution spans into a stable, depth-first event ledger.
 * Absolute timestamps, relative offsets, and legacy records are normalized onto
 * one run-wide time axis so every nesting level can share the same scale.
 */
export function buildTrajectoryModel(
  spans: LogTraceSpan[] | undefined,
  fallbackDurationMs = 0
): TrajectoryModel {
  if (!spans?.length) {
    return {
      entries: [],
      runStartMs: 0,
      runEndMs: 0,
      totalDurationMs: Math.max(0, fallbackDurationMs),
      maxDepth: 0,
    }
  }

  const absoluteStarts = collectAbsoluteStartTimes(spans)
  const absoluteAnchor = absoluteStarts.length > 0 ? Math.min(...absoluteStarts) : 0
  const entries: TrajectoryEntry[] = []

  const walk = (
    items: LogTraceSpan[],
    depth: number,
    pathPrefix: number[],
    parentId: string | null,
    parentIds: string[],
    parentStartMs: number
  ) => {
    const sorted = [...items].sort((left, right) => orderingValue(left) - orderingValue(right))

    sorted.forEach((span, index) => {
      const path = [...pathPrefix, index + 1]
      const sourceId = span.id || `${span.type || 'span'}-${path.join('-')}`
      const id = `${sourceId}::${path.join('.')}`
      const absoluteStart = parseTimestamp(span.startTime)
      const relativeStart = finiteNumber(span.relativeStartMs)
      const startMs =
        absoluteStart ??
        (relativeStart !== null ? absoluteAnchor + relativeStart : parentStartMs || absoluteAnchor)
      const durationMs = resolveDuration(span, startMs)
      const absoluteEnd = parseTimestamp(span.endTime)
      const endMs = Math.max(startMs + durationMs, absoluteEnd ?? startMs)

      entries.push({
        id,
        sourceId,
        span,
        depth,
        path,
        parentId,
        parentIds,
        startMs,
        endMs,
        durationMs: Math.max(durationMs, endMs - startMs),
        offsetMs: 0,
      })

      const children = getTrajectoryChildren(span)
      if (children.length > 0) {
        walk(children, depth + 1, path, id, [...parentIds, id], startMs)
      }
    })
  }

  walk(spans, 0, [], null, [], absoluteAnchor)

  const runStartMs = entries.reduce(
    (earliest, entry) => Math.min(earliest, entry.startMs),
    Number.POSITIVE_INFINITY
  )
  const normalizedRunStart = Number.isFinite(runStartMs) ? runStartMs : 0
  const tracedRunEnd = entries.reduce(
    (latest, entry) => Math.max(latest, entry.endMs),
    normalizedRunStart
  )
  const totalDurationMs = Math.max(0, fallbackDurationMs, tracedRunEnd - normalizedRunStart)
  const runEndMs = normalizedRunStart + totalDurationMs

  return {
    entries: entries.map((entry) => ({
      ...entry,
      offsetMs: Math.max(0, entry.startMs - normalizedRunStart),
    })),
    runStartMs: normalizedRunStart,
    runEndMs,
    totalDurationMs,
    maxDepth: entries.reduce((deepest, entry) => Math.max(deepest, entry.depth + 1), 0),
  }
}

export function getSpanTokenCount(span: LogTraceSpan): number {
  if (typeof span.tokens === 'number') return Math.max(0, span.tokens)
  if (!span.tokens) return 0
  return Math.max(0, span.tokens.total ?? (span.tokens.input ?? 0) + (span.tokens.output ?? 0))
}

export function isTrajectoryError(span: LogTraceSpan): boolean {
  const status = span.status?.toLowerCase()
  return status === 'error' || status === 'failed' || Boolean(span.errorMessage)
}

/** Returns run-level counters without double-counting propagated parent totals/errors. */
export function summarizeTrajectory(model: TrajectoryModel): TrajectorySummary {
  const { entries } = model
  const rootEntries = entries.filter((entry) => entry.depth === 0)
  const parentIds = new Set(entries.map((entry) => entry.parentId).filter(Boolean))
  const rootTokenCount = rootEntries.reduce(
    (total, entry) => total + getSpanTokenCount(entry.span),
    0
  )
  const leafEntries = entries.filter((entry) => !parentIds.has(entry.id))
  const tokenCount =
    rootTokenCount > 0
      ? rootTokenCount
      : leafEntries.reduce((total, entry) => total + getSpanTokenCount(entry.span), 0)
  const errorEntries = entries.filter((entry) => isTrajectoryError(entry.span))
  const errorAncestorIds = new Set(errorEntries.flatMap((entry) => entry.parentIds))
  const failureCount = errorEntries.filter((entry) => !errorAncestorIds.has(entry.id)).length

  return {
    spanCount: entries.length,
    maxDepth: model.maxDepth,
    toolCount: entries.filter((entry) => entry.span.type.toLowerCase() === 'tool').length,
    failureCount,
    tokenCount,
  }
}

function searchValue(value: unknown): string {
  if (value === undefined || value === null) return ''
  if (typeof value === 'string') return value
  try {
    return (JSON.stringify(value) ?? String(value)).slice(0, 10_000)
  } catch {
    return String(value)
  }
}

function entrySearchText(entry: TrajectoryEntry): string {
  const richSpan = spanRecord(entry.span)
  return [
    entry.span.name,
    entry.span.type,
    entry.span.status,
    entry.span.errorType,
    entry.span.errorMessage,
    richSpan.model,
    richSpan.provider,
    searchValue(entry.span.input),
    searchValue(entry.span.output),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

/**
 * Filters the ledger while retaining every ancestor needed to understand a
 * matching nested span. Collapsed branches are removed after matching.
 */
export function getVisibleTrajectoryEntries(
  entries: TrajectoryEntry[],
  { searchQuery, type, collapsedIds }: VisibleEntryOptions
): TrajectoryEntry[] {
  const needle = searchQuery.trim().toLowerCase()
  const normalizedType = type.trim().toLowerCase()
  const hasTypeFilter = normalizedType !== '' && normalizedType !== 'all'
  const matchingIds = new Set<string>()

  for (const entry of entries) {
    const matchesSearch = !needle || entrySearchText(entry).includes(needle)
    const matchesType = !hasTypeFilter || entry.span.type.toLowerCase() === normalizedType
    if (!matchesSearch || !matchesType) continue
    matchingIds.add(entry.id)
    entry.parentIds.forEach((id) => matchingIds.add(id))
  }

  return entries.filter(
    (entry) => matchingIds.has(entry.id) && !entry.parentIds.some((id) => collapsedIds.has(id))
  )
}

export function getTrajectoryTypes(entries: TrajectoryEntry[]): string[] {
  return Array.from(new Set(entries.map((entry) => entry.span.type).filter(Boolean))).sort((a, b) =>
    a.localeCompare(b)
  )
}
