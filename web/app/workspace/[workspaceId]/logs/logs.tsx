'use client'

import { useCallback, useMemo, useRef, useState } from 'react'
import {
  Button,
  Calendar,
  ChipCombobox,
  type ComboboxOption,
  cn,
  Library,
  Popover,
  PopoverAnchor,
  PopoverContent,
  RefreshCw,
} from '@sim/emcn'
import { Download } from '@sim/emcn/icons'
import { useParams } from 'next/navigation'
import { formatDateShort } from '@/lib/core/utils/date-display'
import { hasActiveFilters } from '@/lib/logs/filters'
import { getTriggerOptions } from '@/lib/logs/get-trigger-options'
import { formatDuration } from '@/lib/utils/formatting'
import type {
  ResourceAction,
  ResourceColumn,
  ResourceRow,
} from '@/app/workspace/[workspaceId]/components'
import { Resource } from '@/app/workspace/[workspaceId]/components'
import { useObservabilityListController } from '@/app/workspace/[workspaceId]/logs/controllers/use-observability-list-controller'
import { useTrajectoryDetailController } from '@/app/workspace/[workspaceId]/logs/controllers/use-trajectory-detail-controller'
import { useLogFilters } from '@/app/workspace/[workspaceId]/logs/hooks/use-log-filters'
import type {
  ExecutionLogSummaryView,
  RunStatus,
} from '@/app/workspace/[workspaceId]/logs/model/execution-log'
import type { Suggestion } from '@/app/workspace/[workspaceId]/logs/types'
import { useRegisterGlobalCommands } from '@/app/workspace/[workspaceId]/providers/global-commands-provider'
import { useFolderMap } from '@/hooks/queries/folders'
import {
  Dashboard,
  ExecutionSnapshot,
  LogDetails,
  LogRowContextMenu,
  Trajectory,
} from './components'
import { formatDate, STATUS_CONFIG, StatusBadge, TriggerBadge } from './utils'

const LOG_COLUMNS: ResourceColumn[] = [
  { id: 'run', header: 'Run' },
  { id: 'date', header: 'Date' },
  { id: 'status', header: 'Status' },
  { id: 'cost', header: 'Cost' },
  { id: 'trigger', header: 'Trigger' },
  { id: 'duration', header: 'Duration' },
]

const TIME_RANGE_OPTIONS: ComboboxOption[] = [
  { value: 'All time', label: 'All time' },
  { value: 'Past 30 minutes', label: 'Past 30 minutes' },
  { value: 'Past hour', label: 'Past hour' },
  { value: 'Past 6 hours', label: 'Past 6 hours' },
  { value: 'Past 12 hours', label: 'Past 12 hours' },
  { value: 'Past 24 hours', label: 'Past 24 hours' },
  { value: 'Past 3 days', label: 'Past 3 days' },
  { value: 'Past 7 days', label: 'Past 7 days' },
  { value: 'Past 14 days', label: 'Past 14 days' },
  { value: 'Past 30 days', label: 'Past 30 days' },
  { value: 'Custom range', label: 'Custom range' },
] as const

const colorIconCache = new Map<string, React.ComponentType<{ className?: string }>>()

function getColorIcon(color: string): React.ComponentType<{ className?: string }> {
  const cached = colorIconCache.get(color)
  if (cached) return cached

  const ColorIcon = ({ className }: { className?: string }) => (
    <div
      className={cn(className, 'flex-shrink-0 rounded-[3px]')}
      style={{
        backgroundColor: color,
        width: 10,
        height: 10,
      }}
    />
  )
  ColorIcon.displayName = `ColorIcon(${color})`
  colorIconCache.set(color, ColorIcon)
  return ColorIcon
}

function SpinningRefreshCw(props: React.SVGProps<SVGSVGElement>) {
  return <RefreshCw {...props} animate />
}

/** Renders one list row purely from the native view model. */
function buildRow(view: ExecutionLogSummaryView): ResourceRow {
  const formattedDate = formatDate(view.createdAt)
  const durationText =
    view.durationMs != null ? (formatDuration(view.durationMs, { precision: 2 }) ?? '—') : '—'
  const costText =
    view.costCredits !== null
      ? `${view.costCredits.toLocaleString()} ${view.costCredits === 1 ? 'credit' : 'credits'}`
      : '—'

  return {
    id: view.identity.logId,
    cells: {
      run: { label: view.source.title },
      date: { label: `${formattedDate.compactDate} ${formattedDate.compactTime}` },
      status: { content: <StatusBadge status={view.status} /> },
      cost: { label: costText },
      trigger: view.trigger ? { content: <TriggerBadge trigger={view.trigger} /> } : { label: '—' },
      duration: { label: durationText },
    },
  }
}

/**
 * Logs page: observability over Lingxi-native executions (agent tasks and
 * legacy workflow runs). This component is a thin composition shell — the list
 * controller owns filtering/sorting/pagination/selection, the detail
 * controller owns the selected run's trajectory data and commands, and the
 * pure mapper owns wire → view-model translation.
 */
export default function Logs() {
  const params = useParams()
  const workspaceId = params.workspaceId as string

  const list = useObservabilityListController(workspaceId)
  const detail = useTrajectoryDetailController({
    workspaceId,
    selectedLogId: list.selection.selectedLogId,
    fallbackWireLog: list.selection.selectedWireLog,
    isLive: true,
  })

  const { triggerVisualRefresh, refetchList } = list.refresh
  const { refetch: refetchDetail } = detail.detailQuery
  const selectedLogId = list.selection.selectedLogId

  const handleRefresh = useCallback(() => {
    triggerVisualRefresh()
    refetchList()
    if (selectedLogId) {
      refetchDetail()
    }
  }, [triggerVisualRefresh, refetchList, refetchDetail, selectedLogId])

  const { handleExport } = list.exportAction
  const { set: setViewMode } = list.viewMode

  useRegisterGlobalCommands(() => [
    { id: 'logs-refresh', handler: () => handleRefresh() },
    { id: 'logs-export', handler: () => void handleExport() },
    { id: 'logs-show-dashboard', handler: () => setViewMode('dashboard') },
    { id: 'logs-show-logs', handler: () => setViewMode('logs') },
    { id: 'logs-show-trajectory', handler: () => setViewMode('trajectory') },
  ])

  const rows: ResourceRow[] = useMemo(() => list.list.logViews.map(buildRow), [list.list.logViews])

  const refreshIcon = list.refresh.isVisuallyRefreshing ? SpinningRefreshCw : RefreshCw

  const headerActions = useMemo<ResourceAction[]>(
    () => [
      {
        text: 'Export',
        icon: Download,
        onSelect: handleExport,
        disabled: !detail.commands.canEdit || list.exportAction.isExporting || rows.length === 0,
      },
      {
        text: 'Refresh',
        icon: refreshIcon,
        onSelect: handleRefresh,
        disabled: list.refresh.isVisuallyRefreshing,
      },
      {
        text: 'Logs',
        onSelect: () => list.viewMode.set('logs'),
        active: list.viewMode.isLogsView,
      },
      {
        text: 'Dashboard',
        onSelect: () => list.viewMode.set('dashboard'),
        active: list.viewMode.isDashboardView,
      },
      {
        text: 'Trajectory',
        onSelect: () => list.viewMode.set('trajectory'),
        active: list.viewMode.isTrajectoryView,
      },
    ],
    [
      list.viewMode,
      list.exportAction.isExporting,
      list.refresh.isVisuallyRefreshing,
      refreshIcon,
      handleRefresh,
      handleExport,
      detail.commands.canEdit,
      rows.length,
    ]
  )

  const effectiveSidebarOpen =
    list.selection.isSidebarOpen &&
    (list.selection.selectedLogIndex !== -1 || detail.detailQuery.data != null)

  const suggestionsDropdown = useMemo(() => {
    const state = list.suggestionState
    if (!state.isOpen || state.suggestions.length === 0) return undefined
    const suggestionType =
      state.sections.length > 0 ? 'multi-section' : (state.suggestions[0]?.category ?? null)

    return (
      <div className='max-h-96 overflow-y-auto px-1'>
        {state.sections.length > 0 ? (
          <div className='py-1'>
            {state.suggestions[0]?.category === 'show-all' && (
              <SuggestionButton
                suggestion={state.suggestions[0]}
                index={0}
                highlighted={state.highlightedIndex === 0}
                onHover={state.setHighlightedIndex}
                onSelect={state.onSelect}
              />
            )}
            {state.sections.map((section) => (
              <div key={section.title}>
                <div className='px-3 py-1.5 text-[var(--text-tertiary)] text-caption uppercase tracking-wide'>
                  {section.title}
                </div>
                {section.suggestions.map((suggestion) => {
                  if (suggestion.category === 'show-all') return null
                  const index = state.suggestions.indexOf(suggestion)
                  return (
                    <SuggestionButton
                      key={suggestion.id}
                      suggestion={suggestion}
                      index={index}
                      highlighted={index === state.highlightedIndex}
                      onHover={state.setHighlightedIndex}
                      onSelect={state.onSelect}
                      showCategory
                    />
                  )
                })}
              </div>
            ))}
          </div>
        ) : (
          <div className='py-1'>
            {suggestionType === 'filters' && (
              <div className='px-3 py-1.5 text-[var(--text-tertiary)] text-caption uppercase tracking-wide'>
                SUGGESTED FILTERS
              </div>
            )}
            {state.suggestions.map((suggestion, index) => (
              <SuggestionButton
                key={suggestion.id}
                suggestion={suggestion}
                index={index}
                highlighted={index === state.highlightedIndex}
                onHover={state.setHighlightedIndex}
                onSelect={state.onSelect}
              />
            ))}
          </div>
        )}
      </div>
    )
  }, [list.suggestionState])

  const sidebarOverlay = (
    <LogDetails
      log={detail.detail}
      isOpen={effectiveSidebarOpen}
      onClose={list.selection.onCloseSidebar}
      onNavigateNext={list.selection.onNavigateNext}
      onNavigatePrev={list.selection.onNavigatePrev}
      hasNext={list.selection.hasNext}
      hasPrev={list.selection.hasPrev}
      onRetryExecution={() => detail.commands.retryRun(detail.wireDetail)}
      isRetryPending={detail.commands.isRetryPending}
      onActiveTabChange={list.detailTab.onActiveTabChange}
    />
  )

  return (
    <>
      <Resource>
        <Resource.Header icon={Library} title='Logs' actions={headerActions} />
        <Resource.Options
          search={{ ...list.searchConfig, dropdown: suggestionsDropdown }}
          sort={list.sortConfig}
          filter={{
            content: (
              <LogsFilterPanel
                searchQuery={list.filters.searchQuery}
                onSearchQueryChange={list.filters.setSearchQuery}
              />
            ),
          }}
          filterTags={list.filterTags}
        />
        {list.viewMode.isDashboardView ? (
          <div className='relative flex min-h-0 flex-1 flex-col overflow-auto'>
            <div className='flex min-h-0 flex-1 flex-col px-6'>
              <Dashboard
                stats={list.dashboard.query.data}
                isLoading={list.dashboard.query.isLoading}
                error={list.dashboard.query.error}
                searchQuery={list.dashboard.searchQuery}
              />
            </div>
            {sidebarOverlay}
          </div>
        ) : list.viewMode.isTrajectoryView ? (
          <div className='relative flex min-h-0 flex-1 flex-col overflow-auto'>
            <div className='flex min-h-0 flex-1 flex-col px-6'>
              <Trajectory logs={list.list.logViews} isLoading={list.list.query.isLoading} />
            </div>
            {sidebarOverlay}
          </div>
        ) : (
          <Resource.Table
            apiRef={list.tableRef}
            virtualized
            columns={LOG_COLUMNS}
            rows={rows}
            selectedRowId={list.selection.selectedLogId}
            onRowClick={list.selection.onRowClick}
            onRowHover={list.selection.onRowHover}
            onRowContextMenu={list.contextMenu.open}
            onLoadMore={list.list.loadMore}
            hasMore={list.list.query.hasNextPage ?? false}
            isLoadingMore={list.list.query.isFetchingNextPage}
            overlay={sidebarOverlay}
          />
        )}
      </Resource>

      <LogRowContextMenu
        isOpen={list.contextMenu.isOpen}
        position={list.contextMenu.position}
        onClose={list.contextMenu.close}
        log={list.contextMenu.logView}
        onCopyExecutionId={list.contextMenu.copyExecutionId}
        onCopyLink={list.contextMenu.copyLink}
        onOpenPreview={() => {
          if (list.contextMenu.logId) detail.preview.open(list.contextMenu.logId)
        }}
        onCancelExecution={() => detail.commands.cancelRun(list.contextMenu.wireLog)}
        onRetryExecution={() => detail.commands.retryRun(list.contextMenu.wireLog)}
        canCancelExecution={detail.commands.canEdit}
        isCancelPending={detail.commands.isCancelPending}
        cancelPendingExecutionId={detail.commands.cancelPendingExecutionId}
        isRetryPending={detail.commands.isRetryPending}
        onClearAllFilters={list.filters.resetFilters}
        hasActiveFilters={list.filtersActive}
      />

      {detail.preview.logId !== null && detail.preview.detail?.executionId && (
        <ExecutionSnapshot
          executionId={detail.preview.detail.executionId}
          traceSpans={detail.preview.detail.executionData?.traceSpans}
          isModal
          isOpen={detail.preview.logId !== null}
          onClose={detail.preview.close}
        />
      )}
    </>
  )
}

interface LogsFilterPanelProps {
  searchQuery: string
  onSearchQueryChange: (query: string) => void
}

function LogsFilterPanel({ searchQuery, onSearchQueryChange }: LogsFilterPanelProps) {
  const params = useParams()
  const workspaceId = params.workspaceId as string

  const {
    level,
    setLevel,
    folderIds,
    setFolderIds,
    triggers,
    setTriggers,
    timeRange,
    setTimeRange,
    startDate,
    endDate,
    setDateRange,
    clearDateRange,
    resetFilters,
    workflowIds,
  } = useLogFilters()

  const [datePickerOpen, setDatePickerOpen] = useState(false)
  const previousTimeRangeRef = useRef(timeRange)
  const dateRangeAppliedRef = useRef(false)
  const { data: folders = {} } = useFolderMap(workspaceId)

  const folderList = Object.values(folders).filter((f) => f.workspaceId === workspaceId)

  const selectedStatuses = level === 'all' || !level ? [] : level.split(',').filter(Boolean)

  const statusOptions: ComboboxOption[] = useMemo(
    () =>
      (Object.keys(STATUS_CONFIG) as RunStatus[])
        .filter((status) => STATUS_CONFIG[status].filterable)
        .map((status) => ({
          value: status,
          label: STATUS_CONFIG[status].label,
          icon: getColorIcon(STATUS_CONFIG[status].color),
        })),
    []
  )

  const handleStatusChange = (values: string[]) => {
    setLevel(values.length === 0 ? 'all' : values.join(','))
  }

  const statusDisplayLabel =
    selectedStatuses.length === 0
      ? 'Status'
      : selectedStatuses.length === 1
        ? statusOptions.find((s) => s.value === selectedStatuses[0])?.label || '1 selected'
        : `${selectedStatuses.length} selected`

  const selectedStatusColor =
    selectedStatuses.length === 1
      ? (STATUS_CONFIG[selectedStatuses[0] as RunStatus]?.color ?? null)
      : null

  const folderOptions: ComboboxOption[] = folderList.map((f) => ({ value: f.id, label: f.name }))

  const folderDisplayLabel =
    folderIds.length === 0
      ? 'Folder'
      : folderIds.length === 1
        ? folderList.find((f) => f.id === folderIds[0])?.name || '1 selected'
        : `${folderIds.length} folders`

  const triggerOptions: ComboboxOption[] = useMemo(
    () =>
      getTriggerOptions().map((t) => ({
        value: t.value,
        label: t.label,
      })),
    []
  )

  const triggerDisplayLabel =
    triggers.length === 0
      ? 'Trigger'
      : triggers.length === 1
        ? triggerOptions.find((t) => t.value === triggers[0])?.label || '1 selected'
        : `${triggers.length} triggers`

  const timeDisplayLabel =
    timeRange === 'All time'
      ? 'Time'
      : timeRange === 'Custom range' && startDate && endDate
        ? `${formatDateShort(startDate)} - ${formatDateShort(endDate)}`
        : timeRange === 'Custom range'
          ? 'Custom range'
          : timeRange

  const handleTimeRangeChange = (val: string) => {
    if (val === 'Custom range') {
      previousTimeRangeRef.current = timeRange
      setDatePickerOpen(true)
    } else {
      clearDateRange()
      setTimeRange(val as typeof timeRange)
    }
  }

  const handleDateRangeApply = (start: string, end: string) => {
    dateRangeAppliedRef.current = true
    setDateRange(start, end)
    setDatePickerOpen(false)
  }

  const handleDatePickerCancel = () => {
    if (timeRange === 'Custom range' && !startDate) {
      setTimeRange(previousTimeRangeRef.current)
    }
    setDatePickerOpen(false)
  }

  const filtersActive = hasActiveFilters({
    timeRange,
    level,
    workflowIds,
    folderIds,
    triggers,
    searchQuery,
  })

  const handleClearFilters = () => {
    resetFilters()
    onSearchQueryChange('')
  }

  return (
    <div className='flex w-[240px] flex-col gap-4 p-3'>
      <div className='flex flex-col gap-[9px]'>
        <span className='text-[var(--text-muted)] text-small'>Status</span>
        <ChipCombobox
          options={statusOptions}
          multiSelect
          multiSelectValues={selectedStatuses}
          onMultiSelectChange={handleStatusChange}
          placeholder='All statuses'
          overlayContent={
            <span className='flex items-center gap-1.5 truncate text-[var(--text-primary)]'>
              {selectedStatusColor && (
                <div
                  className='flex-shrink-0 rounded-[3px]'
                  style={{ backgroundColor: selectedStatusColor, width: 8, height: 8 }}
                />
              )}
              <span className='truncate'>{statusDisplayLabel}</span>
            </span>
          }
          showAllOption
          allOptionLabel='All statuses'
          className='w-full'
        />
      </div>

      <div className='flex flex-col gap-[9px]'>
        <span className='text-[var(--text-muted)] text-small'>Folder</span>
        <ChipCombobox
          options={folderOptions}
          multiSelect
          multiSelectValues={folderIds}
          onMultiSelectChange={setFolderIds}
          placeholder='All folders'
          overlayContent={
            <span className='truncate text-[var(--text-primary)]'>{folderDisplayLabel}</span>
          }
          searchable
          searchPlaceholder='Search folders...'
          showAllOption
          allOptionLabel='All folders'
          className='w-full'
        />
      </div>

      <div className='flex flex-col gap-[9px]'>
        <span className='text-[var(--text-muted)] text-small'>Trigger</span>
        <ChipCombobox
          options={triggerOptions}
          multiSelect
          multiSelectValues={triggers}
          onMultiSelectChange={setTriggers}
          placeholder='All triggers'
          overlayContent={
            <span className='truncate text-[var(--text-primary)]'>{triggerDisplayLabel}</span>
          }
          searchable
          searchPlaceholder='Search triggers...'
          showAllOption
          allOptionLabel='All triggers'
          className='w-full'
        />
      </div>

      <div className='flex flex-col gap-[9px]'>
        <span className='text-[var(--text-muted)] text-small'>Time Range</span>
        <div className='relative'>
          <ChipCombobox
            options={TIME_RANGE_OPTIONS}
            value={timeRange}
            onChange={handleTimeRangeChange}
            placeholder='All time'
            overlayContent={
              <span className='truncate text-[var(--text-primary)]'>{timeDisplayLabel}</span>
            }
            className='w-full'
            maxHeight={320}
          />
          <Popover
            open={datePickerOpen}
            onOpenChange={(isOpen) => {
              if (!isOpen) {
                if (dateRangeAppliedRef.current) {
                  dateRangeAppliedRef.current = false
                } else {
                  handleDatePickerCancel()
                }
              }
            }}
          >
            <PopoverAnchor className='pointer-events-none absolute inset-0' />
            <PopoverContent align='start' sideOffset={4} className='w-auto p-0'>
              <Calendar
                mode='range'
                showTime
                startDate={startDate}
                endDate={endDate}
                onRangeChange={handleDateRangeApply}
                onCancel={handleDatePickerCancel}
              />
            </PopoverContent>
          </Popover>
        </div>
      </div>

      {filtersActive && (
        <Button
          variant='active'
          onClick={handleClearFilters}
          className='h-[32px] w-full rounded-md'
        >
          Clear All Filters
        </Button>
      )}
    </div>
  )
}

function SuggestionButton({
  suggestion,
  index,
  highlighted,
  onHover,
  onSelect,
  showCategory,
}: {
  suggestion: Suggestion
  index: number
  highlighted: boolean
  onHover: (i: number) => void
  onSelect: (s: Suggestion) => void
  showCategory?: boolean
}) {
  return (
    <Button
      type='button'
      variant='ghost'
      data-index={index}
      className={cn(
        'h-auto w-full justify-start rounded-md px-3 py-2 text-left transition-colors hover-hover:bg-[var(--surface-5)]',
        highlighted && 'bg-[var(--surface-5)]'
      )}
      onMouseEnter={() => onHover(index)}
      onMouseDown={(e) => {
        e.preventDefault()
        onSelect(suggestion)
      }}
    >
      <div className='flex w-full items-center justify-between gap-3'>
        <div className='min-w-0 flex-1 truncate text-small'>{suggestion.label}</div>
        {showCategory && suggestion.value !== suggestion.label && (
          <div className='shrink-0 font-mono text-[var(--text-muted)] text-xs'>
            {suggestion.category === 'folder' ? 'folder:' : ''}
          </div>
        )}
        {!showCategory && suggestion.description && (
          <div className='shrink-0 text-[var(--text-muted)] text-xs'>{suggestion.value}</div>
        )}
      </div>
    </Button>
  )
}
