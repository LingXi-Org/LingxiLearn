/** @vitest-environment node */
import { describe, expect, it } from 'vitest'
import { createTableGridProjection, projectTableColumns, projectTableRows } from './table-grid'

describe('TableGridController pure projection', () => {
  const table = {
    id: 'table-1',
    name: '学习记录',
    columns: [
      { id: 'c1', key: 'task_id' },
      { id: 'c2', key: 'score' },
      { id: 'sim-only', key: 'workflow_id' },
    ],
  }

  it('projects only Lingxi-owned learning columns in schema order', () => {
    expect(projectTableColumns(table)).toEqual([
      { id: 'c1', key: 'task_id', label: '学习任务' },
      { id: 'c2', key: 'score', label: '得分' },
    ])
  })

  it('projects row values without selection or mutation state', () => {
    const columns = projectTableColumns(table)
    expect(projectTableRows([{ id: 'r1', data: { task_id: 'task-1', score: 92 } }], columns)).toEqual([
      { id: 'r1', cells: { c1: { label: 'task-1' }, c2: { label: '92' } } },
    ])
  })

  it('uses the same controller projection for page and embedded adapters', () => {
    const rows = [{ id: 'r1', values: { task_id: 'task-1', score: 92 } }]
    expect(createTableGridProjection(table, rows)).toEqual(createTableGridProjection(table, rows))
  })
})
