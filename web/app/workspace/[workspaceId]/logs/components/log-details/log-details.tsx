'use client'

import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import {
  Badge,
  Button,
  Chip,
  ChipInput,
  ChipModalTabs,
  Code,
  cn,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Duplicate,
  Eye,
  handleKeyboardActivation,
  Redo,
  Search as SearchIcon,
  Tooltip,
  useCopyToClipboard,
} from '@sim/emcn'
import { ArrowDown, ArrowUp, Check, ChevronUp, Clipboard, Search, Wrench, X } from '@sim/emcn/icons'
import { formatDuration } from '@sim/utils/formatting'
import { useParams, useRouter } from 'next/navigation'
import { useQueryState } from 'nuqs'
import { createPortal } from 'react-dom'
import { BASE_EXECUTION_CHARGE } from '@/lib/billing/constants'
import { isChatEnabled } from '@/lib/core/config/env-flags'
import { MothershipHandoffStorage } from '@/lib/core/utils/browser-storage'
import { filterHiddenOutputKeys } from '@/lib/logs/execution/trace-spans/trace-spans'
import type { TraceSpan } from '@/lib/logs/types'
import { sendMothershipMessage } from '@/lib/mothership/events'
import {
  ExecutionSnapshot,
  FileCards,
  TraceView,
} from '@/app/workspace/[workspaceId]/logs/components'
import { useLogDetailsResize } from '@/app/workspace/[workspaceId]/logs/hooks'
import type { ExecutionLogDetailView } from '@/app/workspace/[workspaceId]/logs/model/execution-log'
import { projectRunCost } from '@/app/workspace/[workspaceId]/logs/model/run-cost'
import {
  logDetailsTabParam,
  logDetailsTabUrlKeys,
} from '@/app/workspace/[workspaceId]/logs/search-params'
import { formatDate, StatusBadge, TriggerBadge } from '@/app/workspace/[workspaceId]/logs/utils'
import { useCodeViewerFeatures } from '@/hooks/use-code-viewer'
import { usePermissionConfig } from '@/hooks/use-permission-config'
import { formatCost } from '@/providers/utils'
import { useLogDetailsUIStore } from '@/stores/logs/store'
import { MAX_LOG_DETAILS_WIDTH_RATIO, MIN_LOG_DETAILS_WIDTH } from '@/stores/logs/utils'
import type { ChatContext } from '@/stores/panel'

/**
 * Renders an already-apportioned integer credit value. `dollars` is only used
 * to distinguish a genuine zero ("0 credits") from a sub-credit charge that
 * rounded down to zero ("<1 credit"); the credit figure itself is authoritative.
 */
function creditLabel(credits: number, dollars: number): string {
  if (credits <= 0) return dollars > 0 ? '<1 credit' : '0 credits'
  return `${credits.toLocaleString()} ${credits === 1 ? 'credit' : 'credits'}`
}

export const RunOutputSection = memo(
  function RunOutputSection({ output }: { output: Record<string, unknown> }) {
    const contentRef = useRef<HTMLDivElement>(null)
    const { copied, copy } = useCopyToClipboard({ resetMs: 1500 })

    const [isContextMenuOpen, setIsContextMenuOpen] = useState(false)
    const [contextMenuPosition, setContextMenuPosition] = useState({ x: 0, y: 0 })

    const {
      isSearchActive,
      searchQuery,
      setSearchQuery,
      matchCount,
      currentMatchIndex,
      activateSearch,
      closeSearch,
      goToNextMatch,
      goToPreviousMatch,
      handleMatchCountChange,
      searchInputRef,
    } = useCodeViewerFeatures({ contentRef })

    const jsonString = useMemo(() => JSON.stringify(output, null, 2), [output])

    function handleContextMenu(e: React.MouseEvent) {
      e.preventDefault()
      e.stopPropagation()
      setContextMenuPosition({ x: e.clientX, y: e.clientY })
      setIsContextMenuOpen(true)
    }

    function handleCopy() {
      copy(jsonString)
      setIsContextMenuOpen(false)
    }

    function handleSearch() {
      activateSearch()
      setIsContextMenuOpen(false)
    }

    return (
      <div className='relative flex min-w-0 flex-col overflow-hidden'>
        <div ref={contentRef} onContextMenu={handleContextMenu} className='relative'>
          <Code.Viewer
            code={jsonString}
            language='json'
            className='!bg-[var(--surface-4)] dark:!bg-[var(--surface-3)] max-h-[300px] min-h-0 max-w-full rounded-md border-0 [word-break:break-all]'
            wrapText
            searchQuery={isSearchActive ? searchQuery : undefined}
            currentMatchIndex={currentMatchIndex}
            onMatchCountChange={handleMatchCountChange}
          />
          {/* Glass action buttons overlay */}
          {!isSearchActive && (
            <div className='absolute top-[7px] right-[6px] z-10 flex gap-1'>
              <Tooltip.Root>
                <Tooltip.Trigger asChild>
                  <Button
                    type='button'
                    variant='default'
                    onClick={(e) => {
                      e.stopPropagation()
                      handleCopy()
                    }}
                    className='size-[20px] cursor-pointer border border-[var(--border-1)] bg-transparent p-0 backdrop-blur-sm hover-hover:bg-[var(--surface-3)]'
                  >
                    {copied ? (
                      <Check className='size-[10px] text-[var(--text-success)]' />
                    ) : (
                      <Clipboard className='size-[10px]' />
                    )}
                  </Button>
                </Tooltip.Trigger>
                <Tooltip.Content side='top'>{copied ? 'Copied' : 'Copy'}</Tooltip.Content>
              </Tooltip.Root>
              <Tooltip.Root>
                <Tooltip.Trigger asChild>
                  <Button
                    type='button'
                    variant='default'
                    onClick={(e) => {
                      e.stopPropagation()
                      activateSearch()
                    }}
                    className='size-[20px] cursor-pointer border border-[var(--border-1)] bg-transparent p-0 backdrop-blur-sm hover-hover:bg-[var(--surface-3)]'
                  >
                    <Search className='size-[10px]' />
                  </Button>
                </Tooltip.Trigger>
                <Tooltip.Content side='top'>Search</Tooltip.Content>
              </Tooltip.Root>
            </div>
          )}
        </div>

        {/* Search Overlay */}
        {isSearchActive && (
          <div
            role='presentation'
            className='absolute top-0 right-0 z-30 flex h-[34px] items-center gap-1.5 rounded-sm border border-[var(--border)] bg-[var(--surface-1)] px-1.5 shadow-sm'
            onClick={(e) => e.stopPropagation()}
          >
            <ChipInput
              ref={searchInputRef}
              type='text'
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder='Search...'
              className='mr-0.5 w-[94px]'
            />
            <span
              className={cn(
                'min-w-[45px] text-center text-xs',
                matchCount > 0 ? 'text-[var(--text-secondary)]' : 'text-[var(--text-tertiary)]'
              )}
            >
              {matchCount > 0 ? `${currentMatchIndex + 1}/${matchCount}` : '0/0'}
            </span>
            <Button
              variant='ghost'
              className='!p-1'
              onClick={goToPreviousMatch}
              disabled={matchCount === 0}
              aria-label='Previous match'
            >
              <ArrowUp className='size-[12px]' />
            </Button>
            <Button
              variant='ghost'
              className='!p-1'
              onClick={goToNextMatch}
              disabled={matchCount === 0}
              aria-label='Next match'
            >
              <ArrowDown className='size-[12px]' />
            </Button>
            <Button
              variant='ghost'
              className='!p-1'
              onClick={closeSearch}
              aria-label='Close search'
            >
              <X className='size-[12px]' />
            </Button>
          </div>
        )}

        {/* Context Menu - rendered in portal to avoid transform/overflow clipping */}
        {typeof document !== 'undefined' &&
          createPortal(
            <DropdownMenu
              open={isContextMenuOpen}
              onOpenChange={() => setIsContextMenuOpen(false)}
              modal={false}
            >
              <DropdownMenuTrigger asChild>
                <div
                  style={{
                    position: 'fixed',
                    left: `${contextMenuPosition.x}px`,
                    top: `${contextMenuPosition.y}px`,
                    width: '1px',
                    height: '1px',
                    pointerEvents: 'none',
                  }}
                  tabIndex={-1}
                  aria-hidden
                />
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align='start'
                side='bottom'
                sideOffset={4}
                onCloseAutoFocus={(e) => e.preventDefault()}
              >
                <DropdownMenuItem onSelect={handleCopy}>
                  <Duplicate />
                  Copy
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={handleSearch}>
                  <SearchIcon />
                  Search
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>,
            document.body
          )}
      </div>
    )
  },
  (prev, next) => prev.output === next.output
)

export type LogDetailsTab = 'overview' | 'trace' | 'events'

interface LogDetailsContentProps {
  log: ExecutionLogDetailView
  onActiveTabChange?: (tab: LogDetailsTab) => void
}

export function LogDetailsContent({ log, onActiveTabChange }: LogDetailsContentProps) {
  const [isExecutionSnapshotOpen, setIsExecutionSnapshotOpen] = useState(false)
  const [activeTab, setActiveTab] = useQueryState(logDetailsTabParam.key, {
    ...logDetailsTabParam.parser,
    ...logDetailsTabUrlKeys,
  })
  const { copied: copiedRunId, copy: copyRunId } = useCopyToClipboard({ resetMs: 1500 })

  const scrollAreaRef = useRef<HTMLDivElement>(null)

  const router = useRouter()
  const { workspaceId } = useParams<{ workspaceId: string }>()

  const { config: permissionConfig } = usePermissionConfig()

  const isInitialTabMountRef = useRef(true)
  /**
   * Honors a deep-linked tab on first mount; resets to overview only when
   * switching to a different log.
   */
  useEffect(() => {
    if (isInitialTabMountRef.current) {
      isInitialTabMountRef.current = false
    } else {
      setActiveTab('overview')
    }
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = 0
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- stable nuqs setter; reset tab when switching logs
  }, [log.identity.logId])

  /**
   * A run "looks like an execution" when it carries a canonical execution id
   * and isn't a legacy mothership job row (those carry no runtime trace).
   */
  const isLikelyExecution = !!log.identity.executionId && log.trigger?.type !== 'mothership'
  const hasExecutionDetail =
    (log.trigger?.type === 'manual' && log.durationMs != null) || !!log.traceSpans

  const hasCostInfo = hasExecutionDetail && log.costTotalDollars != null
  const showRunSnapshot =
    hasExecutionDetail &&
    !!log.identity.executionId &&
    log.trigger?.type !== 'mothership' &&
    !permissionConfig.hideTraceSpans

  const showTraceTab = !permissionConfig.hideTraceSpans && isLikelyExecution
  // double-cast-allowed: contract schema makes duration/startTime optional for legacy persisted JSON; runtime data always supplies them.
  const traceSpans = log.traceSpans as unknown as TraceSpan[] | undefined
  const runtimeEvents = log.runtimeEvents

  const showEventsTab = isLikelyExecution && runtimeEvents.length > 0
  const resolvedTab: LogDetailsTab =
    (activeTab === 'trace' && !showTraceTab) || (activeTab === 'events' && !showEventsTab)
      ? 'overview'
      : activeTab

  useLayoutEffect(() => {
    onActiveTabChange?.(resolvedTab)
  }, [resolvedTab, onActiveTabChange])

  const finalOutput = useMemo(() => {
    const raw = log.finalOutput
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
    return filterHiddenOutputKeys(raw as Record<string, unknown>) as Record<string, unknown>
  }, [log.finalOutput])

  const runInput = useMemo(() => {
    const raw = log.runInput
    if (raw === undefined || raw === null) return null
    if (typeof raw === 'object' && !Array.isArray(raw)) {
      return raw as Record<string, unknown>
    }
    return { input: raw } as Record<string, unknown>
  }, [log.runInput])

  // Cost breakdown is projected by the pure model layer from the canonical
  // usage ledger (single source of truth) — never reconstructed here.
  const costBreakdown = useMemo(
    () => projectRunCost(log.costLedger, log.costTotalDollars),
    [log.costLedger, log.costTotalDollars]
  )

  const formattedTimestamp = formatDate(log.createdAt)

  /**
   * Troubleshooting hands the failed run off to Chat, tagging it by
   * `executionId`. A real Chat run can't be debugged from inside itself, so
   * mothership-triggered logs are excluded — `isLikelyExecution` already encodes
   * "has an executionId and isn't a mothership run".
   */
  const canTroubleshoot = isChatEnabled && log.status === 'error' && isLikelyExecution

  /**
   * Hands the failed run to Chat. When a chat is already mounted (e.g. the run
   * is being viewed inside Chat's resource panel) it consumes the tagged
   * message directly; otherwise a one-shot handoff is persisted and we navigate
   * to a fresh chat that picks it up on mount. Navigation is gated on a
   * successful store, so a failed write never strands the user on an empty chat.
   */
  const handleTroubleshoot = useCallback(() => {
    if (!log.identity.executionId) return
    const sourceTitle = log.source.kind === 'workflow' ? log.source.title.trim() || null : null
    const context: ChatContext = {
      kind: 'logs',
      executionId: log.identity.executionId,
      label: sourceTitle ?? log.source.title,
    }
    const message = sourceTitle
      ? `The "${sourceTitle}" run failed. Investigate the error in this run and help me fix it.`
      : 'This run failed. Investigate the error in this run and help me fix it.'
    if (sendMothershipMessage(message, [context])) return
    if (MothershipHandoffStorage.store({ message, contexts: [context] }, workspaceId)) {
      router.push(`/workspace/${workspaceId}/home`)
    }
  }, [log.identity.executionId, log.source.kind, log.source.title, workspaceId, router])

  return (
    <>
      <div className='mt-4 flex min-h-0 flex-1 flex-col'>
        <ChipModalTabs
          tabs={[
            { value: 'overview', label: 'Overview' },
            ...(showTraceTab ? [{ value: 'trace', label: 'Trace' }] : []),
            ...(showEventsTab ? [{ value: 'events', label: 'Events' }] : []),
          ]}
          value={resolvedTab}
          onChange={(v) => setActiveTab(v as LogDetailsTab)}
        />

        {/* Overview Tab */}
        {resolvedTab === 'overview' && (
          <div ref={scrollAreaRef} className='mt-4 min-h-0 flex-1 overflow-y-auto'>
            <div className='flex flex-col gap-2.5 pb-4'>
              {/* Timestamp + Source header */}
              <div className='grid grid-cols-2 gap-x-3 pb-0.5'>
                <div className='flex min-w-0 flex-col gap-0.5'>
                  <span className='text-[var(--text-tertiary)] text-caption'>Timestamp</span>
                  <span className='text-[var(--text-secondary)] text-sm tabular-nums'>
                    {formattedTimestamp
                      ? `${formattedTimestamp.compactDate} ${formattedTimestamp.compactTime}`
                      : '—'}
                  </span>
                </div>
                <div className='flex min-w-0 flex-col gap-0.5'>
                  <span className='text-[var(--text-tertiary)] text-caption'>
                    {log.source.kind === 'agent-task' ? 'Task' : 'Source'}
                  </span>
                  {/* No navigation: the workflow editor is not a run source surface. */}
                  <div className='flex min-w-0 items-center gap-1.5'>
                    <span className='min-w-0 truncate text-[var(--text-secondary)] text-sm'>
                      {log.source.title}
                    </span>
                  </div>
                </div>
              </div>

              {/* Details Section */}
              <div className='divide-y divide-[var(--border)] overflow-hidden rounded-md border border-[var(--border)] bg-[var(--surface-2)] dark:bg-transparent'>
                {/* Run ID — click to copy */}
                {log.identity.executionId && (
                  <div
                    role='button'
                    tabIndex={0}
                    aria-label='Copy run ID'
                    className='flex h-10 min-w-0 cursor-pointer items-center justify-between gap-4 px-3 transition-colors hover-hover:bg-[var(--surface-active)]'
                    onClick={() => copyRunId(log.identity.executionId!)}
                    onKeyDown={(event) =>
                      handleKeyboardActivation(event, () => copyRunId(log.identity.executionId!))
                    }
                  >
                    <span className='flex-shrink-0 text-[var(--text-tertiary)] text-caption'>
                      Run ID
                    </span>
                    <span className='min-w-0 truncate text-[var(--text-secondary)] text-caption tabular-nums'>
                      {copiedRunId ? 'Copied!' : log.identity.executionId}
                    </span>
                  </div>
                )}

                {/* Task ID — the owning AgentTask, when the runtime recorded one */}
                {log.taskId && (
                  <div className='flex h-10 min-w-0 items-center justify-between gap-4 px-3'>
                    <span className='flex-shrink-0 text-[var(--text-tertiary)] text-caption'>
                      Task ID
                    </span>
                    <span className='min-w-0 truncate text-[var(--text-secondary)] text-caption tabular-nums'>
                      {log.taskId}
                    </span>
                  </div>
                )}

                {/* Level */}
                <div className='flex h-10 items-center justify-between px-3'>
                  <span className='text-[var(--text-tertiary)] text-caption'>Level</span>
                  <StatusBadge status={log.status} />
                </div>

                {/* Trigger */}
                <div className='flex h-10 items-center justify-between px-3'>
                  <span className='text-[var(--text-tertiary)] text-caption'>Trigger</span>
                  {log.trigger ? (
                    <TriggerBadge trigger={log.trigger} />
                  ) : (
                    <span className='text-[var(--text-secondary)] text-caption'>None</span>
                  )}
                </div>

                {/* Duration */}
                <div className='flex h-10 items-center justify-between px-3'>
                  <span className='text-[var(--text-tertiary)] text-caption'>Duration</span>
                  <span className='text-[var(--text-secondary)] text-caption tabular-nums'>
                    {log.durationMs != null
                      ? formatDuration(log.durationMs, { precision: 2 }) || '—'
                      : '—'}
                  </span>
                </div>

                {/* Version */}
                {log.deploymentVersionLabel && (
                  <div className='flex h-10 items-center gap-2 px-3'>
                    <span className='flex-shrink-0 text-[var(--text-tertiary)] text-caption'>
                      Version
                    </span>
                    <div className='flex w-0 flex-1 justify-end'>
                      <Badge variant='green' size='sm' className='max-w-full truncate'>
                        {log.deploymentVersionLabel}
                      </Badge>
                    </div>
                  </div>
                )}

                {/* Snapshot */}
                {showRunSnapshot && (
                  <div className='flex h-10 items-center justify-between px-3'>
                    <span className='text-[var(--text-tertiary)] text-caption'>Snapshot</span>
                    <Chip leftIcon={Eye} onClick={() => setIsExecutionSnapshotOpen(true)}>
                      View Snapshot
                    </Chip>
                  </div>
                )}

                {/* Troubleshoot */}
                {canTroubleshoot && (
                  <div className='flex h-10 items-center justify-between px-3'>
                    <span className='text-[var(--text-tertiary)] text-caption'>Troubleshoot</span>
                    <Chip leftIcon={Wrench} onClick={handleTroubleshoot}>
                      Troubleshoot in Chat
                    </Chip>
                  </div>
                )}
              </div>

              {/* Run Input */}
              {hasExecutionDetail && runInput && !permissionConfig.hideTraceSpans && (
                <div className='flex flex-col gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-2 dark:bg-transparent'>
                  <span className='text-[var(--text-tertiary)] text-caption'>Run Input</span>
                  <RunOutputSection output={runInput} />
                </div>
              )}

              {/* Run Output */}
              {hasExecutionDetail && finalOutput && !permissionConfig.hideTraceSpans && (
                <div className='flex flex-col gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-2 dark:bg-transparent'>
                  <span
                    className={cn(
                      'text-caption',
                      finalOutput.error ? 'text-[var(--text-error)]' : 'text-[var(--text-tertiary)]'
                    )}
                  >
                    Run Output
                  </span>
                  <RunOutputSection output={finalOutput} />
                </div>
              )}

              {/* Files */}
              {log.files && log.files.length > 0 && <FileCards files={log.files} isExecutionFile />}

              {/* Cost Breakdown */}
              {hasCostInfo && costBreakdown && (
                <div className='divide-y divide-[var(--border)] overflow-hidden rounded-md border border-[var(--border)] bg-[var(--surface-2)] dark:bg-transparent'>
                  {costBreakdown.rows.map((row) => (
                    <div key={row.key} className='flex h-10 items-center justify-between px-3'>
                      <span className='min-w-0 truncate text-[var(--text-tertiary)] text-caption'>
                        {row.label}
                      </span>
                      <span className='flex-shrink-0 text-[var(--text-secondary)] text-caption tabular-nums'>
                        {creditLabel(row.credits, row.dollars)}
                      </span>
                    </div>
                  ))}
                  <div className='flex h-10 items-center justify-between px-3'>
                    <span className='text-[var(--text-secondary)] text-caption'>Total</span>
                    <span className='text-[var(--text-primary)] text-caption tabular-nums'>
                      {creditLabel(costBreakdown.totalCredits, costBreakdown.totalDollars)}
                    </span>
                  </div>
                  {(costBreakdown.tokens.input > 0 || costBreakdown.tokens.output > 0) && (
                    <div className='flex h-10 items-center justify-between px-3'>
                      <span className='text-[var(--text-tertiary)] text-caption'>Tokens</span>
                      <span className='text-[var(--text-secondary)] text-caption tabular-nums'>
                        {costBreakdown.tokens.input} in · {costBreakdown.tokens.output} out
                      </span>
                    </div>
                  )}
                  <div className='px-3 py-2'>
                    <p className='text-[var(--text-tertiary)] text-xs'>
                      Total includes a {formatCost(BASE_EXECUTION_CHARGE)} base charge plus model
                      and tool usage.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Trace Tab */}
        {showTraceTab && resolvedTab === 'trace' && (
          <div className='mt-3 min-h-0 flex-1 overflow-hidden focus-visible:outline-none'>
            {traceSpans?.length ? (
              <TraceView
                traceSpans={traceSpans}
                runCostDollars={log.costTotalDollars ?? undefined}
              />
            ) : log.hasDetailPayload ? (
              <div className='flex h-full items-center justify-center px-4 text-center'>
                <span className='text-[var(--text-tertiary)] text-sm'>
                  No trace data available for this run
                </span>
              </div>
            ) : (
              <div className='flex h-full items-center justify-center px-4 text-center'>
                <span className='text-[var(--text-tertiary)] text-sm'>Loading trace…</span>
              </div>
            )}
          </div>
        )}

        {showEventsTab && resolvedTab === 'events' && (
          <div
            ref={scrollAreaRef}
            className='mt-3 min-h-0 flex-1 overflow-y-auto rounded-lg border border-[var(--border-subtle)]'
          >
            <div className='divide-y divide-[var(--border-subtle)]'>
              {runtimeEvents.map((event, index) => (
                <details
                  key={`${String(event.sequence ?? index)}-${String(event.kind)}`}
                  className='group p-3'
                >
                  <summary className='flex cursor-pointer list-none items-center justify-between gap-3 text-sm'>
                    <span className='font-mono text-[var(--text-primary)]'>
                      {String(event.kind ?? 'runtime.event')}
                    </span>
                    <span className='text-xs text-[var(--text-tertiary)]'>
                      {String(event.agent ?? 'coordinator')} · {String(event.sequence ?? index + 1)}
                    </span>
                  </summary>
                  <pre className='mt-2 overflow-x-auto rounded-md bg-[var(--surface-secondary)] p-2 text-xs text-[var(--text-secondary)]'>
                    {JSON.stringify(
                      {
                        payload: event.payload,
                        runtime: event.runtime,
                        createdAt: event.createdAt,
                      },
                      null,
                      2
                    )}
                  </pre>
                </details>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Frozen Canvas Modal */}
      {log.identity.executionId && (
        <ExecutionSnapshot
          executionId={log.identity.executionId}
          traceSpans={traceSpans}
          isModal
          isOpen={isExecutionSnapshotOpen}
          onClose={() => setIsExecutionSnapshotOpen(false)}
        />
      )}
    </>
  )
}

interface LogDetailsProps {
  log: ExecutionLogDetailView | null
  isOpen: boolean
  onClose: () => void
  onNavigateNext?: () => void
  onNavigatePrev?: () => void
  hasNext?: boolean
  hasPrev?: boolean
  onRetryExecution?: () => void
  isRetryPending?: boolean
  onActiveTabChange?: (tab: LogDetailsTab) => void
}

export const LogDetails = memo(function LogDetails({
  log,
  isOpen,
  onClose,
  onNavigateNext,
  onNavigatePrev,
  hasNext = false,
  hasPrev = false,
  onRetryExecution,
  isRetryPending = false,
  onActiveTabChange,
}: LogDetailsProps) {
  const activeTabRef = useRef<LogDetailsTab>('overview')

  const handleActiveTabChange = useCallback(
    (tab: LogDetailsTab) => {
      activeTabRef.current = tab
      onActiveTabChange?.(tab)
    },
    [onActiveTabChange]
  )

  const panelWidth = useLogDetailsUIStore((state) => state.panelWidth)
  const { handleMouseDown } = useLogDetailsResize()

  const maxVw = `${MAX_LOG_DETAILS_WIDTH_RATIO * 100}vw`
  const effectiveWidth = `clamp(min(${MIN_LOG_DETAILS_WIDTH}px, ${maxVw}), ${panelWidth}px, ${maxVw})`

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }

      if (!isOpen) return

      // Trace tab owns arrow keys for span navigation.
      if (activeTabRef.current === 'trace') return

      if (e.key === 'ArrowUp' && hasPrev && onNavigatePrev) {
        e.preventDefault()
        onNavigatePrev()
      }

      if (e.key === 'ArrowDown' && hasNext && onNavigateNext) {
        e.preventDefault()
        onNavigateNext()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose, hasPrev, hasNext, onNavigatePrev, onNavigateNext])

  return (
    <>
      {/* Resize Handle - positioned outside the panel */}
      {isOpen && (
        <div
          className='absolute top-0 bottom-0 z-[var(--z-dropdown)] w-[8px] cursor-ew-resize'
          style={{ right: `calc(${effectiveWidth} - 4px)` }}
          onMouseDown={handleMouseDown}
          role='separator'
          aria-label='Resize log details panel'
          aria-orientation='vertical'
        />
      )}

      <div
        className={cn(
          'absolute top-0 right-0 bottom-0 z-[var(--z-dropdown)] overflow-hidden border-l bg-[var(--bg)] shadow-md transition-transform duration-200 ease-out',
          isOpen ? 'translate-x-0' : 'translate-x-full'
        )}
        style={{ width: effectiveWidth }}
        aria-label='Log details sidebar'
      >
        {log && (
          <div className='flex h-full flex-col px-3.5 pt-3'>
            {/* Header */}
            <div className='flex items-center justify-between'>
              <h2 className='text-[var(--text-primary)] text-sm'>Log Details</h2>
              <div className='flex items-center gap-[1px]'>
                {log.status === 'error' && log.source.kind !== 'unknown' && (
                  <Tooltip.Root>
                    <Tooltip.Trigger asChild>
                      <Button
                        variant='ghost'
                        className='!p-1'
                        onClick={() => onRetryExecution?.()}
                        disabled={isRetryPending}
                        aria-label='Retry execution'
                      >
                        <Redo className='size-[14px]' />
                      </Button>
                    </Tooltip.Trigger>
                    <Tooltip.Content side='bottom'>Retry</Tooltip.Content>
                  </Tooltip.Root>
                )}
                <Button
                  variant='ghost'
                  className='!p-1'
                  onClick={() => hasPrev && onNavigatePrev?.()}
                  disabled={!hasPrev}
                  aria-label='Previous log'
                >
                  <ChevronUp className='size-[14px]' />
                </Button>
                <Button
                  variant='ghost'
                  className='!p-1'
                  onClick={() => hasNext && onNavigateNext?.()}
                  disabled={!hasNext}
                  aria-label='Next log'
                >
                  <ChevronUp className='size-[14px] rotate-180' />
                </Button>
                <Button variant='ghost' className='!p-1' onClick={onClose} aria-label='Close'>
                  <X className='size-[14px]' />
                </Button>
              </div>
            </div>

            <LogDetailsContent log={log} onActiveTabChange={handleActiveTabChange} />
          </div>
        )}
      </div>
    </>
  )
})
