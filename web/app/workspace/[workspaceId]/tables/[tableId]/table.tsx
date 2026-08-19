'use client'

import { Table as TableIcon } from '@sim/emcn/icons'
import { Resource } from '@/app/workspace/[workspaceId]/components'
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
        <p className='mx-auto mb-4 max-w-[1100px] text-[12px] text-[var(--text-muted)]'>
          学习记录由 Lingxi AgentTask 运行产生，仅供查看，不能手动新增或修改。
        </p>
        <DetailPresentation
          columns={controller.grid.columns}
          rows={controller.grid.rows}
          loading={controller.loading}
          error={controller.error}
          onRetry={() => void controller.reload()}
        />
      </main>
    </Resource>
  )
}

export function Table(props: TableProps) {
  return <TableDetailShell {...props} />
}
