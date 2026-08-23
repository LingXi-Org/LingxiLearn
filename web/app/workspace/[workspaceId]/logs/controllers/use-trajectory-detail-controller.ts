'use client'

import { useCallback, useMemo, useState } from 'react'
import { toast } from '@/components/ui-kit'
import { getErrorMessage } from '@/lib/utils/errors'
import type { ExecutionLogDetail, ExecutionLogRow } from '@/lib/api/contracts/logs'
import type { ExecutionLogDetailView } from '@/app/workspace/[workspaceId]/logs/model/execution-log'
import { mapExecutionLogDetail } from '@/app/workspace/[workspaceId]/logs/model/execution-log-mapper'
import { useUserPermissionsContext } from '@/app/workspace/[workspaceId]/providers/workspace-permissions-provider'
import { useCancelExecution, useLogDetail, useRetryExecution } from '@/hooks/queries/logs'
import { api } from '@/lib/lingxi/api'

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
 * Native AgentTask runs use AgentTask cancel/fork commands. Only explicitly
 * classified legacy workflow rows use the compatibility workflow endpoints.
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
  const [nativeCancelPending, setNativeCancelPending] = useState(false)
  const [nativeRetryPending, setNativeRetryPending] = useState(false)
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
      const mapped = log ? mapExecutionLogDetail(log) : null
      const workflowId = log?.workflow?.id || log?.workflowId
      const executionId = log?.executionId
      if (!userPermissions.canEdit || !executionId) return

      try {
        if (mapped?.source.kind === 'agent-task' && mapped.taskId) {
          setNativeCancelPending(true)
          await api.cancelAgentTask(mapped.taskId)
        } else if (mapped?.source.kind === 'workflow' && workflowId) {
          await cancelMutate({ workflowId, executionId })
        } else {
          return
        }
        toast.success('Run stopped')
      } catch (error) {
        toast.error(getErrorMessage(error, 'Failed to stop run'))
      } finally {
        setNativeCancelPending(false)
      }
    },
    [userPermissions.canEdit, cancelMutate]
  )

  const retryRun = useCallback(
    async (log: ExecutionLogRow | null) => {
      const mapped = log ? mapExecutionLogDetail(log) : null
      const workflowId = log?.workflow?.id || log?.workflowId
      const executionId = log?.executionId
      if (!executionId) return

      try {
        if (mapped?.source.kind === 'agent-task' && mapped.taskId) {
          setNativeRetryPending(true)
          await api.forkAgentTask(mapped.taskId)
        } else if (mapped?.source.kind === 'workflow' && workflowId) {
          await retryMutate({ workflowId, executionId })
        } else {
          return
        }
        toast.success('Retry started')
      } catch {
        toast.error('Failed to retry execution')
      } finally {
        setNativeRetryPending(false)
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
      isCancelPending: cancelExecution.isPending || nativeCancelPending,
      cancelPendingExecutionId: cancelExecution.variables?.executionId,
      isRetryPending: retryExecution.isPending || nativeRetryPending,
    },
  }
}

export type TrajectoryDetailController = ReturnType<typeof useTrajectoryDetailController>
