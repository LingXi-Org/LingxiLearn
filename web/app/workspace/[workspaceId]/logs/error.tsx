'use client'

import { type ErrorBoundaryProps, ErrorState } from '@/app/workspace/[workspaceId]/components'

export default function LogsError({ error, reset }: ErrorBoundaryProps) {
  return (
    <ErrorState
      error={error}
      reset={reset}
      title='日志加载失败'
      description='加载日志时出现问题，请稍后重试。'
      loggerName='LogsError'
    />
  )
}
