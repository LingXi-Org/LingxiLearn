'use client'

import { Table as TableIcon } from '@sim/emcn/icons'
import { Resource } from '@/app/workspace/[workspaceId]/components'
import { apiUrl } from '@/lib/lingxi/api'
import { useTableDetailController } from './controllers/table-detail'
import { DetailPresentation } from './detail-presentation'

export interface TableProps {
  embedded?: boolean
  workspaceId?: string
  tableId: string
  tableLocksEnabled?: boolean
  viewsEnabled?: boolean
}

/** Shared page/embedded adapter over one Lingxi-native Table Detail controller. */
export function TableDetailShell({ embedded = false, tableId }: TableProps) {
  const controller = useTableDetailController(tableId)

  return (
    <Resource>
      {!embedded && (
        <Resource.Header icon={TableIcon} title={controller.table?.name || '学习记录'} />
      )}
      <main className='min-h-0 flex-1 overflow-y-auto p-4'>
        <div className='mx-auto mb-4 flex max-w-[1100px] flex-wrap items-center gap-2'>
          <input
            aria-label='筛选表格'
            className='h-8 min-w-52 rounded-md border border-[var(--border-1)] bg-transparent px-3 text-sm'
            placeholder='筛选当前表格…'
            value={controller.query}
            onChange={(event) => controller.setQuery(event.target.value)}
          />
          <select
            aria-label='排序字段'
            className='h-8 rounded-md border border-[var(--border-1)] bg-[var(--surface-3)] px-2 text-sm'
            value={controller.sortKey}
            onChange={(event) => controller.setSortKey(event.target.value)}
          >
            <option value=''>默认顺序</option>
            {controller.grid.columns.map((column) => (
              <option key={column.id} value={column.key}>
                {column.label}
              </option>
            ))}
          </select>
          <button
            type='button'
            className='h-8 rounded-md border border-[var(--border-1)] px-3 text-sm'
            onClick={() => controller.setDescending(!controller.descending)}
          >
            {controller.descending ? '降序' : '升序'}
          </button>
          <select
            aria-label='已保存视图'
            className='h-8 rounded-md border border-[var(--border-1)] bg-[var(--surface-3)] px-2 text-sm'
            defaultValue=''
            onChange={(event) => controller.applyView(event.target.value)}
          >
            <option value=''>已保存视图</option>
            {controller.views.map((view) => (
              <option key={view.id} value={view.id}>
                {view.name}
              </option>
            ))}
          </select>
          <button
            type='button'
            className='h-8 rounded-md border border-[var(--border-1)] px-3 text-sm'
            onClick={() => {
              const name = window.prompt('视图名称')?.trim()
              if (name) void controller.saveView(name)
            }}
          >
            保存视图
          </button>
          {controller.writable && (
            <>
              <button
                type='button'
                className='h-8 rounded-md border border-[var(--border-1)] px-3 text-sm'
                onClick={() => {
                  const raw = window.prompt('输入新行 JSON', '{}')
                  if (!raw) return
                  try {
                    void controller.createRow(JSON.parse(raw) as Record<string, unknown>)
                  } catch {
                    window.alert('JSON 格式无效')
                  }
                }}
              >
                新增行
              </button>
              <button
                type='button'
                disabled={!controller.selectedRowId}
                className='h-8 rounded-md border border-[var(--border-1)] px-3 text-sm disabled:opacity-40'
                onClick={() => {
                  const raw = window.prompt('输入要更新的字段 JSON', '{}')
                  if (!raw) return
                  try {
                    void controller.updateSelectedRow(JSON.parse(raw) as Record<string, unknown>)
                  } catch {
                    window.alert('JSON 格式无效')
                  }
                }}
              >
                编辑选中行
              </button>
              <button
                type='button'
                disabled={!controller.selectedRowId}
                className='h-8 rounded-md border border-[var(--border-1)] px-3 text-sm disabled:opacity-40'
                onClick={() => {
                  if (window.confirm('确定删除选中行？')) void controller.deleteSelectedRow()
                }}
              >
                删除选中行
              </button>
            </>
          )}
          <a
            className='inline-flex h-8 items-center rounded-md border border-[var(--border-1)] px-3 text-sm'
            href={apiUrl(`/table/${encodeURIComponent(tableId)}/export`)}
            download
          >
            导出 CSV
          </a>
        </div>
        <DetailPresentation
          columns={controller.grid.columns}
          rows={controller.grid.rows}
          loading={controller.loading}
          error={controller.error}
          onRetry={() => void controller.reload()}
          selectedRowId={controller.selectedRowId}
          onRowClick={controller.setSelectedRowId}
        />
      </main>
    </Resource>
  )
}

export function Table(props: TableProps) {
  return <TableDetailShell {...props} />
}
