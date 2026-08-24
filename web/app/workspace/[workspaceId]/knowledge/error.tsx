'use client'

import { userFacingError, workspaceCopy } from '@/lib/product-copy'
import { type ErrorBoundaryProps, ErrorState } from '@/app/workspace/[workspaceId]/components'

export default function KnowledgeError({ error, reset }: ErrorBoundaryProps) {
  return (
    <ErrorState
      error={error}
      reset={reset}
      title={workspaceCopy.resources.knowledge.loadFailedTitle}
      description={userFacingError(error, 'loadFailed')}
      loggerName='KnowledgeError'
    />
  )
}
