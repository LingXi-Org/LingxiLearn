/** @vitest-environment node */
import { describe, expect, it } from 'vitest'
import {
  createTableGridProjection,
  filterAndSortTableRows,
  projectTableColumns,
  projectTableRows,
} from './table-grid'

describe('TableGridController pure projection', () => {
  const table = {
    id: 'table-1',
    name: '学习记录',
    columns: [
      { id: 'c1', key: 'task_id' },
      { id: 'c2', key: 'score' },
      { id: 'custom', key: 'student_note', name: '学习笔记' },
      { id: 'sim-only', key: 'workflow_id' },
    ],
  }

  it('projects only Lingxi-owned learning columns in schema order', () => {
    expect(projectTableColumns(table)).toEqual([
      { id: 'c1', key: 'task_id', label: '学习任务' },
      { id: 'c2', key: 'score', label: '得分' },
      { id: 'custom', key: 'student_note', label: '学习笔记' },
    ])
  })

  it('projects row values without selection or mutation state', () => {
    const columns = projectTableColumns(table)
    expect(projectTableRows([{ id: 'r1', data: { task_id: 'task-1', score: 92 } }], columns)).toEqual([
      {
        id: 'r1',
        cells: {
          c1: { label: 'task-1' },
          c2: { label: '92' },
          custom: { label: '' },
        },
      },
    ])
  })

  it('uses the same controller projection for page and embedded adapters', () => {
    const rows = [{ id: 'r1', values: { task_id: 'task-1', score: 92 } }]
    expect(createTableGridProjection(table, rows)).toEqual(createTableGridProjection(table, rows))
  })

  it('filters and sorts native row values deterministically', () => {
    const rows = [
      { id: 'r2', values: { student_note: 'Beta', score: 2 } },
      { id: 'r1', values: { student_note: 'alpha', score: 10 } },
    ]
    expect(filterAndSortTableRows(rows, 'ALP', 'score', true).map((row) => row.id)).toEqual([
      'r1',
    ])
    expect(filterAndSortTableRows(rows, '', 'score', false).map((row) => row.id)).toEqual([
      'r2',
      'r1',
    ])
  })
})
