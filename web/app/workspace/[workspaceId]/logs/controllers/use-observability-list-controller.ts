'use client'

import {
  type MouseEvent as ReactMouseEvent,
  useCallback,
  useEffect,
  useEffectEvent,
  useMemo,
  useReducer,
  useRef,
  useState,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useQueryState } from 'nuqs'
import type { ExecutionLogSummary } from '@/lib/api/contracts/logs'
import { formatDateShort } from '@/lib/core/utils/date-display'
import { API_BASE } from '@/lib/lingxi/api'
import {
  getEndDateFromTimeRange,
  getStartDateFromTimeRange,
  hasActiveFilters,
} from '@/lib/logs/filters'
import { getTriggerOptions } from '@/lib/logs/get-trigger-options'
import { type ParsedFilter, parseQuery, queryToApiParams } from '@/lib/logs/query-parser'
import { type FolderData, SearchSuggestions, type TriggerData } from '@/lib/logs/search-suggestions'
import { SEARCH_DEBOUNCE_MS } from '@/lib/url-state'
import type {
  FilterTag,
  ResourceTableHandle,
  SearchConfig,
  SortConfig,
} from '@/app/workspace/[workspaceId]/components'
import { useLogFilters } from '@/app/workspace/[workspaceId]/logs/hooks/use-log-filters'
import { useSearchState } from '@/app/workspace/[workspaceId]/logs/hooks/use-search-state'
import type { RunStatus } from '@/app/workspace/[workspaceId]/logs/model/execution-log'
import { mapExecutionLogSummary } from '@/app/workspace/[workspaceId]/logs/model/execution-log-mapper'
import {
  executionIdParam,
  executionIdWriteOptions,
  logDetailsTabParam,
  logDetailsTabUrlKeys,
  logFilterUrlKeys,
  logSortParams,
} from '@/app/workspace/[workspaceId]/logs/search-params'
import { STATUS_CONFIG } from '@/app/workspace/[workspaceId]/logs/utils'
import { useFolderMap, useFolders } from '@/hooks/queries/folders'
import {
  prefetchLogDetail,
  useDashboardStats,
  useLogByExecutionId,
  useLogsList,
} from '@/hooks/queries/logs'
import { useDebounce } from '@/hooks/use-debounce'
import { useUrlSort } from '@/hooks/use-url-sort'
import { useFilterStore } from '@/stores/logs/filters/store'
import type { LogViewMode } from '@/lib/logs/filter-types'

const LOGS_PER_PAGE = 50 as const
const REFRESH_SPINNER_DURATION_MS = 1000 as const
const LIVE_REFRESH_INTERVAL_MS = 10_000 as const

interface LogSelectionState {
  selectedLogId: string | null
  isSidebarOpen: boolean
}

type LogSelectionAction =
  | { type: 'TOGGLE_LOG'; logId: string }
  | { type: 'SELECT_LOG'; logId: string }
  | { type: 'CLOSE_SIDEBAR' }
  | { type: 'TOGGLE_SIDEBAR' }

function logSelectionReducer(
  state: LogSelectionState,
  action: LogSelectionAction
): LogSelectionState {
  switch (action.type) {
    case 'TOGGLE_LOG':
      if (state.selectedLogId === action.logId && state.isSidebarOpen) {
        return { selectedLogId: null, isSidebarOpen: false }
      }
      return { selectedLogId: action.logId, isSidebarOpen: true }
    case 'SELECT_LOG':
      return { ...state, selectedLogId: action.logId }
    case 'CLOSE_SIDEBAR':
      return { selectedLogId: null, isSidebarOpen: false }
    case 'TOGGLE_SIDEBAR':
      return state.selectedLogId ? { ...state, isSidebarOpen: !state.isSidebarOpen } : state
    default:
      return state
  }
}

/**
 * List controller for the Logs observability surface: filtering, sorting,
 * pagination, selection/navigation, live refresh, export, and the filter-bar
 * search state. It owns wire rows and their mapped view models; presentation
 * components render from the view models only.
 *
 * The controller is the single place allowed to touch the legacy wire fields
 * (e.g. resolving a filter tag's source name from the row payload). It never
 * queries workflow entities.
 */
export function useObservabilityListController(workspaceId: string) {
  const {
    timeRange,
    startDate,
    endDate,
    level,
    workflowIds,
    folderIds,
    searchQuery: urlSearchQuery,
    setSearchQuery: setUrlSearchQuery,
    triggers,
    resetFilters,
    setLevel,
    setWorkflowIds,
    setFolderIds,
    setTriggers,
    setTimeRange,
    setDateRange,
    clearDateRange,
  } = useLogFilters()

  const viewMode = useFilterStore((s) => s.viewMode)
  const setViewMode = useFilterStore((s) => s.setViewMode)
  const isLogsView = viewMode === 'logs'
  const isDashboardView = viewMode === 'dashboard'
  const isTrajectoryView = viewMode === 'trajectory'

  const [{ selectedLogId, isSidebarOpen }, dispatch] = useReducer(logSelectionReducer, {
    selectedLogId: null,
    isSidebarOpen: false,
  })

  const [executionId, setExecutionId] = useQueryState(executionIdParam.key, executionIdParam.parser)
  const [pendingExecutionId, setPendingExecutionId] = useState<string | null>(() => executionId)

  /**
   * The log-details `tab` param is owned/written by the details panel, but the
   * list must clear it when the panel closes so a lingering `?tab=trace` never
   * carries over to the next run opened from the list.
   */
  const [, setLogDetailsTab] = useQueryState(logDetailsTabParam.key, {
    ...logDetailsTabParam.parser,
    ...logDetailsTabUrlKeys,
  })

  /**
   * `urlSearchQuery` is the instant nuqs value (its URL write is debounced inside
   * `useLogFilters`); the query/filtering still debounce off it to avoid
   * per-keystroke fetches. The raw value is written to the URL, so trim here on
   * read — the server keeps receiving a trimmed query.
   */
  const debouncedSearchQuery = useDebounce(urlSearchQuery, SEARCH_DEBOUNCE_MS).trim()

  const isLive = true
  const [isVisuallyRefreshing, setIsVisuallyRefreshing] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const refreshTimersRef = useRef(new Set<number>())
  const wireLogsRef = useRef<ExecutionLogSummary[]>([])
  const selectedLogIndexRef = useRef(-1)
  const selectedLogIdRef = useRef<string | null>(null)
  const isSidebarOpenRef = useRef(false)
  const shouldScrollIntoViewRef = useRef(false)
  const resourceTableRef = useRef<ResourceTableHandle>(null)
  const logsRefetchRef = useRef<() => void>(() => {})
  const activeTabRef = useRef<string>('overview')
  const logsQueryRef = useRef({ isFetching: false, hasNextPage: false, fetchNextPage: () => {} })

  /**
   * URL-backed sort (`sort` + `dir`). The defaults match the server's default
   * ordering, so a clean URL means "no active sort" and clearing the sort
   * writes the defaults back (which `clearOnDefault` strips from the URL).
   */
  const {
    sort: sortBy,
    dir: sortOrder,
    activeSort,
    onSort,
    onClear: onClearSort,
  } = useUrlSort(logSortParams, logFilterUrlKeys)

  const [contextMenu, setContextMenu] = useState<{
    isOpen: boolean
    position: { x: number; y: number }
    logId: string | null
  }>({ isOpen: false, position: { x: 0, y: 0 }, logId: null })

  const queryClient = useQueryClient()

  const logFilters = useMemo(
    () => ({
      timeRange,
      startDate,
      endDate,
      level,
      workflowIds,
      folderIds,
      triggers,
      searchQuery: debouncedSearchQuery,
      limit: LOGS_PER_PAGE,
      sortBy,
      sortOrder,
    }),
    [
      timeRange,
      startDate,
      endDate,
      level,
      workflowIds,
      folderIds,
      triggers,
      debouncedSearchQuery,
      sortBy,
      sortOrder,
    ]
  )

  const logsQuery = useLogsList(workspaceId, logFilters, {
    refetchInterval: isLive ? LIVE_REFRESH_INTERVAL_MS : false,
  })

  const dashboardFilters = useMemo(
    () => ({
      timeRange,
      startDate,
      endDate,
      level,
      workflowIds,
      folderIds,
      triggers,
      searchQuery: debouncedSearchQuery,
    }),
    [timeRange, startDate, endDate, level, workflowIds, folderIds, triggers, debouncedSearchQuery]
  )

  const dashboardStatsQuery = useDashboardStats(workspaceId, dashboardFilters, {
    enabled: isDashboardView,
    refetchInterval: isLive ? LIVE_REFRESH_INTERVAL_MS : false,
  })

  const wireLogs = useMemo(() => {
    return logsQuery.data?.pages?.flatMap((page) => page.logs) ?? []
  }, [logsQuery.data?.pages])

  /** Native view models — the only shape presentation consumes. */
  const logViews = useMemo(() => wireLogs.map(mapExecutionLogSummary), [wireLogs])

  const selectedLogIndex = selectedLogId ? wireLogs.findIndex((l) => l.id === selectedLogId) : -1
  const selectedWireLog = selectedLogIndex >= 0 ? wireLogs[selectedLogIndex] : null

  const handleLogHover = useCallback(
    (rowId: string) => {
      prefetchLogDetail(queryClient, rowId, workspaceId)
    },
    [queryClient, workspaceId]
  )

  useFolders(workspaceId)

  wireLogsRef.current = wireLogs
  selectedLogIndexRef.current = selectedLogIndex
  selectedLogIdRef.current = selectedLogId
  isSidebarOpenRef.current = isSidebarOpen
  logsRefetchRef.current = logsQuery.refetch
  logsQueryRef.current = {
    isFetching: logsQuery.isFetching,
    hasNextPage: logsQuery.hasNextPage ?? false,
    fetchNextPage: logsQuery.fetchNextPage,
  }

  const deepLinkQuery = useLogByExecutionId(workspaceId, pendingExecutionId)

  useEffect(() => {
    if (!pendingExecutionId) return
    const resolvedId = deepLinkQuery.data?.id
    if (resolvedId) {
      dispatch({ type: 'TOGGLE_LOG', logId: resolvedId })
      setPendingExecutionId(null)
    } else if (deepLinkQuery.isError) {
      setPendingExecutionId(null)
    }
  }, [pendingExecutionId, deepLinkQuery.data, deepLinkQuery.isError])

  useEffect(() => {
    const timers = refreshTimersRef.current
    return () => {
      timers.forEach((id) => window.clearTimeout(id))
      timers.clear()
    }
  }, [])

  /**
   * The single write path for user-driven `executionId` changes. Cancels any
   * in-flight deep-link resolution first — an explicit interaction supersedes
   * it, otherwise the resolved row would open over the user's selection and
   * leave the URL pointing at a different run than the panel shows.
   */
  const writeExecutionId = useCallback(
    (value: string | null) => {
      setPendingExecutionId(null)
      void setExecutionId(value, executionIdWriteOptions)
    },
    [setExecutionId]
  )

  /**
   * Mirrors the reducer's TOGGLE_LOG branch: clicking the already-open row
   * closes the sidebar (strip `executionId`); any other click opens the row
   * (sync `executionId` to it so the URL always deep-links the open run).
   */
  const handleLogClick = useCallback(
    (rowId: string) => {
      const opens = !(selectedLogIdRef.current === rowId && isSidebarOpenRef.current)
      dispatch({ type: 'TOGGLE_LOG', logId: rowId })
      if (opens) {
        const log = wireLogsRef.current.find((l) => l.id === rowId)
        writeExecutionId(log?.executionId ?? null)
      } else {
        writeExecutionId(null)
      }
    },
    [writeExecutionId]
  )

  const handleNavigateNext = useCallback(() => {
    const idx = selectedLogIndexRef.current
    const currentLogs = wireLogsRef.current
    if (idx >= 0 && idx < currentLogs.length - 1) {
      const nextLog = currentLogs[idx + 1]
      shouldScrollIntoViewRef.current = true
      dispatch({ type: 'SELECT_LOG', logId: nextLog.id })
      if (isSidebarOpenRef.current) {
        writeExecutionId(nextLog.executionId ?? null)
      }
    }
  }, [writeExecutionId])

  const handleNavigatePrev = useCallback(() => {
    const idx = selectedLogIndexRef.current
    const currentLogs = wireLogsRef.current
    if (idx > 0) {
      const prevLog = currentLogs[idx - 1]
      shouldScrollIntoViewRef.current = true
      dispatch({ type: 'SELECT_LOG', logId: prevLog.id })
      if (isSidebarOpenRef.current) {
        writeExecutionId(prevLog.executionId ?? null)
      }
    }
  }, [writeExecutionId])

  const handleCloseSidebar = useCallback(() => {
    dispatch({ type: 'CLOSE_SIDEBAR' })
    writeExecutionId(null)
    activeTabRef.current = 'overview'
  }, [writeExecutionId])

  /**
   * Strip the `tab` param whenever the detail panel transitions from open to
   * closed — by the X button, toggling the same row, or the keyboard — so
   * reopening another log starts on overview rather than inheriting the closed
   * log's tab. Guarded on a prior-open ref so an initial deep-linked `?tab=` is
   * preserved (the panel isn't open yet on first mount).
   */
  const wasSidebarOpenRef = useRef(false)
  useEffect(() => {
    if (isSidebarOpen) {
      wasSidebarOpenRef.current = true
    } else if (wasSidebarOpenRef.current) {
      wasSidebarOpenRef.current = false
      setLogDetailsTab(null)
    }
  }, [isSidebarOpen, setLogDetailsTab])

  const handleActiveTabChange = useCallback((tab: string) => {
    activeTabRef.current = tab
  }, [])

  const handleLogContextMenu = useCallback((e: ReactMouseEvent, rowId: string) => {
    e.preventDefault()
    setContextMenu({ isOpen: true, position: { x: e.clientX, y: e.clientY }, logId: rowId })
  }, [])

  const closeContextMenu = useCallback(() => {
    setContextMenu((prev) => ({ ...prev, isOpen: false }))
  }, [])

  const contextMenuWireLog = contextMenu.logId
    ? (wireLogs.find((l) => l.id === contextMenu.logId) ?? null)
    : null
  const contextMenuLogView = contextMenu.logId
    ? (logViews.find((v) => v.identity.logId === contextMenu.logId) ?? null)
    : null

  const copyContextExecutionId = useCallback(() => {
    if (contextMenuWireLog?.executionId) {
      navigator.clipboard.writeText(contextMenuWireLog.executionId).catch(() => {})
    }
  }, [contextMenuWireLog])

  const copyContextLink = useCallback(() => {
    if (contextMenuWireLog?.executionId) {
      const url = `${window.location.origin}/workspace/${workspaceId}/logs?executionId=${contextMenuWireLog.executionId}`
      navigator.clipboard.writeText(url).catch(() => {})
    }
  }, [contextMenuWireLog, workspaceId])

  const filtersActive = hasActiveFilters({
    timeRange,
    level,
    workflowIds,
    folderIds,
    triggers,
    searchQuery: debouncedSearchQuery,
  })

  const handleClearAllFilters = useCallback(() => {
    resetFilters()
  }, [resetFilters])

  useEffect(() => {
    if (!selectedLogId || !shouldScrollIntoViewRef.current) return
    shouldScrollIntoViewRef.current = false
    // Route through the virtualizer; a querySelector would miss windowed-out rows.
    resourceTableRef.current?.scrollToRow(selectedLogId)
  }, [selectedLogId, selectedLogIndex])

  const triggerVisualRefresh = useCallback(() => {
    setIsVisuallyRefreshing(true)
    const timerId = window.setTimeout(() => {
      setIsVisuallyRefreshing(false)
      refreshTimersRef.current.delete(timerId)
    }, REFRESH_SPINNER_DURATION_MS)
    refreshTimersRef.current.add(timerId)
  }, [])

  const prevIsFetchingRef = useRef(logsQuery.isFetching)
  useEffect(() => {
    const wasFetching = prevIsFetchingRef.current
    const isFetching = logsQuery.isFetching
    prevIsFetchingRef.current = isFetching

    if (isLive && !wasFetching && isFetching) {
      triggerVisualRefresh()
    }
  }, [logsQuery.isFetching, isLive, triggerVisualRefresh])

  const handleExport = useCallback(async () => {
    setIsExporting(true)
    try {
      const params = new URLSearchParams()
      params.set('workspaceId', workspaceId)
      if (level !== 'all') params.set('level', level)
      if (triggers.length > 0) params.set('triggers', triggers.join(','))
      if (workflowIds.length > 0) params.set('workflowIds', workflowIds.join(','))
      if (folderIds.length > 0) params.set('folderIds', folderIds.join(','))

      const computedStartDate = getStartDateFromTimeRange(timeRange, startDate)
      if (computedStartDate) {
        params.set('startDate', computedStartDate.toISOString())
      }

      const computedEndDate = getEndDateFromTimeRange(timeRange, endDate)
      if (computedEndDate) {
        params.set('endDate', computedEndDate.toISOString())
      }

      const parsed = parseQuery(debouncedSearchQuery)
      const extra = queryToApiParams(parsed)
      Object.entries(extra).forEach(([k, v]) => params.set(k, v))

      const url = `${API_BASE}/api/logs/export?${params.toString()}`
      const a = document.createElement('a')
      a.href = url
      a.download = 'logs_export.csv'
      document.body.appendChild(a)
      a.click()
      a.remove()
    } finally {
      setIsExporting(false)
    }
  }, [
    workspaceId,
    level,
    triggers,
    workflowIds,
    folderIds,
    timeRange,
    startDate,
    endDate,
    debouncedSearchQuery,
  ])

  const loadMoreLogs = useCallback(() => {
    const { isFetching, hasNextPage, fetchNextPage } = logsQueryRef.current
    if (!isFetching && hasNextPage) {
      fetchNextPage()
    }
  }, [])

  const handleNavigateNextEvent = useEffectEvent(handleNavigateNext)
  const handleNavigatePrevEvent = useEffectEvent(handleNavigatePrev)
  const writeExecutionIdEvent = useEffectEvent((value: string | null) => {
    writeExecutionId(value)
  })

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (activeTabRef.current === 'trace') return
      const currentLogs = wireLogsRef.current
      const currentIndex = selectedLogIndexRef.current
      if (currentLogs.length === 0) return

      if (currentIndex === -1 && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
        e.preventDefault()
        shouldScrollIntoViewRef.current = true
        dispatch({ type: 'SELECT_LOG', logId: currentLogs[0].id })
        return
      }

      if (e.key === 'ArrowUp' && !e.metaKey && !e.ctrlKey && currentIndex > 0) {
        e.preventDefault()
        handleNavigatePrevEvent()
      }

      if (
        e.key === 'ArrowDown' &&
        !e.metaKey &&
        !e.ctrlKey &&
        currentIndex < currentLogs.length - 1
      ) {
        e.preventDefault()
        handleNavigateNextEvent()
      }

      if (e.key === 'Enter' && selectedLogIdRef.current) {
        e.preventDefault()
        const willOpen = !isSidebarOpenRef.current
        dispatch({ type: 'TOGGLE_SIDEBAR' })
        if (willOpen) {
          const log = currentLogs.find((l) => l.id === selectedLogIdRef.current)
          writeExecutionIdEvent(log?.executionId ?? null)
        } else {
          writeExecutionIdEvent(null)
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const { data: folders = {} } = useFolderMap(workspaceId)

  const filterTags = useMemo<FilterTag[]>(() => {
    const tags: FilterTag[] = []

    if (level && level !== 'all') {
      const statuses = level.split(',').filter(Boolean)
      const labels = statuses.map((s) => STATUS_CONFIG[s as RunStatus]?.label ?? s)
      tags.push({
        label: `Status: ${labels.join(', ')}`,
        onRemove: () => setLevel('all'),
      })
    }

    if (workflowIds.length > 0) {
      // Wire-compat display only: source names resolve from the already-loaded
      // log rows (or the dashboard stats payload) — never from a workflow query.
      const names = workflowIds.map(
        (id) =>
          wireLogs.find((l) => l.workflow?.id === id || l.workflowId === id)?.workflow?.name ??
          id.slice(0, 8)
      )
      tags.push({
        label: `Source: ${names.join(', ')}`,
        onRemove: () => setWorkflowIds([]),
      })
    }

    if (folderIds.length > 0) {
      const names = folderIds.map((id) => folders[id]?.name ?? id.slice(0, 8))
      tags.push({
        label: `Folder: ${names.join(', ')}`,
        onRemove: () => setFolderIds([]),
      })
    }

    if (triggers.length > 0) {
      tags.push({
        label: `Trigger: ${triggers.join(', ')}`,
        onRemove: () => setTriggers([]),
      })
    }

    if (timeRange !== 'All time') {
      tags.push({
        label:
          timeRange === 'Custom range' && startDate && endDate
            ? `${formatDateShort(startDate)} – ${formatDateShort(endDate)}`
            : timeRange,
        onRemove: () => {
          clearDateRange()
          setTimeRange('All time')
        },
      })
    }

    return tags
  }, [
    level,
    setLevel,
    workflowIds,
    setWorkflowIds,
    wireLogs,
    folderIds,
    setFolderIds,
    folders,
    triggers,
    setTriggers,
    timeRange,
    startDate,
    endDate,
    clearDateRange,
    setTimeRange,
  ])

  const foldersData = useMemo<FolderData[]>(
    () => Object.values(folders).map((f) => ({ id: f.id, name: f.name })),
    [folders]
  )
  const triggersData = useMemo<TriggerData[]>(
    () => getTriggerOptions().map((t) => ({ value: t.value, label: t.label, color: t.color })),
    []
  )
  const suggestionEngine = useMemo(
    () => new SearchSuggestions(foldersData, triggersData),
    [foldersData, triggersData]
  )

  const handleFiltersChange = useCallback(
    (filters: ParsedFilter[], textSearch: string) => {
      const filterStrings = filters.map(
        (f) => `${f.field}:${f.operator !== '=' ? f.operator : ''}${f.originalValue}`
      )
      const fullQuery = [...filterStrings, textSearch].filter(Boolean).join(' ')
      setUrlSearchQuery(fullQuery)
    },
    [setUrlSearchQuery]
  )

  const getSuggestions = useCallback(
    (input: string) => suggestionEngine.getSuggestions(input),
    [suggestionEngine]
  )

  const {
    appliedFilters,
    currentInput,
    textSearch,
    isOpen: isSuggestionsOpen,
    suggestions,
    sections,
    highlightedIndex,
    highlightedBadgeIndex,
    inputRef: searchInputRef,
    dropdownRef: searchDropdownRef,
    handleInputChange: handleSearchInputChange,
    handleSuggestionSelect,
    handleKeyDown: handleSearchKeyDown,
    handleFocus: handleSearchFocus,
    handleBlur: handleSearchBlur,
    removeBadge,
    clearAll: clearSearch,
    setHighlightedIndex,
    initializeFromQuery,
  } = useSearchState({
    onFiltersChange: handleFiltersChange,
    getSuggestions,
  })

  const lastExternalSearchValue = useRef<string | undefined>(undefined)
  useEffect(() => {
    if (urlSearchQuery === lastExternalSearchValue.current) return
    const isMount = lastExternalSearchValue.current === undefined
    lastExternalSearchValue.current = urlSearchQuery
    // On mount with no initial query, skip the no-op parse
    if (isMount && !urlSearchQuery) return
    const parsed = parseQuery(urlSearchQuery)
    initializeFromQuery(parsed.textSearch, parsed.filters)
  }, [urlSearchQuery, initializeFromQuery])

  useEffect(() => {
    if (!isSuggestionsOpen || highlightedIndex < 0) return
    const container = searchDropdownRef.current
    const el = container?.querySelector(`[data-index="${highlightedIndex}"]`)
    if (container && el) {
      el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  }, [isSuggestionsOpen, highlightedIndex, searchDropdownRef])

  const searchTags = useMemo(
    () => [
      ...appliedFilters.map((f, i) => ({
        label: f.field,
        value: `${f.operator !== '=' ? f.operator : ''}${f.originalValue}`,
        onRemove: () => removeBadge(i),
      })),
      ...(textSearch
        ? [
            {
              label: 'search',
              value: textSearch,
              onRemove: () => handleFiltersChange(appliedFilters, ''),
            },
          ]
        : []),
    ],
    [appliedFilters, textSearch, removeBadge, handleFiltersChange]
  )

  const sortConfig = useMemo<SortConfig>(
    () => ({
      options: [
        { id: 'date', label: 'Date' },
        { id: 'duration', label: 'Duration' },
        { id: 'cost', label: 'Cost' },
        { id: 'status', label: 'Status' },
      ],
      active: activeSort,
      onSort,
      onClear: onClearSort,
    }),
    [activeSort, onSort, onClearSort]
  )

  const searchConfig = useMemo<Omit<SearchConfig, 'dropdown'>>(
    () => ({
      value: currentInput,
      onChange: handleSearchInputChange,
      placeholder: 'Search logs...',
      inputRef: searchInputRef,
      onKeyDown: handleSearchKeyDown,
      onFocus: handleSearchFocus,
      onBlur: handleSearchBlur,
      tags: searchTags.length > 0 ? searchTags : undefined,
      highlightedTagIndex: highlightedBadgeIndex,
      onClearAll: clearSearch,
      dropdownRef: searchDropdownRef,
    }),
    [
      currentInput,
      handleSearchInputChange,
      searchInputRef,
      handleSearchKeyDown,
      handleSearchFocus,
      handleSearchBlur,
      searchTags,
      highlightedBadgeIndex,
      clearSearch,
      searchDropdownRef,
    ]
  )

  const suggestionState = useMemo(
    () => ({
      isOpen: isSuggestionsOpen,
      suggestions,
      sections,
      highlightedIndex,
      setHighlightedIndex,
      onSelect: handleSuggestionSelect,
    }),
    [
      isSuggestionsOpen,
      suggestions,
      sections,
      highlightedIndex,
      setHighlightedIndex,
      handleSuggestionSelect,
    ]
  )

  return {
    filters: {
      timeRange,
      startDate,
      endDate,
      level,
      workflowIds,
      folderIds,
      triggers,
      searchQuery: urlSearchQuery,
      setSearchQuery: setUrlSearchQuery,
      setLevel,
      setWorkflowIds,
      setFolderIds,
      setTriggers,
      setTimeRange,
      setDateRange,
      clearDateRange,
      resetFilters,
    },
    filtersActive,
    filterTags,
    viewMode: {
      value: viewMode as LogViewMode,
      set: setViewMode,
      isLogsView,
      isDashboardView,
      isTrajectoryView,
    },
    sortConfig,
    searchConfig,
    suggestionState,
    list: {
      wireLogs,
      logViews,
      query: logsQuery,
      loadMore: loadMoreLogs,
    },
    dashboard: {
      query: dashboardStatsQuery,
      searchQuery: debouncedSearchQuery,
    },
    selection: {
      selectedLogId,
      isSidebarOpen,
      selectedLogIndex,
      selectedWireLog,
      hasNext: selectedLogIndex >= 0 && selectedLogIndex < wireLogs.length - 1,
      hasPrev: selectedLogIndex > 0,
      onRowClick: handleLogClick,
      onNavigateNext: handleNavigateNext,
      onNavigatePrev: handleNavigatePrev,
      onCloseSidebar: handleCloseSidebar,
      onRowHover: handleLogHover,
    },
    contextMenu: {
      isOpen: contextMenu.isOpen,
      position: contextMenu.position,
      logId: contextMenu.logId,
      wireLog: contextMenuWireLog,
      logView: contextMenuLogView,
      open: handleLogContextMenu,
      close: closeContextMenu,
      copyExecutionId: copyContextExecutionId,
      copyLink: copyContextLink,
    },
    refresh: {
      isVisuallyRefreshing,
      triggerVisualRefresh,
      refetchList: logsQuery.refetch,
    },
    exportAction: {
      isExporting,
      handleExport,
    },
    tableRef: resourceTableRef,
    detailTab: {
      activeTabRef,
      onActiveTabChange: handleActiveTabChange,
    },
  }
}

export type ObservabilityListController = ReturnType<typeof useObservabilityListController>
