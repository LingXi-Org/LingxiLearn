import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, type WorkspaceTableItem } from '@/lib/lingxi/api'
import type { WorkspaceTableViewItem } from '@/lib/lingxi/types'
import { createTableGridProjection, filterAndSortTableRows } from './table-grid'

interface TableDetailState {
  table: WorkspaceTableItem | null
  rows: Array<Record<string, unknown>>
  loading: boolean
  error: string | null
  views: WorkspaceTableViewItem[]
}

const INITIAL_STATE: TableDetailState = {
  table: null,
  rows: [],
  loading: true,
  error: null,
  views: [],
}

/**
 * Shared Lingxi-native domain controller used by both page and embedded shells.
 * WorkspaceTable is read-only, so unsupported mutation/import/execution state is absent.
 */
export function useTableDetailController(tableId: string) {
  const [state, setState] = useState<TableDetailState>(INITIAL_STATE)
  const requestIdRef = useRef(0)
  const [query, setQuery] = useState('')
  const [sortKey, setSortKey] = useState('')
  const [descending, setDescending] = useState(false)
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null)

  const reload = useCallback(async () => {
    const requestId = ++requestIdRef.current
    setState((current) => ({ ...current, loading: true, error: null }))
    try {
      const [tableResult, rowResult, viewResult] = await Promise.all([
        api.workspaceTable(tableId),
        api.workspaceTableRows(tableId),
        api.workspaceTableViews(tableId),
      ])
      if (requestId !== requestIdRef.current) return
      setState({
        table: tableResult.data.table,
        rows: rowResult.data.rows ?? [],
        loading: false,
        error: null,
        views: viewResult.data.views ?? [],
      })
    } catch (error) {
      if (requestId !== requestIdRef.current) return
      setState((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : '无法加载学习记录',
      }))
    }
  }, [tableId])

  useEffect(() => {
    void reload()
    return () => {
      requestIdRef.current += 1
    }
  }, [reload])

  const grid = useMemo(
    () =>
      createTableGridProjection(
        state.table,
        filterAndSortTableRows(state.rows, query, sortKey, descending)
      ),
    [descending, query, sortKey, state.table, state.rows]
  )

  const applyView = useCallback(
    (viewId: string) => {
      const view = state.views.find((candidate) => candidate.id === viewId)
      if (!view) return
      setQuery(typeof view.config.query === 'string' ? view.config.query : '')
      setSortKey(typeof view.config.sortKey === 'string' ? view.config.sortKey : '')
      setDescending(view.config.descending === true)
    },
    [state.views]
  )

  const saveView = useCallback(
    async (name: string) => {
      const result = await api.createWorkspaceTableView(tableId, name, {
        query,
        sortKey,
        descending,
      })
      setState((current) => ({ ...current, views: [...current.views, result.data.view] }))
    },
    [descending, query, sortKey, tableId]
  )

  const createRow = useCallback(
    async (values: Record<string, unknown>) => {
      await api.createWorkspaceRows(tableId, [values])
      await reload()
    },
    [reload, tableId]
  )

  const updateSelectedRow = useCallback(
    async (values: Record<string, unknown>) => {
      if (!selectedRowId) return
      await api.updateWorkspaceRow(tableId, selectedRowId, values)
      await reload()
    },
    [reload, selectedRowId, tableId]
  )

  const deleteSelectedRow = useCallback(async () => {
    if (!selectedRowId) return
    await api.deleteWorkspaceRow(tableId, selectedRowId)
    setSelectedRowId(null)
    await reload()
  }, [reload, selectedRowId, tableId])

  return {
    ...state,
    grid,
    reload,
    query,
    setQuery,
    sortKey,
    setSortKey,
    descending,
    setDescending,
    applyView,
    saveView,
    selectedRowId,
    setSelectedRowId,
    createRow,
    updateSelectedRow,
    deleteSelectedRow,
    writable: state.table?.metadata?.readOnly !== true,
  }
}
