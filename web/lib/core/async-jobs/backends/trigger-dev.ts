import { taskContext } from '@trigger.dev/core/v3'
import { ApiError, runs, type TriggerOptions, tasks } from '@trigger.dev/sdk'
import { resolveTriggerRegion } from '@/lib/core/async-jobs/region'
import {
  AsyncJobEnqueueError,
  type EnqueueOptions,
  JOB_STATUS,
  type Job,
  type JobMetadata,
  type JobQueueBackend,
  type JobStatus,
  type JobType,
  validateMaxDurationSeconds,
} from '@/lib/core/async-jobs/types'
import { createLogger } from '@/lib/logger'
import { sha256Hex } from '@/lib/security/hash'
import { toError } from '@/lib/utils/errors'

const logger = createLogger('TriggerDevJobQueue')
function classifyTriggerEnqueueError(error: unknown): AsyncJobEnqueueError {
  if (error instanceof ApiError && error.status && error.status >= 400 && error.status < 500) {
    return new AsyncJobEnqueueError(toError(error).message, {
      acceptance: 'rejected',
      retryable: error.status === 408 || error.status === 409 || error.status === 429,
      cause: error,
    })
  }

  return new AsyncJobEnqueueError(toError(error).message, {
    acceptance: 'unknown',
    retryable: true,
    cause: error,
  })
}

function buildExecutionTag(executionId: string): string {
  const tag = `executionId:${executionId}`
  return tag.length <= 128 ? tag : `executionIdHash:${sha256Hex(executionId)}`
}

function buildWorkflowTag(workflowId: string): string {
  const tag = `workflowId:${workflowId}`
  return tag.length <= 128 ? tag : `workflowIdHash:${sha256Hex(workflowId)}`
}

/**
 * Maps trigger.dev task IDs to our JobType
 */
const JOB_TYPE_TO_TASK_ID: Record<JobType, string> = {
  'webhook-execution': 'webhook-execution',
  'workflow-group-cell': 'workflow-group-cell',
}

/**
 * Maps trigger.dev run status to our JobStatus
 */
function mapTriggerDevStatus(status: string): JobStatus {
  switch (status) {
    case 'PENDING_VERSION':
    case 'DELAYED':
    case 'QUEUED':
      return JOB_STATUS.PENDING
    case 'DEQUEUED':
    case 'EXECUTING':
    case 'WAITING':
      return JOB_STATUS.PROCESSING
    case 'COMPLETED':
      return JOB_STATUS.COMPLETED
    case 'CANCELED':
      return JOB_STATUS.CANCELLED
    case 'FAILED':
    case 'CRASHED':
    case 'INTERRUPTED':
    case 'SYSTEM_FAILURE':
    case 'EXPIRED':
    case 'TIMED_OUT':
      return JOB_STATUS.FAILED
    default:
      return JOB_STATUS.PENDING
  }
}

/**
 * Adapter that wraps the trigger.dev SDK to conform to JobQueueBackend interface.
 */
export class TriggerDevJobQueue implements JobQueueBackend {
  async enqueue<TPayload>(
    type: JobType,
    payload: TPayload,
    options?: EnqueueOptions
  ): Promise<string> {
    const taskId = JOB_TYPE_TO_TASK_ID[type]
    if (!taskId) {
      throw new Error(`Unknown job type: ${type}`)
    }

    const enrichedPayload =
      options?.metadata && typeof payload === 'object' && payload !== null
        ? { ...payload, ...options.metadata }
        : payload

    const tags = buildTags(options)
    const triggerOptions: TriggerOptions = {}
    if (tags.length > 0) triggerOptions.tags = tags
    const maxDuration = validateMaxDurationSeconds(options?.maxDurationSeconds)
    if (maxDuration !== undefined) triggerOptions.maxDuration = maxDuration
    if (options?.concurrencyKey) triggerOptions.concurrencyKey = options.concurrencyKey
    if (options?.jobId) {
      triggerOptions.idempotencyKey = options.jobId
      triggerOptions.idempotencyKeyTTL = '14d'
    }
    if (options?.delayMs && options.delayMs > 0) {
      triggerOptions.delay = new Date(Date.now() + options.delayMs)
    }
    try {
      triggerOptions.region = await resolveTriggerRegion()
    } catch (error) {
      throw new AsyncJobEnqueueError(toError(error).message, {
        acceptance: 'rejected',
        retryable: true,
        cause: error,
      })
    }

    let handle: Awaited<ReturnType<typeof tasks.trigger>>
    try {
      handle = await tasks.trigger(taskId, enrichedPayload, triggerOptions)
    } catch (error) {
      throw classifyTriggerEnqueueError(error)
    }

    logger.debug('Enqueued job via trigger.dev', { jobId: handle.id, type, taskId, tags })
    return handle.id
  }

  async batchEnqueue<TPayload>(
    type: JobType,
    items: Array<{ payload: TPayload; options?: EnqueueOptions }>
  ): Promise<string[]> {
    if (items.length === 0) return []
    for (const { options } of items) {
      validateMaxDurationSeconds(options?.maxDurationSeconds)
    }
    // tasks.batchTrigger returns only a batchId, not per-item run IDs, so we
    // can't use it when callers need to track individual runs (e.g. table cell
    // tasks need per-row jobIds for cancellation). Sequential `tasks.trigger`
    // gives us per-item IDs and naturally preserves input order in the queue.
    const ids: string[] = []
    for (const { payload, options } of items) {
      const id = await this.enqueue(type, payload, options)
      ids.push(id)
    }
    return ids
  }

  async batchEnqueueAndWait<TPayload>(
    type: JobType,
    items: Array<{ payload: TPayload; options?: EnqueueOptions }>
  ): Promise<string[]> {
    if (items.length === 0) return []
    for (const { options } of items) {
      validateMaxDurationSeconds(options?.maxDurationSeconds)
    }
    // The SDK's checkpoint-and-resume requires task runtime context. The only
    // caller (`dispatcherStep` invoked by `tableRunDispatcherTask.run`) is
    // always inside a task; check defensively so misuse fails at the boundary
    // instead of as a confusing SDK internal error.
    if (!taskContext.isInsideTask) {
      throw new Error(
        'batchEnqueueAndWait requires trigger.dev task runtime context — call from within a registered task'
      )
    }

    const taskId = JOB_TYPE_TO_TASK_ID[type]
    if (!taskId) throw new Error(`Unknown job type: ${type}`)

    const region = await resolveTriggerRegion()
    const batchItems = items.map(({ payload, options }) => {
      const enrichedPayload =
        options?.metadata && typeof payload === 'object' && payload !== null
          ? { ...payload, ...options.metadata }
          : payload
      const tags = buildTags(options)
      const batchItem: {
        payload: unknown
        options?: {
          concurrencyKey?: string
          maxDuration?: number
          tags?: string[]
          region?: string
        }
      } = { payload: enrichedPayload }
      const batchOpts: {
        concurrencyKey?: string
        maxDuration?: number
        tags?: string[]
        region?: string
      } = { region }
      if (options?.concurrencyKey) batchOpts.concurrencyKey = options.concurrencyKey
      const maxDuration = validateMaxDurationSeconds(options?.maxDurationSeconds)
      if (maxDuration !== undefined) batchOpts.maxDuration = maxDuration
      if (tags.length > 0) batchOpts.tags = tags
      batchItem.options = batchOpts
      return batchItem
    })

    const result = await tasks.batchTriggerAndWait(taskId, batchItems)
    logger.debug('batchTriggerAndWait completed', {
      type,
      taskId,
      runCount: result.runs.length,
    })
    return result.runs.map((r) => r.id)
  }

  async getJob(jobId: string): Promise<Job | null> {
    try {
      let run: Awaited<ReturnType<typeof runs.retrieve>>
      try {
        run = await runs.retrieve(jobId)
      } catch (error) {
        const isNotFound =
          (error instanceof Error && error.message.toLowerCase().includes('not found')) ||
          (error && typeof error === 'object' && 'status' in error && error.status === 404)
        if (!isNotFound) throw error

        let runId: string | undefined
        for await (const candidate of runs.list({ tag: `jobId:${jobId}`, limit: 1 })) {
          runId = candidate.id
          break
        }
        if (!runId) {
          logger.debug('Job not found in trigger.dev', { jobId })
          return null
        }
        run = await runs.retrieve(runId)
      }

      const payload = run.payload as Record<string, unknown>
      const metadata: JobMetadata = {
        workflowId: payload?.workflowId as string | undefined,
        userId: payload?.userId as string | undefined,
        correlation:
          payload?.correlation && typeof payload.correlation === 'object'
            ? (payload.correlation as JobMetadata['correlation'])
            : undefined,
      }

      return {
        id: run.id,
        type: run.taskIdentifier as JobType,
        payload: run.payload,
        status: mapTriggerDevStatus(run.status),
        createdAt: run.createdAt ? new Date(run.createdAt) : new Date(),
        startedAt: run.startedAt ? new Date(run.startedAt) : undefined,
        completedAt: run.finishedAt ? new Date(run.finishedAt) : undefined,
        attempts: run.attemptCount ?? 1,
        maxAttempts: 3,
        error: run.error?.message,
        output: run.output as unknown,
        metadata,
      }
    } catch (error) {
      const isNotFound =
        (error instanceof Error && error.message.toLowerCase().includes('not found')) ||
        (error && typeof error === 'object' && 'status' in error && error.status === 404)

      if (isNotFound) {
        logger.debug('Job not found in trigger.dev', { jobId })
        return null
      }

      logger.error('Failed to get job from trigger.dev', { jobId, error })
      throw error
    }
  }

  async startJob(_jobId: string): Promise<boolean> {
    return true
  }

  async completeJob(_jobId: string, _output: unknown): Promise<void> {}

  async markJobFailed(_jobId: string, _error: string): Promise<void> {}

  async cancelJob(jobId: string): Promise<void> {
    try {
      await runs.cancel(jobId)
      logger.debug('Cancelled trigger.dev run', { jobId })
    } catch (error) {
      const isNotFound =
        (error instanceof Error && error.message.toLowerCase().includes('not found')) ||
        (error && typeof error === 'object' && 'status' in error && error.status === 404)
      if (isNotFound) {
        logger.debug('Cancel target not found in trigger.dev (already finished?)', { jobId })
        return
      }
      logger.error('Failed to cancel trigger.dev run', { jobId, error })
      throw error
    }
  }

  cancelByKey(_cancelKey: string): boolean {
    // No in-process AbortControllers to abort — trigger.dev runs are cancelled
    // by jobId or via tag sweep (see `cancelCellRunsByTags`). Callers that
    // need both surfaces should fan out themselves.
    return false
  }
}

/**
 * Derives trigger.dev tags from job type, metadata, and explicit tags.
 * Tags follow the `namespace:value` convention for consistent filtering.
 * Max 10 tags per run, each max 128 chars.
 */
function buildTags(options?: EnqueueOptions): string[] {
  const tags: string[] = []
  const meta = options?.metadata

  if (options?.jobId) tags.push(`jobId:${options.jobId}`)

  const executionId =
    meta?.correlation?.executionId ??
    (typeof meta?.executionId === 'string' ? meta.executionId : undefined)
  if (executionId) tags.push(buildExecutionTag(executionId))

  const workflowId =
    meta?.correlation?.workflowId ??
    (typeof meta?.workflowId === 'string' ? meta.workflowId : undefined)
  if (meta?.workspaceId) tags.push(`workspaceId:${meta.workspaceId}`)
  if (workflowId) tags.push(buildWorkflowTag(workflowId))
  if (meta?.userId) tags.push(`userId:${meta.userId}`)

  if (meta?.correlation) {
    const c = meta.correlation
    tags.push(`source:${c.source}`)
    if (c.webhookId) tags.push(`webhookId:${c.webhookId}`)
    if (c.scheduleId) tags.push(`scheduleId:${c.scheduleId}`)
    if (c.provider) tags.push(`provider:${c.provider}`)
  }

  if (options?.tags) {
    for (const tag of options.tags) {
      if (!tags.includes(tag)) tags.push(tag)
    }
  }

  return tags.slice(0, 10)
}
