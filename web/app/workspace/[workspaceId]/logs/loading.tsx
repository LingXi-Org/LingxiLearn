'use client'

import { Library, RefreshCw } from '@/components/ui-kit'
import { Download } from '@/components/ui-kit/icons'
import {
  type ChromeActionSpec,
  ResourceChromeFallback,
} from '@/app/workspace/[workspaceId]/components'

const COLUMNS = [
  { id: 'workflow', header: '工作流' },
  { id: 'date', header: '时间' },
  { id: 'status', header: '状态' },
  { id: 'cost', header: '成本' },
  { id: 'trigger', header: '触发方式' },
  { id: 'duration', header: '耗时' },
]

const ACTIONS: ChromeActionSpec[] = [
  { text: '导出', icon: Download },
  { text: '刷新', icon: RefreshCw },
  { text: '日志', active: true },
  { text: '概览' },
  { text: '轨迹' },
]

export default function LogsLoading() {
  return (
    <ResourceChromeFallback
      icon={Library}
      title='日志'
      columns={COLUMNS}
      actions={ACTIONS}
      searchPlaceholder='Search logs...'
      hasSort
      hasFilter
    />
  )
}
