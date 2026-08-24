'use client'

import { userFacingError, workspaceCopy } from '@/lib/product-copy'
import { type ErrorBoundaryProps, ErrorState } from '@/app/workspace/[workspaceId]/components'

export default function FilesError({ error, reset }: ErrorBoundaryProps) {
  return (
    <ErrorState
      error={error}
      reset={reset}
      title={workspaceCopy.resources.files.loadFailedTitle}
      description={userFacingError(error, 'loadFailed')}
      loggerName='FilesError'
    />
  )
}
