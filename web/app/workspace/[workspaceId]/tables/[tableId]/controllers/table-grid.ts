import type { WorkspaceTableItem } from '@/lib/lingxi/api'

export interface TableDetailColumn {
  id: string
  key: string
  label: string
}

export interface TableDetailGridRow {
  id: string
  cells: Record<string, { label: string }>
}

const COLUMN_LABELS: Readonly<Record<string, string>> = {
  task_id: '学习任务',
  event_kind: '学习事件',
  agent: '执行智能体',
  sequence: '序号',
  recorded_at: '记录时间',
  knowledge_point: '知识点',
  learning_state: '学习状态',
  mastery: '掌握度',
  progress: '学习进度',
  score: '得分',
  question: '题目',
  answer: '作答',
  result: '结果',
  summary: '学习摘要',
}

const LEGACY_SIM_COLUMNS = new Set(['workflow_id', 'workflow_group_id', 'enrichment_id'])

function cellText(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return ''
  }
}

/** Pure schema projection for the Lingxi-owned, read-only learning table. */
export function projectTableColumns(table: WorkspaceTableItem | null): TableDetailColumn[] {
  const columns = table?.columns ?? table?.schema?.columns ?? []
  return columns.flatMap((column) => {
    const key = typeof column.key === 'string' ? column.key : ''
    if (!key || LEGACY_SIM_COLUMNS.has(key)) return []
    const name = typeof column.name === 'string' ? column.name.trim() : ''
    const label = (COLUMN_LABELS[key] ?? name) || key
    return [{ id: String(column.id ?? key), key, label }]
  })
}

/** Pure row projection; selection and mutations intentionally do not exist. */
export function projectTableRows(
  rows: ReadonlyArray<Record<string, unknown>>,
  columns: ReadonlyArray<TableDetailColumn>
): TableDetailGridRow[] {
  return rows.map((row, index) => {
    const values =
      row.data && typeof row.data === 'object'
        ? (row.data as Record<string, unknown>)
        : row.values && typeof row.values === 'object'
          ? (row.values as Record<string, unknown>)
          : row
    return {
      id: String(row.id ?? `row-${index}`),
      cells: Object.fromEntries(
        columns.map((column) => [column.id, { label: cellText(values[column.key]) }])
      ),
    }
  })
}

export function createTableGridProjection(
  table: WorkspaceTableItem | null,
  rows: ReadonlyArray<Record<string, unknown>>
) {
  const columns = projectTableColumns(table)
  return { columns, rows: projectTableRows(rows, columns) }
}

export function filterAndSortTableRows(
  rows: ReadonlyArray<Record<string, unknown>>,
  query: string,
  sortKey: string,
  descending: boolean
): Array<Record<string, unknown>> {
  const needle = query.trim().toLocaleLowerCase()
  const filtered = needle
    ? rows.filter((row) => JSON.stringify(row).toLocaleLowerCase().includes(needle))
    : [...rows]
  if (!sortKey) return filtered
  return filtered.sort((left, right) => {
    const leftValues = (left.data ?? left.values ?? left) as Record<string, unknown>
    const rightValues = (right.data ?? right.values ?? right) as Record<string, unknown>
    const comparison = String(leftValues[sortKey] ?? '').localeCompare(
      String(rightValues[sortKey] ?? ''),
      'zh-CN',
      { numeric: true }
    )
    return descending ? -comparison : comparison
  })
}
