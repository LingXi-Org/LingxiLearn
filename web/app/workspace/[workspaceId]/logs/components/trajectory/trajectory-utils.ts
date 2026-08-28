import type {
  Trajectory as ApiTrajectory,
  ExecutionTimelineSpan,
  TrajectoryItem,
} from '@/lib/api/contracts/logs'

export const TRAJECTORY_LANES = [
  { id: 'run', label: 'RUN' },
  { id: 'control', label: 'CONTROL ROUND' },
  { id: 'task', label: 'CAPABILITY TASK' },
  { id: 'action', label: 'ACTION' },
  { id: 'runtime', label: 'RUNTIME' },
  { id: 'state', label: 'STATE' },
  { id: 'resource', label: 'RESOURCE' },
  { id: 'output', label: 'OUTPUT' },
] as const
export type TrajectoryLaneId = (typeof TRAJECTORY_LANES)[number]['id']

export interface TrajectoryLane {
  id: TrajectoryLaneId
  label: string
  entries: TrajectoryEntry[]
}

export interface TrajectoryEntry {
  id: string
  sourceId: string
  span: ExecutionTimelineSpan
  depth: number
  path: number[]
  parentId: string | null
  parentIds: string[]
  startMs: number
  endMs: number
  durationMs: number
  offsetMs: number
  lane: TrajectoryLaneId
  precision: 'exact' | 'inferred'
  item?: TrajectoryItem
}

export interface TrajectoryModel {
  entries: TrajectoryEntry[]
  runStartMs: number
  runEndMs: number
  totalDurationMs: number
  maxDepth: number
  lanes: TrajectoryLane[]
  clockStartedAt?: string
  trajectorySummary?: Record<string, unknown>
  source: 'trajectory' | 'legacy'
}

export interface TrajectorySummary {
  spanCount: number
  maxDepth: number
  toolCount: number
  failureCount: number
  tokenCount: number
  roundCount?: number
  taskCount?: number
  actionCount?: number
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

function orderingValue(span: ExecutionTimelineSpan): number {
  return (
    parseTimestamp(span.startedAt) ??
    finiteNumber(span.relativeStartMs) ??
    finiteNumber(span.executionOrder) ??
    Number.POSITIVE_INFINITY
  )
}

/** Returns native child spans in execution order. */
export function getTrajectoryChildren(span: ExecutionTimelineSpan): ExecutionTimelineSpan[] {
  const children = [...(span.children ?? [])]
  return children.sort((left, right) => orderingValue(left) - orderingValue(right))
}

function collectAbsoluteStartTimes(spans: ExecutionTimelineSpan[]): number[] {
  const values: number[] = []
  const walk = (items: ExecutionTimelineSpan[]) => {
    for (const span of items) {
      const start = parseTimestamp(span.startedAt)
      if (start !== null) values.push(start)
      const children = getTrajectoryChildren(span)
      if (children.length > 0) walk(children)
    }
  }
  walk(spans)
  return values
}

function resolveDuration(span: ExecutionTimelineSpan, startMs: number): number {
  const explicit = finiteNumber(span.durationMs)
  if (explicit !== null) return Math.max(0, explicit)

  const end = parseTimestamp(span.endedAt)
  return end !== null ? Math.max(0, end - startMs) : 0
}

function laneForSpan(span: ExecutionTimelineSpan): TrajectoryLaneId {
  const value = `${span.kind} ${span.category ?? ''}`.toLowerCase()
  if (value.includes('workflow') || value.includes('run')) return 'run'
  if (value.includes('decision') || value.includes('control') || value.includes('agent'))
    return 'control'
  if (value.includes('runtime')) return 'runtime'
  if (value.includes('state')) return 'state'
  if (value.includes('resource')) return 'resource'
  if (value.includes('output')) return 'output'
  return 'action'
}

function laneForItem(item: TrajectoryItem): TrajectoryLaneId {
  return TRAJECTORY_LANES.some((lane) => lane.id === item.lane) ? item.lane : 'action'
}

function itemToSpan(item: TrajectoryItem): ExecutionTimelineSpan {
  const metadata = item.metadata ?? {}
  const tokenValue =
    metadata.tokens ??
    metadata.tokenCount ??
    metadata.token_count ??
    metadata.totalTokens ??
    metadata.total_tokens ??
    (metadata.usage as Record<string, unknown> | undefined)?.tokens
  return {
    id: item.id,
    name: item.label,
    kind: item.kind,
    status: item.status ?? 'running',
    startedAt: item.startTime,
    endedAt: item.endTime ?? item.startTime,
    durationMs: item.durationMs,
    relativeStartMs: item.relativeStartMs,
    input: metadata,
    ...(typeof tokenValue === 'number' || (tokenValue && typeof tokenValue === 'object')
      ? { tokens: tokenValue as ExecutionTimelineSpan['tokens'] }
      : {}),
    ...(item.spanId ? { spanId: item.spanId } : {}),
  }
}

function buildSemanticModel(
  trajectory: ApiTrajectory,
  fallbackDurationMs: number
): TrajectoryModel {
  const clockStart = parseTimestamp(trajectory.clock.startedAt) ?? 0
  const duration = Math.max(0, trajectory.clock.durationMs, fallbackDurationMs)
  const sourceEntries: Array<{
    item: TrajectoryItem
    lane: TrajectoryLaneId
    start: number
    end: number
    span: ExecutionTimelineSpan
    rawParentId: string | null
    sourceId: string
    id: string
  }> = []
  const seenIds = new Set<string>()
  const lanes: TrajectoryLane[] = TRAJECTORY_LANES.map(({ id, label }) => {
    const source = trajectory.lanes.find((lane) => lane.id === id)
    ;(source?.items ?? []).forEach((item, index) => {
      const start = parseTimestamp(item.startTime) ?? clockStart + Math.max(0, item.relativeStartMs)
      const itemDuration = Math.max(0, item.durationMs)
      const end = Math.max(start + itemDuration, parseTimestamp(item.endTime) ?? start)
      const _path = [index + 1]
      const span = itemToSpan(item)
      const sourceId = item.id
      // Backend semantic ids are stable; only disambiguate malformed payloads
      // that reuse one id in multiple lanes.
      let semanticId = sourceId
      if (seenIds.has(semanticId)) semanticId = `${sourceId}::${id}`
      seenIds.add(semanticId)
      sourceEntries.push({
        item,
        lane: laneForItem(item),
        start,
        end,
        span,
        rawParentId: item.parentId ?? null,
        sourceId,
        id: semanticId,
      })
    })
    return { id, label, entries: [] }
  })
  const entryBySourceId = new Map<string, (typeof sourceEntries)[number]>()
  for (const source of sourceEntries) {
    if (!entryBySourceId.has(source.sourceId)) entryBySourceId.set(source.sourceId, source)
  }
  const entryCache = new Map<string, TrajectoryEntry>()
  const materialize = (source: (typeof sourceEntries)[number], path: number[]): TrajectoryEntry => {
    const existing = entryCache.get(source.id)
    if (existing) return existing
    const parent = source.rawParentId ? entryBySourceId.get(source.rawParentId) : undefined
    const parentEntry = parent ? materialize(parent, [...path, 0]) : undefined
    const parentIds = parentEntry ? [...parentEntry.parentIds, parentEntry.id] : []
    const entry = {
      id: source.id,
      sourceId: source.sourceId,
      span: source.span,
      depth: parentEntry ? parentEntry.depth + 1 : 0,
      path,
      parentId: parentEntry?.id ?? null,
      parentIds,
      startMs: source.start,
      endMs: source.end,
      durationMs: Math.max(0, source.item.durationMs, source.end - source.start),
      offsetMs: Math.max(0, source.start - clockStart),
      lane: source.lane,
      precision: source.item.precision,
      item: source.item,
    } satisfies TrajectoryEntry
    entryCache.set(source.id, entry)
    return entry
  }
  sourceEntries.forEach((source, index) => materialize(source, [index + 1]))
  for (const lane of lanes) {
    lane.entries = sourceEntries
      .filter((source) => source.lane === lane.id)
      .map((source) => entryCache.get(source.id)!)
  }
  const entries = lanes.flatMap((lane) => lane.entries)
  return {
    entries,
    runStartMs: clockStart,
    runEndMs: clockStart + duration,
    totalDurationMs: duration,
    maxDepth: entries.reduce((deepest, entry) => Math.max(deepest, entry.depth + 1), 0),
    lanes,
    clockStartedAt: trajectory.clock.startedAt,
    trajectorySummary: trajectory.summary,
    source: 'trajectory',
  }
}

/**
 * Converts recursive execution spans into a stable, depth-first event ledger.
 * Absolute timestamps, relative offsets, and legacy records are normalized onto
 * one run-wide time axis so every nesting level can share the same scale.
 */
export function buildTrajectoryModel(
  spans: ExecutionTimelineSpan[] | undefined,
  fallbackDurationMs = 0,
  trajectory?: ApiTrajectory
): TrajectoryModel {
  if (trajectory) return buildSemanticModel(trajectory, fallbackDurationMs)
  if (!spans?.length) {
    const lanes = TRAJECTORY_LANES.map(({ id, label }) => ({
      id,
      label,
      entries: [],
    }))
    return {
      entries: [],
      runStartMs: 0,
      runEndMs: 0,
      totalDurationMs: Math.max(0, fallbackDurationMs),
      maxDepth: 0,
      lanes,
      source: 'legacy',
    }
  }

  const absoluteStarts = collectAbsoluteStartTimes(spans)
  const absoluteAnchor = absoluteStarts.length > 0 ? Math.min(...absoluteStarts) : 0
  const entries: TrajectoryEntry[] = []

  const walk = (
    items: ExecutionTimelineSpan[],
    depth: number,
    pathPrefix: number[],
    parentId: string | null,
    parentIds: string[],
    parentStartMs: number
  ) => {
    const sorted = [...items].sort((left, right) => orderingValue(left) - orderingValue(right))

    sorted.forEach((span, index) => {
      const path = [...pathPrefix, index + 1]
      const sourceId = span.id || `${span.kind || 'span'}-${path.join('-')}`
      const id = `${sourceId}::${path.join('.')}`
      const absoluteStart = parseTimestamp(span.startedAt)
      const relativeStart = finiteNumber(span.relativeStartMs)
      const startMs =
        absoluteStart ??
        (relativeStart !== null ? absoluteAnchor + relativeStart : parentStartMs || absoluteAnchor)
      const durationMs = resolveDuration(span, startMs)
      const absoluteEnd = parseTimestamp(span.endedAt)
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
        lane: laneForSpan(span),
        precision: 'inferred',
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

  const normalizedEntries = entries.map((entry) => ({
    ...entry,
    offsetMs: Math.max(0, entry.startMs - normalizedRunStart),
  }))
  const lanes = TRAJECTORY_LANES.map(({ id, label }) => ({
    id,
    label,
    entries: normalizedEntries.filter((entry) => entry.lane === id),
  }))

  return {
    entries: normalizedEntries,
    runStartMs: normalizedRunStart,
    runEndMs,
    totalDurationMs,
    maxDepth: entries.reduce((deepest, entry) => Math.max(deepest, entry.depth + 1), 0),
    lanes,
    source: 'legacy',
  }
}

export function getSpanTokenCount(span: ExecutionTimelineSpan): number {
  if (typeof span.tokens === 'number') return Math.max(0, span.tokens)
  if (!span.tokens) return 0
  return Math.max(0, span.tokens.total ?? (span.tokens.input ?? 0) + (span.tokens.output ?? 0))
}

function trajectorySummaryTokenCount(summary: Record<string, unknown> | undefined): number {
  if (!summary) return 0
  const raw =
    summary.tokens ??
    summary.tokenCount ??
    summary.token_count ??
    summary.totalTokens ??
    summary.total_tokens
  if (typeof raw === 'number' && Number.isFinite(raw)) return Math.max(0, raw)
  if (!raw || typeof raw !== 'object') return 0
  const value = raw as Record<string, unknown>
  const total = value.total ?? value.total_tokens
  if (typeof total === 'number' && Number.isFinite(total)) return Math.max(0, total)
  const input = Number(value.input ?? value.input_tokens ?? 0)
  const output = Number(value.output ?? value.output_tokens ?? 0)
  return Math.max(0, (Number.isFinite(input) ? input : 0) + (Number.isFinite(output) ? output : 0))
}

export function isTrajectoryError(span: ExecutionTimelineSpan): boolean {
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
  const semanticTokenCount = trajectorySummaryTokenCount(model.trajectorySummary)
  const tokenCount =
    semanticTokenCount > 0
      ? semanticTokenCount
      : rootTokenCount > 0
        ? rootTokenCount
        : leafEntries.reduce((total, entry) => total + getSpanTokenCount(entry.span), 0)
  const errorEntries = entries.filter((entry) => isTrajectoryError(entry.span))
  const errorAncestorIds = new Set(errorEntries.flatMap((entry) => entry.parentIds))
  const failureCount = errorEntries.filter((entry) => !errorAncestorIds.has(entry.id)).length

  const summary: TrajectorySummary = {
    spanCount: entries.length,
    maxDepth: model.maxDepth,
    toolCount: entries.filter((entry) => entry.span.kind.toLowerCase() === 'tool').length,
    failureCount,
    tokenCount,
  }
  if (model.source === 'trajectory') {
    summary.roundCount =
      model.lanes
        .find((lane) => lane.id === 'control')
        ?.entries.filter((entry) => entry.item?.kind === 'round').length ?? 0
    summary.taskCount = model.lanes.find((lane) => lane.id === 'task')?.entries.length ?? 0
    summary.actionCount = model.lanes.find((lane) => lane.id === 'action')?.entries.length ?? 0
  }
  return summary
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
  return [
    entry.span.name,
    entry.span.kind,
    entry.span.status,
    entry.span.errorType,
    entry.span.errorMessage,
    entry.span.model,
    entry.span.provider,
    entry.lane,
    entry.item?.roundStep,
    searchValue(entry.item?.metadata),
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
    const matchesType = !hasTypeFilter || entry.span.kind.toLowerCase() === normalizedType
    if (!matchesSearch || !matchesType) continue
    matchingIds.add(entry.id)
    entry.parentIds.forEach((id) => matchingIds.add(id))
  }

  return entries.filter(
    (entry) => matchingIds.has(entry.id) && !entry.parentIds.some((id) => collapsedIds.has(id))
  )
}

export function getTrajectoryTypes(entries: TrajectoryEntry[]): string[] {
  return Array.from(new Set(entries.map((entry) => entry.span.kind).filter(Boolean))).sort((a, b) =>
    a.localeCompare(b)
  )
}
