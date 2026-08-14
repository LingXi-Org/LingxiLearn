'use client'

import { useMemo, useState } from 'react'
import type { SortSpec, TablePredicate } from '@/lib/table'
import { getColumnId } from '@/lib/table/column-keys'
import { useTable } from './hooks'

interface LingxiReadOnlyTableProps {
  workspaceId: string
  tableId: string
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

export function LingxiReadOnlyTable({ workspaceId, tableId }: LingxiReadOnlyTableProps) {
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<SortSpec | null>(null)
  const queryOptions = useMemo(() => ({ filter: null as TablePredicate | null, sort }), [sort])
  const table = useTable({ workspaceId, tableId, queryOptions })
  const { tableData, columns, rows, isLoadingTable, isLoadingRows, hasNextPage, fetchNextPage } = table

  const visibleRows = useMemo(() => {
    const needle = search.trim().toLowerCase()
    if (!needle) return rows
    return rows.filter((row) =>
      columns.some((column) => displayValue(row.data[getColumnId(column)]).toLowerCase().includes(needle))
    )
  }, [columns, rows, search])

  const toggleSort = (column: (typeof columns)[number]) => {
    const field = getColumnId(column)
    const current = sort?.[0]
    setSort(
      current?.field === field && current.direction === 'asc'
        ? [{ field, direction: 'desc' }]
        : [{ field, direction: 'asc' }]
    )
  }

  if (isLoadingTable) return <div className='p-6 text-sm text-[var(--text-muted)]'>正在加载表格…</div>
  if (!tableData) return <div className='p-6 text-sm text-[var(--text-muted)]'>表格不存在或尚未生成。</div>

  return (
    <div className='flex h-full min-h-0 flex-col overflow-hidden bg-[var(--surface-1)]'>
      <div className='flex items-center gap-3 border-b border-[var(--border)] px-4 py-3'>
        <div className='min-w-0 flex-1'>
          <h1 className='truncate text-sm font-medium text-[var(--text-primary)]'>{tableData.name}</h1>
          <p className='text-xs text-[var(--text-muted)]'>只读运行数据 · {tableData.rowCount} 行</p>
        </div>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder='筛选当前数据…'
          aria-label='筛选表格数据'
          className='h-8 w-56 rounded border border-[var(--border)] bg-[var(--surface-2)] px-2 text-xs text-[var(--text-primary)] outline-none'
        />
      </div>
      <div className='min-h-0 flex-1 overflow-auto'>
        <table className='w-full border-collapse text-xs'>
          <thead className='sticky top-0 z-10 bg-[var(--surface-2)]'>
            <tr>
              {columns.map((column) => (
                <th
                  key={getColumnId(column)}
                  className='cursor-pointer whitespace-nowrap border-b border-r border-[var(--border)] px-3 py-2 text-left font-medium text-[var(--text-secondary)]'
                  onClick={() => toggleSort(column)}
                >
                  {column.name}
                  {sort?.[0]?.field === getColumnId(column)
                    ? sort[0].direction === 'asc'
                      ? ' ↑'
                      : ' ↓'
                    : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr key={row.id} className='hover:bg-[var(--surface-2)]'>
                {columns.map((column) => (
                  <td
                    key={getColumnId(column)}
                    className='max-w-[320px] border-b border-r border-[var(--border)] px-3 py-2 align-top text-[var(--text-primary)]'
                  >
                    <span className='line-clamp-3 whitespace-pre-wrap'>
                      {displayValue(row.data[getColumnId(column)])}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {isLoadingRows && <div className='p-4 text-center text-xs text-[var(--text-muted)]'>正在加载数据…</div>}
        {!isLoadingRows && visibleRows.length === 0 && <div className='p-8 text-center text-xs text-[var(--text-muted)]'>暂无匹配数据。</div>}
        {hasNextPage && (
          <button
            type='button'
            onClick={() => void fetchNextPage()}
            className='m-4 rounded border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-secondary)]'
          >
            加载更多
          </button>
        )}
      </div>
    </div>
  )
}

