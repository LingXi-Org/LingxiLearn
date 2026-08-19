import { createLogger } from '@/lib/logger'
import { generateId } from '@/lib/utils/id'
import { getSessionSnapshot } from '@/lib/auth/session-snapshot'
import { useOperationQueueStore } from '@/stores/operation-queue/store'
import type { WorkflowState } from '@/stores/workflows/workflow/types'
import { normalizeWorkflowState } from '@/stores/workflows/workflow/validation'

const logger = createLogger('WorkflowSocketOperations')

/**
 * Reads the acting user off the canonical session snapshot. This is a pure
 * read of state the SessionProvider already owns — an operation enqueue must
 * never trigger its own `/api/v1/me` request.
 */
function resolveUserId(): string {
  return getSessionSnapshot()?.user.id ?? 'unknown'
}

interface EnqueueWorkflowOperationArgs {
  operation: string
  target: string
  payload: any
  workflowId: string
  operationId?: string
}

/**
 * Queues a workflow socket operation so it flows through the standard operation queue,
 * ensuring consistent retries, confirmations, and telemetry.
 */
async function enqueueWorkflowOperation({
  operation,
  target,
  payload,
  workflowId,
  operationId,
}: EnqueueWorkflowOperationArgs): Promise<string> {
  const userId = resolveUserId()
  const opId = operationId ?? generateId()

  useOperationQueueStore.getState().addToQueue({
    id: opId,
    operation: {
      operation,
      target,
      payload,
    },
    workflowId,
    userId,
  })

  logger.debug('Queued workflow operation', {
    workflowId,
    operation,
    target,
    operationId: opId,
  })

  return opId
}

interface EnqueueReplaceStateArgs {
  workflowId: string
  state: WorkflowState
  operationId?: string
}

/**
 * Convenience wrapper for broadcasting a full workflow state replacement via the queue.
 */
export async function enqueueReplaceWorkflowState({
  workflowId,
  state,
  operationId,
}: EnqueueReplaceStateArgs): Promise<string> {
  const { state: validatedState, warnings } = normalizeWorkflowState(state)

  if (warnings.length > 0) {
    logger.warn('Normalized state before enqueuing replace-state', {
      workflowId,
      warningCount: warnings.length,
      warnings,
    })
  }

  return enqueueWorkflowOperation({
    workflowId,
    operation: 'replace-state',
    target: 'workflow',
    payload: { state: validatedState },
    operationId,
  })
}
