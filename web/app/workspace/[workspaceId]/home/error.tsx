'use client'

import { workspaceCopy } from '@/lib/product-copy'
import { type ErrorBoundaryProps, ErrorState } from '@/app/workspace/[workspaceId]/components'

export default function HomeError({ error, reset }: ErrorBoundaryProps) {
  return (
    <ErrorState
      error={error}
      reset={reset}
      title='工作区首页加载失败'
      description={workspaceCopy.common.errors.loadFailed}
      loggerName='HomeError'
    />
  )
}
