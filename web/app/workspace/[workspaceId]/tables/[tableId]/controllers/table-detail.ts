import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, type WorkspaceTableItem } from '@/lib/lingxi/api'
import { createTableGridProjection } from './table-grid'

interface TableDetailState {
  table: WorkspaceTableItem | null
  rows: Array<Record<string, unknown>>
  loading: boolean
  error: string | null
}

const INITIAL_STATE: TableDetailState = { table: null, rows: [], loading: true, error: null }

/**
 * Shared Lingxi-native domain controller used by both page and embedded shells.
 * WorkspaceTable is read-only, so unsupported mutation/import/execution state is absent.
 */
export function useTableDetailController(tableId: string) {
  const [state, setState] = useState<TableDetailState>(INITIAL_STATE)
  const requestIdRef = useRef(0)

  const reload = useCallback(async () => {
    const requestId = ++requestIdRef.current
    setState((current) => ({ ...current, loading: true, error: null }))
    try {
      const [tableResult, rowResult] = await Promise.all([
        api.workspaceTable(tableId),
        api.workspaceTableRows(tableId),
      ])
      if (requestId !== requestIdRef.current) return
      setState({
        table: tableResult.data.table,
        rows: rowResult.data.rows ?? [],
        loading: false,
        error: null,
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
    () => createTableGridProjection(state.table, state.rows),
    [state.table, state.rows]
  )

  return { ...state, grid, reload }
}
