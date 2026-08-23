'use client'

import {
  type KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  Badge,
  Button,
  ChipCombobox,
  ChipInput,
  CollapsibleCard,
  cn,
  Loader,
  Tooltip,
} from '@/components/ui-kit'
import {
  ChevronDown,
  ChevronsDownUp,
  ChevronsUpDown,
  Clock,
  Search,
  Workflow,
  Wrench,
} from '@/components/ui-kit/icons'
import { useParams } from 'next/navigation'
import type { LogTraceSpan } from '@/lib/api/contracts/logs'
import type { TraceSpan } from '@/lib/logs/types'
import { formatDuration } from '@/lib/utils/formatting'
import {
  adjustBgForContrast,
  formatCostAmount,
  getDisplayName,
  iconColorClass,
} from '@/app/workspace/[workspaceId]/logs/components/log-details/utils'
import type {
  ExecutionLogDetailView,
  ExecutionLogSummaryView,
  RunStatus,
} from '@/app/workspace/[workspaceId]/logs/model/execution-log'
import { mapExecutionLogDetail } from '@/app/workspace/[workspaceId]/logs/model/execution-log-mapper'
import { getSpanPresentation } from '@/app/workspace/[workspaceId]/logs/model/span-presentation'
import { useLogDetail } from '@/hooks/queries/logs'
import {
  buildTrajectoryModel,
  getSpanTokenCount,
  getTrajectoryTypes,
  getVisibleTrajectoryEntries,
  isTrajectoryError,
  summarizeTrajectory,
  type TrajectoryEntry,
  type TrajectoryModel,
} from './trajectory-utils'

const ACTIVE_RUN_REFRESH_MS = 3_000
const EMPTY_COLLAPSED_IDS = new Set<string>()
const DETAIL_PREVIEW_LIMIT = 20_000

interface TrajectoryProps {
  logs: ExecutionLogSummaryView[]
  isLoading: boolean
}

function asTraceSpan(span: LogTraceSpan): TraceSpan {
  return span as unknown as TraceSpan
}

function getSpanName(span: LogTraceSpan): string {
  return getDisplayName(asTraceSpan(span))
}

function getSpanVisual(span: LogTraceSpan) {
  const richSpan = asTraceSpan(span)
  const presentation = getSpanPresentation(
    span.type,
    span.name,
    typeof richSpan.provider === 'string' ? richSpan.provider : undefined
  )
  return {
    ...presentation,
    bgColor: adjustBgForContrast(presentation.bgColor),
  }
}

function formatMs(value: number): string {
  return formatDuration(Math.max(0, value), { precision: 2 }) ?? '—'
}

function formatOffset(value: number): string {
  return value <= 0 ? '0 ms' : `+${formatMs(value)}`
}

function getRunLabel(log: ExecutionLogSummaryView): string {
  const date = new Date(log.createdAt)
  const timestamp = Number.isFinite(date.getTime())
    ? date.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : log.createdAt
  return `${log.source.title} · ${timestamp}`
}

function getRunBadge(status: RunStatus | null) {
  switch (status) {
    case 'error':
      return { label: 'Error', variant: 'red' as const }
    case 'running':
      return { label: 'Running', variant: 'amber' as const }
    case 'pending':
    case 'redacting':
      return { label: 'Pending', variant: 'amber' as const }
    case 'cancelled':
    case 'cancelling':
      return { label: 'Cancelled', variant: 'orange' as const }
    default:
      return { label: 'Success', variant: 'green' as const }
  }
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className='min-w-0 rounded-md bg-[var(--surface-2)] px-3 py-2.5 dark:bg-[var(--surface-1)]'>
      <div className='truncate text-[var(--text-muted)] text-xs uppercase tracking-[0.08em]'>
        {label}
      </div>
      <div className='mt-1 truncate text-[var(--text-primary)] text-sm tabular-nums'>{value}</div>
    </div>
  )
}

function TrajectorySummaryCards({ model }: { model: TrajectoryModel }) {
  const summary = useMemo(() => summarizeTrajectory(model), [model])
  const cards = [
    {
      label: 'Rounds',
      value: String(
        summary.roundCount ?? model.lanes.find((lane) => lane.id === 'control')?.entries.length ?? 0
      ),
    },
    {
      label: 'Tasks',
      value: String(
        summary.taskCount ?? model.lanes.find((lane) => lane.id === 'task')?.entries.length ?? 0
      ),
    },
    {
      label: 'Actions',
      value: String(
        summary.actionCount ??
          model.lanes.find((lane) => lane.id === 'action')?.entries.length ??
          summary.spanCount
      ),
    },
    { label: 'Failures', value: String(summary.failureCount) },
    { label: 'Tokens', value: summary.tokenCount.toLocaleString() },
    { label: 'Duration', value: formatMs(model.totalDurationMs) },
  ]

  return (
    <div className='grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6'>
      {cards.map((card) => (
        <StatCard key={card.label} label={card.label} value={card.value} />
      ))}
    </div>
  )
}

function TimelineBar({
  entry,
  totalDurationMs,
  selected,
  onSelect,
}: {
  entry: TrajectoryEntry
  totalDurationMs: number
  selected: boolean
  onSelect: (entry: TrajectoryEntry) => void
}) {
  const { bgColor } = getSpanVisual(entry.span)
  const scale = Math.max(1, totalDurationMs)
  const left = Math.min(100, (entry.offsetMs / scale) * 100)
  const width = Math.max(0, Math.min(100 - left, (entry.durationMs / scale) * 100))
  const hasError = isTrajectoryError(entry.span)

  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button
          type='button'
          aria-label={`Inspect ${getSpanName(entry.span)}`}
          className={cn(
            'absolute top-1/2 h-3 -translate-y-1/2 rounded-sm border transition-[filter,box-shadow] hover:brightness-110',
            selected
              ? 'border-[var(--text-primary)] shadow-[0_0_0_1px_var(--surface-1)]'
              : 'border-transparent'
          )}
          style={{
            left: `${left}%`,
            width: `max(4px, ${width}%)`,
            backgroundColor: hasError ? 'var(--text-error)' : bgColor,
          }}
          onClick={() => onSelect(entry)}
        />
      </Tooltip.Trigger>
      <Tooltip.Content side='top' className='max-w-[320px]'>
        <div className='flex flex-col gap-0.5'>
          <span>
            {entry.path.join('.')} · {getSpanName(entry.span)}
          </span>
          <span className='text-[var(--text-tertiary)] text-caption'>
            {formatOffset(entry.offsetMs)} · {formatMs(entry.durationMs)}
          </span>
        </div>
      </Tooltip.Content>
    </Tooltip.Root>
  )
}

function TrajectoryTimeline({
  model,
  selectedId,
  onSelect,
}: {
  model: TrajectoryModel
  selectedId: string | null
  onSelect: (entry: TrajectoryEntry) => void
}) {
  return (
    <section className='rounded-md border border-[var(--border)] bg-[var(--surface-1)]'>
      <div className='flex items-center justify-between border-[var(--border)] border-b px-3.5 py-2.5'>
        <div className='flex min-w-0 items-center gap-2'>
          <Clock className='size-[14px] flex-shrink-0 text-[var(--text-icon)]' />
          <span className='truncate text-[var(--text-primary)] text-sm'>Timing overview</span>
          <span className='hidden text-[var(--text-tertiary)] text-caption sm:inline'>
            All lanes share one execution clock
          </span>
        </div>
      </div>
      <div className='overflow-x-auto px-3.5 pt-3 pb-2.5'>
        <div className='min-w-[640px]'>
          <div className='rounded-md border border-[var(--border)] bg-[var(--surface-2)] py-1.5'>
            {model.lanes.map((lane) => (
              <div key={lane.id} className='flex h-7 items-center'>
                <span className='w-32 flex-shrink-0 pr-2 text-right text-[var(--text-muted)] text-[10px] uppercase tracking-[0.04em]'>
                  {lane.label}
                </span>
                <div
                  className='relative mr-2 h-full min-w-0 flex-1 border-[var(--border)] border-l'
                  style={{
                    backgroundImage:
                      'linear-gradient(to right, var(--border) 1px, transparent 1px)',
                    backgroundSize: '20% 100%',
                  }}
                >
                  {lane.entries.map((entry) => (
                    <TimelineBar
                      key={entry.id}
                      entry={entry}
                      totalDurationMs={model.totalDurationMs}
                      selected={selectedId === entry.id}
                      onSelect={onSelect}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className='mt-1.5 flex items-center justify-between pl-32 text-[var(--text-muted)] text-xs tabular-nums'>
            <span>0 ms</span>
            <span>{formatOffset(model.totalDurationMs / 2)}</span>
            <span>{formatOffset(model.totalDurationMs)}</span>
          </div>
        </div>
      </div>
    </section>
  )
}

function SpanIcon({ span }: { span: LogTraceSpan }) {
  const { icon: Icon, bgColor } = getSpanVisual(span)
  return (
    <div
      className='flex size-[16px] flex-shrink-0 items-center justify-center overflow-hidden rounded-sm [&_img]:size-full'
      style={{ backgroundColor: bgColor }}
    >
      {Icon ? <Icon className={cn('size-[11px]', iconColorClass(bgColor))} /> : null}
    </div>
  )
}

function typeBadgeVariant(type: string) {
  switch (type.toLowerCase()) {
    case 'tool':
      return 'orange' as const
    case 'model':
    case 'agent':
      return 'purple' as const
    case 'workflow':
      return 'blue-secondary' as const
    case 'loop':
    case 'parallel':
    case 'iteration':
      return 'teal' as const
    default:
      return 'gray-secondary' as const
  }
}

function TrajectoryLedger({
  entries,
  childIds,
  collapsedIds,
  selectedId,
  onToggle,
  onSelect,
}: {
  entries: TrajectoryEntry[]
  childIds: ReadonlySet<string>
  collapsedIds: ReadonlySet<string>
  selectedId: string | null
  onToggle: (id: string) => void
  onSelect: (entry: TrajectoryEntry) => void
}) {
  const handleKeyDown = (event: ReactKeyboardEvent, entry: TrajectoryEntry, index: number) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(entry)
      return
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    event.preventDefault()
    const nextIndex = event.key === 'ArrowDown' ? index + 1 : index - 1
    const next = entries[nextIndex]
    if (!next) return
    onSelect(next)
    document.querySelector<HTMLElement>(`[data-trajectory-id="${CSS.escape(next.id)}"]`)?.focus()
  }

  if (entries.length === 0) {
    return (
      <div className='flex min-h-[240px] items-center justify-center px-4 text-center text-[var(--text-tertiary)] text-sm'>
        No matching spans
      </div>
    )
  }

  return (
    <div className='h-full overflow-auto'>
      <table className='w-full min-w-[680px] table-fixed border-collapse'>
        <thead className='sticky top-0 z-[1] bg-[var(--surface-2)]'>
          <tr className='border-[var(--border)] border-b text-left text-[var(--text-muted)] text-xs'>
            <th className='w-[124px] px-3 py-2'>Lane</th>
            <th className='px-2 py-2'>Stage</th>
            <th className='w-[112px] px-2 py-2'>Type</th>
            <th className='w-[92px] px-2 py-2 text-right'>Start</th>
            <th className='w-[92px] px-3 py-2 text-right'>Duration</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry, index) => {
            const canExpand = childIds.has(entry.id)
            const isCollapsed = collapsedIds.has(entry.id)
            const hasError = isTrajectoryError(entry.span)
            return (
              <tr
                key={entry.id}
                data-trajectory-id={entry.id}
                tabIndex={selectedId === entry.id ? 0 : -1}
                aria-selected={selectedId === entry.id}
                className={cn(
                  'cursor-pointer border-[var(--border)] border-b text-sm outline-none transition-colors last:border-b-0 hover-hover:bg-[var(--surface-2)] focus-visible:bg-[var(--surface-3)]',
                  selectedId === entry.id && 'bg-[var(--surface-3)]'
                )}
                onClick={() => onSelect(entry)}
                onKeyDown={(event) => handleKeyDown(event, entry, index)}
              >
                <td className='px-3 py-2 font-mono text-[var(--text-tertiary)] text-xs uppercase tracking-[0.04em]'>
                  {entry.lane.toUpperCase()}
                  {entry.item?.roundStep != null ? ` · step ${entry.item.roundStep}` : ''}
                </td>
                <td className='min-w-0 px-2 py-2'>
                  <div
                    className='flex min-w-0 items-center gap-1.5'
                    style={{ paddingLeft: entry.depth * 16 }}
                  >
                    {canExpand ? (
                      <Button
                        type='button'
                        variant='ghost'
                        className='size-[16px] flex-shrink-0 p-0 text-[var(--text-tertiary)]'
                        aria-label={isCollapsed ? 'Expand span' : 'Collapse span'}
                        onClick={(event) => {
                          event.stopPropagation()
                          onToggle(entry.id)
                        }}
                      >
                        <ChevronDown
                          className={cn(
                            'size-[11px] transition-transform',
                            isCollapsed && '-rotate-90'
                          )}
                        />
                      </Button>
                    ) : (
                      <span className='size-[16px] flex-shrink-0' />
                    )}
                    <SpanIcon span={entry.span} />
                    <span
                      className={cn(
                        'truncate',
                        hasError ? 'text-[var(--text-error)]' : 'text-[var(--text-primary)]'
                      )}
                    >
                      {getSpanName(entry.span)}
                    </span>
                    {entry.item?.roundStep != null ? (
                      <span className='ml-1 flex-shrink-0 text-[var(--text-tertiary)] text-caption'>
                        Step {entry.item.roundStep}
                      </span>
                    ) : null}
                  </div>
                </td>
                <td className='px-2 py-2'>
                  <Badge
                    variant={typeBadgeVariant(entry.span.type)}
                    size='sm'
                    className='max-w-full'
                  >
                    <span className='truncate'>{entry.span.type}</span>
                  </Badge>
                </td>
                <td className='px-2 py-2 text-right text-[var(--text-secondary)] text-caption tabular-nums'>
                  {formatOffset(entry.offsetMs)}
                </td>
                <td className='px-3 py-2 text-right text-[var(--text-secondary)] text-caption tabular-nums'>
                  {formatMs(entry.durationMs)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function previewValue(value: unknown): string {
  let serialized: string
  if (typeof value === 'string') serialized = value
  else {
    try {
      serialized = JSON.stringify(value, null, 2) ?? String(value)
    } catch {
      serialized = String(value)
    }
  }
  if (serialized.length <= DETAIL_PREVIEW_LIMIT) return serialized
  return `${serialized.slice(0, DETAIL_PREVIEW_LIMIT)}\n… output truncated in viewer`
}

function DetailCard({
  title,
  value,
  defaultOpen = false,
  error = false,
}: {
  title: string
  value: unknown
  defaultOpen?: boolean
  error?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  if (value === undefined || value === null || value === '') return null

  return (
    <CollapsibleCard
      title={title}
      badge={
        error ? (
          <Badge variant='red' size='sm'>
            Error
          </Badge>
        ) : undefined
      }
      collapsed={!open}
      onToggleCollapse={() => setOpen((current) => !current)}
    >
      <pre
        className={cn(
          'max-h-[280px] overflow-auto whitespace-pre-wrap break-words rounded-sm bg-[var(--surface-1)] p-2 font-mono text-xs',
          error ? 'text-[var(--text-error)]' : 'text-[var(--text-secondary)]'
        )}
      >
        {previewValue(value)}
      </pre>
    </CollapsibleCard>
  )
}

function InspectorMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className='min-w-0 rounded-md bg-[var(--surface-2)] px-2.5 py-2'>
      <div className='truncate text-[var(--text-muted)] text-xs uppercase tracking-[0.06em]'>
        {label}
      </div>
      <div className='mt-0.5 truncate text-[var(--text-primary)] text-caption tabular-nums'>
        {value}
      </div>
    </div>
  )
}

function TrajectoryInspector({ entry }: { entry: TrajectoryEntry | null }) {
  const [activeTab, setActiveTab] = useState<'overview' | 'input' | 'output' | 'timing'>('overview')

  if (!entry) {
    return (
      <div className='flex h-full min-h-[240px] items-center justify-center px-4 text-center text-[var(--text-tertiary)] text-sm'>
        Select a span to inspect its details
      </div>
    )
  }

  const span = entry.span
  const richSpan = span as unknown as Record<string, unknown>
  const hasError = isTrajectoryError(span)
  const status = hasError ? 'Error' : span.errorHandled ? 'Handled' : span.status || 'Success'
  const statusVariant = hasError ? 'red' : span.errorHandled ? 'amber' : 'green'
  const cost = formatCostAmount(span.cost?.total)
  const tokens = getSpanTokenCount(span)
  const metadata = {
    id: entry.sourceId,
    blockId: span.blockId,
    model: richSpan.model,
    provider: richSpan.provider,
    toolCallId: richSpan.toolCallId,
    finishReason: richSpan.finishReason,
    tries: richSpan.tries,
  }
  const compactMetadata = Object.fromEntries(
    Object.entries(metadata).filter(([, value]) => value !== undefined && value !== null)
  )
  const tabs = [
    { id: 'overview' as const, label: 'Overview' },
    { id: 'input' as const, label: 'Input' },
    { id: 'output' as const, label: 'Output' },
    { id: 'timing' as const, label: 'Timing' },
  ]

  return (
    <aside className='flex h-full min-h-0 flex-col overflow-auto p-3.5'>
      <div className='flex min-w-0 items-start gap-2'>
        <SpanIcon span={span} />
        <div className='min-w-0 flex-1'>
          <h3 className='truncate text-[var(--text-primary)] text-sm'>{getSpanName(span)}</h3>
          <div className='mt-0.5 text-[var(--text-tertiary)] text-caption'>
            {entry.lane.toUpperCase()} · {entry.precision}
          </div>
        </div>
        <Badge variant={statusVariant} size='sm' className='flex-shrink-0 capitalize'>
          {status}
        </Badge>
      </div>

      <div className='mt-3 grid grid-cols-2 gap-2'>
        <InspectorMetric label='Duration' value={formatMs(entry.durationMs)} />
        <InspectorMetric label='Started' value={formatOffset(entry.offsetMs)} />
        <InspectorMetric
          label='Completed'
          value={formatOffset(entry.offsetMs + entry.durationMs)}
        />
        <InspectorMetric
          label={cost ? 'Cost' : 'Tokens'}
          value={cost || (tokens > 0 ? tokens.toLocaleString() : '—')}
        />
      </div>

      <div className='mt-3 flex items-center gap-1 border-[var(--border)] border-b' role='tablist'>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type='button'
            role='tab'
            aria-selected={activeTab === tab.id}
            className={cn(
              'border-b-2 border-transparent px-2 py-1.5 text-xs transition-colors',
              activeTab === tab.id
                ? 'border-[var(--text-primary)] text-[var(--text-primary)]'
                : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
            )}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {span.errorMessage ? (
        <p className='mt-3 text-[var(--text-error)] text-sm'>{span.errorMessage}</p>
      ) : activeTab === 'overview' ? (
        <p className='mt-3 text-[var(--text-secondary)] text-sm'>
          {span.type} stage in the {entry.lane.toUpperCase()} lane ({entry.precision} timing).
        </p>
      ) : null}

      <div className='mt-3 flex flex-col gap-2'>
        {activeTab === 'overview' && (
          <>
            <DetailCard
              key={`${entry.id}-error`}
              title='Error'
              value={span.errorMessage || span.errorType}
              defaultOpen
              error
            />
            <DetailCard key={`${entry.id}-thinking`} title='Thinking' value={richSpan.thinking} />
            <DetailCard
              key={`${entry.id}-metadata`}
              title='Metadata'
              value={Object.keys(compactMetadata).length > 0 ? compactMetadata : undefined}
            />
          </>
        )}
        {activeTab === 'input' && (
          <DetailCard
            key={`${entry.id}-input`}
            title='Input payload'
            value={span.input}
            defaultOpen
          />
        )}
        {activeTab === 'output' && (
          <DetailCard
            key={`${entry.id}-output`}
            title='Output payload'
            value={span.output}
            defaultOpen
          />
        )}
        {activeTab === 'timing' && (
          <DetailCard
            key={`${entry.id}-timing`}
            title='Timing details'
            defaultOpen
            value={{
              startedAt: new Date(entry.startMs).toISOString(),
              offsetMs: entry.offsetMs,
              durationMs: entry.durationMs,
              completedAt: new Date(entry.endMs).toISOString(),
            }}
          />
        )}
      </div>
    </aside>
  )
}

function TrajectoryContent({
  log,
  model,
}: {
  log: ExecutionLogDetailView
  model: TrajectoryModel
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [type, setType] = useState('all')
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set())
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    setSearchQuery('')
    setType('all')
    setCollapsedIds(new Set())
    setSelectedId(null)
  }, [log.identity.logId])

  const childIds = useMemo(
    () => new Set(model.entries.map((entry) => entry.parentId).filter((id): id is string => !!id)),
    [model.entries]
  )
  const isFiltering = searchQuery.trim().length > 0 || type !== 'all'
  const visibleEntries = useMemo(
    () =>
      getVisibleTrajectoryEntries(model.entries, {
        searchQuery,
        type,
        collapsedIds: isFiltering ? EMPTY_COLLAPSED_IDS : collapsedIds,
      }),
    [model.entries, searchQuery, type, isFiltering, collapsedIds]
  )
  const fallbackSelection =
    model.entries.find((entry) => isTrajectoryError(entry.span) && !childIds.has(entry.id)) ??
    model.entries[0] ??
    null
  const selectedEntry = model.entries.find((entry) => entry.id === selectedId) ?? fallbackSelection
  const effectiveSelectedId = selectedEntry?.id ?? null

  const typeOptions = useMemo(
    () => [
      { value: 'all', label: 'All types' },
      ...getTrajectoryTypes(model.entries).map((item) => ({ value: item, label: item })),
    ],
    [model.entries]
  )

  const handleSelect = useCallback((entry: TrajectoryEntry) => {
    setSelectedId(entry.id)
    setCollapsedIds((current) => {
      if (!entry.parentIds.some((id) => current.has(id))) return current
      const next = new Set(current)
      entry.parentIds.forEach((id) => next.delete(id))
      return next
    })
  }, [])

  const handleToggle = useCallback((id: string) => {
    setCollapsedIds((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  return (
    <div className='flex min-h-0 flex-1 flex-col gap-3'>
      <div
        className='flex min-h-[32px] flex-wrap items-center gap-1 border-[var(--border)] border-b pb-1'
        role='toolbar'
        aria-label='Trajectory controls'
      >
        <span className='mr-1 text-[var(--text-tertiary)] text-xs'>Timeline</span>
        <Button
          type='button'
          variant='ghost'
          className='h-7 px-2 text-xs'
          aria-label='Use recorded duration'
        >
          <Clock className='mr-1 size-[13px]' />
          Recorded duration
        </Button>
        <Button
          type='button'
          variant='ghost'
          className='h-7 px-2 text-xs'
          aria-label='Expand all turns'
          onClick={() => setCollapsedIds(new Set())}
        >
          <ChevronsUpDown className='mr-1 size-[13px]' />
          Expand turns
        </Button>
        <Button
          type='button'
          variant='ghost'
          className='h-7 px-2 text-xs'
          aria-label='Collapse all turns'
          onClick={() => setCollapsedIds(new Set(childIds))}
        >
          <ChevronsDownUp className='mr-1 size-[13px]' />
          Collapse turns
        </Button>
        <span className='ml-auto text-[var(--text-tertiary)] text-caption tabular-nums'>
          {model.entries.length} records
        </span>
      </div>
      <TrajectorySummaryCards model={model} />
      <TrajectoryTimeline model={model} selectedId={effectiveSelectedId} onSelect={handleSelect} />

      <section className='flex min-h-[420px] flex-1 flex-col overflow-hidden rounded-md border border-[var(--border)] bg-[var(--surface-1)]'>
        <div className='flex flex-wrap items-center gap-2 border-[var(--border)] border-b px-3.5 py-2.5'>
          <ChipInput
            icon={Search}
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder='Search stages, input, or output...'
            className='min-w-[220px] flex-1'
          />
          <ChipCombobox
            options={typeOptions}
            value={type}
            onChange={setType}
            className='w-[140px]'
            searchable
            searchPlaceholder='Search types...'
          />
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <Button
                type='button'
                variant='ghost'
                className='!p-1'
                aria-label='Expand all levels'
                onClick={() => setCollapsedIds(new Set())}
              >
                <ChevronsUpDown className='size-[14px]' />
              </Button>
            </Tooltip.Trigger>
            <Tooltip.Content side='top'>Expand all</Tooltip.Content>
          </Tooltip.Root>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <Button
                type='button'
                variant='ghost'
                className='!p-1'
                aria-label='Collapse all levels'
                onClick={() => setCollapsedIds(new Set(childIds))}
              >
                <ChevronsDownUp className='size-[14px]' />
              </Button>
            </Tooltip.Trigger>
            <Tooltip.Content side='top'>Collapse all</Tooltip.Content>
          </Tooltip.Root>
        </div>

        <div className='grid min-h-0 flex-1 grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px]'>
          <div className='min-h-0 overflow-hidden border-[var(--border)] xl:border-r'>
            <TrajectoryLedger
              entries={visibleEntries}
              childIds={childIds}
              collapsedIds={isFiltering ? EMPTY_COLLAPSED_IDS : collapsedIds}
              selectedId={effectiveSelectedId}
              onToggle={handleToggle}
              onSelect={handleSelect}
            />
          </div>
          <div className='min-h-0 border-[var(--border)] border-t xl:border-t-0'>
            <TrajectoryInspector entry={selectedEntry} />
          </div>
        </div>
      </section>
    </div>
  )
}

/**
 * Dashboard trajectory view for inspecting one execution as a multi-level,
 * time-aligned ledger with a focused span inspector.
 */
export function Trajectory({ logs, isLoading }: TrajectoryProps) {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null)
  const effectiveLogId =
    selectedLogId && logs.some((log) => log.identity.logId === selectedLogId)
      ? selectedLogId
      : (logs[0]?.identity.logId ?? null)
  const selectedSummary = logs.find((log) => log.identity.logId === effectiveLogId) ?? null
  const isActiveRun =
    selectedSummary?.status === 'running' ||
    selectedSummary?.status === 'pending' ||
    selectedSummary?.status === 'redacting'
  const detailQuery = useLogDetail(effectiveLogId ?? undefined, workspaceId, {
    refetchInterval: isActiveRun ? ACTIVE_RUN_REFRESH_MS : false,
  })
  const detail = detailQuery.data ? mapExecutionLogDetail(detailQuery.data) : null
  const traceSpans = detail?.traceSpans
  const trajectory = detail?.trajectory
  const fallbackDuration = detail?.durationMs ?? selectedSummary?.durationMs ?? 0
  const model = useMemo(
    () => buildTrajectoryModel(traceSpans, fallbackDuration ?? 0, trajectory),
    [traceSpans, fallbackDuration, trajectory]
  )
  const runOptions = useMemo(
    () => logs.map((log) => ({ value: log.identity.logId, label: getRunLabel(log) })),
    [logs]
  )
  const selectedRunBadge = getRunBadge(detail?.status ?? selectedSummary?.status ?? null)

  if (isLoading && logs.length === 0) {
    return (
      <div className='mt-6 flex min-h-[320px] flex-1 items-center justify-center'>
        <Loader className='size-[16px] text-[var(--text-secondary)]' animate />
      </div>
    )
  }

  if (logs.length === 0) {
    return (
      <div className='mt-6 flex min-h-[320px] flex-1 items-center justify-center'>
        <div className='text-center text-[var(--text-secondary)]'>
          <Workflow className='mx-auto size-[18px] text-[var(--text-icon)]' />
          <p className='mt-2 text-sm'>No executions found</p>
          <p className='mt-1 text-[var(--text-tertiary)] text-caption'>
            Run a workflow to record its multi-level trajectory here.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className='mt-6 flex min-h-0 flex-1 flex-col pb-6'>
      <div className='mb-3 flex flex-wrap items-center gap-3'>
        <div className='flex min-w-0 flex-1 items-center gap-2'>
          <div className='flex size-[28px] flex-shrink-0 items-center justify-center rounded-md bg-[var(--surface-3)]'>
            <Workflow className='size-[14px] text-[var(--text-icon)]' />
          </div>
          <div className='min-w-0'>
            <div className='flex items-center gap-2'>
              <h2 className='truncate text-[var(--text-primary)] text-sm'>Execution trajectory</h2>
              <Badge variant={selectedRunBadge.variant} size='sm' dot className='flex-shrink-0'>
                {selectedRunBadge.label}
              </Badge>
            </div>
            <p className='truncate text-[var(--text-tertiary)] text-caption'>
              Time-aligned, multi-level workflow pipeline
            </p>
          </div>
        </div>
        <ChipCombobox
          options={runOptions}
          value={effectiveLogId ?? undefined}
          onChange={setSelectedLogId}
          placeholder='Select an execution'
          className='w-full sm:w-[360px]'
          searchable
          searchPlaceholder='Search executions...'
          dropdownWidth={420}
        />
      </div>

      {detailQuery.isPending ? (
        <div className='flex min-h-[320px] flex-1 items-center justify-center rounded-md border border-[var(--border)]'>
          <Loader className='size-[16px] text-[var(--text-secondary)]' animate />
        </div>
      ) : detailQuery.error ? (
        <div className='flex min-h-[320px] flex-1 items-center justify-center rounded-md border border-[var(--border)] px-4 text-center'>
          <div>
            <p className='text-[var(--text-error)] text-sm'>Unable to load this trajectory</p>
            <p className='mt-1 text-[var(--text-tertiary)] text-caption'>
              {detailQuery.error.message}
            </p>
          </div>
        </div>
      ) : !detail || model.entries.length === 0 ? (
        <div className='flex min-h-[320px] flex-1 items-center justify-center rounded-md border border-[var(--border)] px-4 text-center'>
          <div className='text-[var(--text-secondary)]'>
            <Wrench className='mx-auto size-[18px] text-[var(--text-icon)]' />
            <p className='mt-2 text-sm'>No trajectory data recorded</p>
            <p className='mt-1 text-[var(--text-tertiary)] text-caption'>
              This execution predates trace capture or did not emit any spans.
            </p>
          </div>
        </div>
      ) : (
        <TrajectoryContent log={detail} model={model} />
      )}
    </div>
  )
}
