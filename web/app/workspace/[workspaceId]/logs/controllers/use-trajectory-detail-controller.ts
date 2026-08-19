'use client'

import { useCallback, useMemo, useState } from 'react'
import { toast } from '@sim/emcn'
import { getErrorMessage } from '@sim/utils/errors'
import type { ExecutionLogDetail, ExecutionLogRow } from '@/lib/api/contracts/logs'
import type { ExecutionLogDetailView } from '@/app/workspace/[workspaceId]/logs/model/execution-log'
import { mapExecutionLogDetail } from '@/app/workspace/[workspaceId]/logs/model/execution-log-mapper'
import { useUserPermissionsContext } from '@/app/workspace/[workspaceId]/providers/workspace-permissions-provider'
import { useCancelExecution, useLogDetail, useRetryExecution } from '@/hooks/queries/logs'

const ACTIVE_RUN_DETAIL_REFRESH_MS = 3_000 as const

interface UseTrajectoryDetailControllerParams {
  workspaceId: string
  /** Currently selected row (list controller owns selection state). */
  selectedLogId: string | null
  /** Wire list row rendered while the detail query is in flight. */
  fallbackWireLog: ExecutionLogRow | null
  isLive: boolean
}

/**
 * Detail controller for the Logs observability surface: it owns the selected
 * run's detail query (with live refresh for active runs), maps the wire detail
 * into the native view model (timeline/run-hierarchy/event data flows to the
 * canonical trajectory projector unchanged), and exposes the run commands
 * (cancel/retry) plus the snapshot preview state.
 *
 * Cancel/retry still target the workflow-scoped command endpoints on the wire;
 * the workflow id is read from the wire row here, at the controller boundary —
 * it never enters the view model.
 */
export function useTrajectoryDetailController({
  workspaceId,
  selectedLogId,
  fallbackWireLog,
  isLive,
}: UseTrajectoryDetailControllerParams) {
  const userPermissions = useUserPermissionsContext()

  const refetchInterval = useCallback(
    (query: { state: { data?: ExecutionLogDetail } }) => {
      if (!isLive) return false
      const status = query.state.data?.status
      return status === 'running' || status === 'pending' || status === 'redacting'
        ? ACTIVE_RUN_DETAIL_REFRESH_MS
        : false
    },
    [isLive]
  )

  const selectedDetailQuery = useLogDetail(selectedLogId ?? undefined, workspaceId, {
    refetchInterval,
  })

  const [previewLogId, setPreviewLogId] = useState<string | null>(null)
  const previewDetailQuery = useLogDetail(previewLogId ?? undefined, workspaceId, {
    refetchInterval,
  })

  const wireDetail = selectedDetailQuery.data ?? fallbackWireLog ?? null
  const detail: ExecutionLogDetailView | null = useMemo(
    () => (wireDetail ? mapExecutionLogDetail(wireDetail) : null),
    [wireDetail]
  )

  const cancelExecution = useCancelExecution(workspaceId)
  const retryExecution = useRetryExecution()
  const cancelMutate = cancelExecution.mutateAsync
  const retryMutate = retryExecution.mutateAsync

  const cancelRun = useCallback(
    async (log: ExecutionLogRow | null) => {
      // Wire-compat: the cancel endpoint is still workflow-scoped on the wire.
      const workflowId = log?.workflow?.id || log?.workflowId
      const executionId = log?.executionId
      if (!userPermissions.canEdit || !workflowId || !executionId) return

      try {
        await cancelMutate({ workflowId, executionId })
        toast.success('Run stopped')
      } catch (error) {
        toast.error(getErrorMessage(error, 'Failed to stop run'))
      }
    },
    [userPermissions.canEdit, cancelMutate]
  )

  const retryRun = useCallback(
    async (log: ExecutionLogRow | null) => {
      // Wire-compat: the retry endpoint is still workflow-scoped on the wire.
      const workflowId = log?.workflow?.id || log?.workflowId
      const executionId = log?.executionId
      if (!workflowId || !executionId) return

      try {
        await retryMutate({ workflowId, executionId })
        toast.success('Retry started')
      } catch {
        toast.error('Failed to retry execution')
      }
    },
    [retryMutate]
  )

  return {
    /** Native detail view model for the selected run (null when unselected). */
    detail,
    /** Wire detail/row backing the view model (snapshot preview + commands). */
    wireDetail,
    detailQuery: selectedDetailQuery,
    preview: {
      logId: previewLogId,
      detail: previewDetailQuery.data ?? null,
      open: setPreviewLogId,
      close: () => setPreviewLogId(null),
    },
    commands: {
      cancelRun,
      retryRun,
      canEdit: userPermissions.canEdit,
      isCancelPending: cancelExecution.isPending,
      cancelPendingExecutionId: cancelExecution.variables?.executionId,
      isRetryPending: retryExecution.isPending,
    },
  }
}

export type TrajectoryDetailController = ReturnType<typeof useTrajectoryDetailController>
