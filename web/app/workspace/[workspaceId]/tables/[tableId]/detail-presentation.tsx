import { Chip } from '@/components/ui-kit'
import { Resource } from '@/app/workspace/[workspaceId]/components'
import type { TableDetailGridRow } from './controllers/table-grid'

interface DetailPresentationProps {
  columns: Array<{ id: string; label: string }>
  rows: TableDetailGridRow[]
  loading: boolean
  error: string | null
  onRetry: () => void
  selectedRowId?: string | null
  onRowClick?: (rowId: string) => void
}

/** Presentation-only surface: no fetching, grid lifecycle, or modal FSM. */
export function DetailPresentation({
  columns,
  rows,
  loading,
  error,
  onRetry,
  selectedRowId,
  onRowClick,
}: DetailPresentationProps) {
  if (loading) {
    return <p className='p-8 text-center text-[13px] text-[var(--text-muted)]'>正在加载学习记录…</p>
  }
  if (error) {
    return (
      <div className='flex flex-col items-center gap-3 p-8 text-[13px] text-[var(--text-muted)]'>
        <p>{error}</p>
        <Chip onClick={onRetry}>重试</Chip>
      </div>
    )
  }
  if (columns.length === 0) {
    return (
      <p className='p-8 text-center text-[13px] text-[var(--text-muted)]'>暂无学习记录字段。</p>
    )
  }
  return (
    <Resource.Table
      columns={columns.map((column) => ({ id: column.id, header: column.label }))}
      rows={rows}
      selectedRowId={selectedRowId}
      onRowClick={onRowClick}
    />
  )
}
