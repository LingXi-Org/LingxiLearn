import { z } from 'zod'
import { userFileSchema } from '@/lib/api/contracts/primitives'
import { defineRouteContract } from '@/lib/api/contracts/types'

const comparisonOperatorSchema = z.enum(['=', '>', '<', '>=', '<=', '!='])

export const logIdParamsSchema = z.object({
  id: z.string().min(1),
})

export const executionIdParamsSchema = z.object({
  executionId: z.string().min(1),
})

const logFilterQuerySchema = z.object({
  workspaceId: z.string(),
  level: z.string().optional(),
  workflowIds: z.string().optional(),
  folderIds: z.string().optional(),
  triggers: z.string().optional(),
  startDate: z.string().optional(),
  endDate: z.string().optional(),
  search: z.string().optional(),
  workflowName: z.string().optional(),
  folderName: z.string().optional(),
  executionId: z.string().optional(),
  costOperator: comparisonOperatorSchema.optional(),
  costValue: z.coerce.number().optional(),
  durationOperator: comparisonOperatorSchema.optional(),
  durationValue: z.coerce.number().optional(),
})

export const logSortBySchema = z.enum(['date', 'duration', 'cost', 'status']).default('date')
export const logSortOrderSchema = z.enum(['asc', 'desc']).default('desc')

export const listLogsQuerySchema = logFilterQuerySchema.extend({
  cursor: z.string().optional(),
  limit: z.coerce.number().int().min(1).max(200).optional().default(100),
  sortBy: logSortBySchema,
  sortOrder: logSortOrderSchema,
})

export const logDetailQuerySchema = z.object({
  workspaceId: z.string().min(1),
})

export const statsQueryParamsSchema = logFilterQuerySchema.extend({
  segmentCount: z.coerce.number().optional().default(72),
})

const workflowSummarySchema = z
  .object({
    id: z.string(),
    name: z.string().nullable(),
    description: z.string().nullable(),
    folderId: z.string().nullable(),
    userId: z.string().nullable(),
    workspaceId: z.string().nullable(),
    createdAt: z.string().nullable(),
    updatedAt: z.string().nullable(),
  })
  .partial()

const tokenBreakdownSchema = z
  .object({
    total: z.number().optional(),
    input: z.number().optional(),
    output: z.number().optional(),
    prompt: z.number().optional(),
    completion: z.number().optional(),
  })
  .partial()

const modelCostSchema = z
  .object({
    input: z.number().optional(),
    output: z.number().optional(),
    total: z.number().optional(),
    tokens: tokenBreakdownSchema.optional(),
  })
  .partial()

const costSummarySchema = z
  .object({
    total: z.number().optional(),
    input: z.number().optional(),
    output: z.number().optional(),
    tokens: tokenBreakdownSchema.optional(),
    models: z.record(z.string(), modelCostSchema).optional(),
    pricing: z
      .object({
        input: z.number(),
        output: z.number(),
        cachedInput: z.number().optional(),
        updatedAt: z.string(),
      })
      .optional(),
  })
  .partial()

/**
 * Itemized cost breakdown derived from the usage_log ledger (the single source
 * of truth) for the detail view. Each item is one billed line (base fee, a
 * model, or a tool/integration); the items reconcile to `total`.
 */
const costLedgerItemSchema = z.object({
  category: z.enum(['fixed', 'model', 'tool']),
  description: z.string(),
  cost: z.number(),
  inputTokens: z.number().optional(),
  outputTokens: z.number().optional(),
})

export const costLedgerSchema = z.object({
  total: z.number(),
  items: z.array(costLedgerItemSchema),
})

export type CostLedger = z.output<typeof costLedgerSchema>
export type CostLedgerItem = z.output<typeof costLedgerItemSchema>

const pauseSummarySchema = z.object({
  status: z.string().nullable(),
  total: z.number(),
  resumed: z.number(),
})

const blockExecutionSchema = z.object({
  id: z.string(),
  blockId: z.string(),
  blockName: z.string(),
  blockType: z.string(),
  startedAt: z.string(),
  endedAt: z.string(),
  durationMs: z.number(),
  status: z.enum(['success', 'error', 'skipped']),
  errorMessage: z.string().optional(),
  errorStackTrace: z.string().optional(),
  inputData: z.unknown(),
  outputData: z.unknown(),
  cost: costSummarySchema.optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
})

export type ExecutionTimelineSpan = {
  [key: string]: unknown
  id: string
  name: string
  kind: string
  durationMs: number
  startedAt: string
  endedAt: string
  status: string
  errorHandled?: boolean
  errorType?: string
  errorMessage?: string
  nodeId?: string
  input?: unknown
  output?: unknown
  tokens?: {
    total?: number
    input?: number
    output?: number
    cacheRead?: number
    cacheWrite?: number
    reasoning?: number
  }
  cost?: { total?: number; input?: number; output?: number; toolCost?: number }
  relativeStartMs?: number
  category?: string
  provider?: string
  executionOrder?: number
  tries?: number
  model?: string
  finishReason?: string
  ttft?: number
  iterationIndex?: number
  thinking?: string
  modelToolCalls?: unknown[]
  children?: ExecutionTimelineSpan[]
}

export const executionTimelineSpanSchema: z.ZodType<ExecutionTimelineSpan> = z
  .lazy(() =>
    z
      .object({
        id: z.string().describe('Trace-span identifier.'),
        name: z.string().describe('Trace-span name.'),
        kind: z.string().describe('Execution span category.'),
        durationMs: z.number().describe('Span duration in milliseconds.'),
        startedAt: z.string().describe('ISO 8601 span start timestamp.'),
        endedAt: z.string().describe('ISO 8601 span end timestamp.'),
        status: z.string().describe('Execution span status.'),
        errorHandled: z.boolean().describe('Whether the recorded error was handled.').optional(),
        errorType: z.string().describe('Recorded error type.').optional(),
        errorMessage: z.string().describe('Recorded error message.').optional(),
        nodeId: z.string().describe('Execution node associated with the span.').optional(),
        input: z.unknown().describe('Input captured for the traced operation.').optional(),
        output: z.unknown().describe('Output captured for the traced operation.').optional(),
        tokens: z
          .object({
            total: z.number().describe('Total tokens.').optional(),
            input: z.number().describe('Input tokens.').optional(),
            output: z.number().describe('Output tokens.').optional(),
            cacheRead: z.number().describe('Cache-read tokens.').optional(),
            cacheWrite: z.number().describe('Cache-write tokens.').optional(),
            reasoning: z.number().describe('Reasoning tokens.').optional(),
          })
          .describe('Token usage attributed to the span.')
          .optional(),
        cost: z
          .object({
            total: z.number().describe('Total span cost in USD.').optional(),
            input: z.number().describe('Input-token cost in USD.').optional(),
            output: z.number().describe('Output-token cost in USD.').optional(),
            toolCost: z.number().describe('Tool cost in USD.').optional(),
          })
          .partial()
          .describe('Cost attributed to the span.')
          .optional(),
        relativeStartMs: z
          .number()
          .describe('Offset from the root span in milliseconds.')
          .optional(),
        children: z
          .array(executionTimelineSpanSchema)
          .describe('Nested child execution spans.')
          .optional(),
      })
      .catchall(z.unknown().describe('Additional provider-specific trace-span metadata.'))
  )
  .meta({
    id: 'ExecutionTimelineSpan',
    title: 'Execution timeline span',
    description: 'One recursive operation span in a LingxiLearn execution timeline.',
  })

export const timelineSpansSchema = z.array(executionTimelineSpanSchema)

export const executionTimelineSchema = z.object({
  schemaVersion: z.literal('lingxilearn.timeline.v1'),
  executionId: z.string(),
  spans: z.array(executionTimelineSpanSchema),
  totalTokens: z.number(),
  waitingForUserMs: z.number(),
})

export const nativeExecutionSnapshotSchema = z.object({
  schemaVersion: z.literal('lingxilearn.execution.v1'),
  executionId: z.string(),
  taskId: z.string(),
  graphVersion: z.string(),
  status: z.string(),
  paused: z.boolean(),
  terminal: z.boolean(),
  nodes: z.record(z.string(), z.record(z.string(), z.unknown())),
  dependencies: z.array(z.record(z.string(), z.unknown())),
  variables: z.record(z.string(), z.unknown()),
  groups: z.record(z.string(), z.unknown()),
  metadata: z.record(z.string(), z.unknown()),
})

export const runtimeEventSchema = z.object({
  sequence: z.number().optional(),
  kind: z.string(),
  agent: z.string().optional(),
  payload: z.record(z.string(), z.unknown()).optional(),
  runtime: z.record(z.string(), z.unknown()).optional(),
  executionId: z.string().nullable().optional(),
  createdAt: z.string().nullable().optional(),
})

/** Versioned semantic trajectory projection used by the Logs timing overview. */
export const trajectoryLaneIdSchema = z.enum([
  'run',
  'control',
  'task',
  'action',
  'runtime',
  'state',
  'resource',
  'output',
])

export const trajectoryItemSchema = z.object({
  id: z.string(),
  lane: trajectoryLaneIdSchema,
  kind: z.string(),
  label: z.string(),
  status: z.string().optional(),
  startTime: z.string(),
  endTime: z.string().optional(),
  relativeStartMs: z.number(),
  durationMs: z.number(),
  parentId: z.string().optional(),
  decisionId: z.string().optional(),
  roundStep: z.number().optional(),
  turnId: z.string().optional(),
  workItemId: z.string().optional(),
  spanId: z.string().optional(),
  attempt: z.number().optional(),
  precision: z.enum(['exact', 'inferred']),
  metadata: z.record(z.string(), z.unknown()).optional(),
})

export type TrajectoryItem = z.output<typeof trajectoryItemSchema>

export const trajectoryLaneSchema = z.object({
  id: trajectoryLaneIdSchema,
  label: z.string(),
  items: z.array(trajectoryItemSchema),
})

export const trajectorySchema = z.object({
  version: z.string(),
  executionId: z.string(),
  clock: z.object({
    startedAt: z.string(),
    endedAt: z.string().nullable().optional(),
    durationMs: z.number(),
  }),
  lanes: z.array(trajectoryLaneSchema),
  relations: z.array(z.record(z.string(), z.unknown())).optional(),
  summary: z.record(z.string(), z.unknown()).optional(),
})

export type Trajectory = z.output<typeof trajectorySchema>

const executionDataDetailSchema = z
  .object({
    totalDuration: z.number().nullable().optional(),
    enhanced: z.literal(true).optional(),
    timeline: executionTimelineSchema.optional(),
    trajectory: trajectorySchema.optional(),
    runtimeEvents: z.array(runtimeEventSchema).optional(),
    blockExecutions: z.array(blockExecutionSchema).optional(),
    finalOutput: z.unknown().optional(),
    workflowInput: z.unknown().optional(),
    blockInput: z.record(z.string(), z.unknown()).optional(),
    trigger: z.unknown().optional(),
  })
  .passthrough()

/**
 * Wire schema for one execution-log row. The Lingxi domain model is
 * execution-centric (`ExecutionLog*`); legacy wire field names (`workflowId`,
 * `workflow`, `jobTitle`) are kept for backend wire compatibility and are
 * translated into the native observability view model by the logs mapper —
 * UI code must not treat them as a workflow identity.
 */
export const executionLogSummarySchema = z.object({
  id: z.string(),
  workflowId: z.string().nullable(),
  executionId: z.string().nullable(),
  deploymentVersionId: z.string().nullable(),
  deploymentVersion: z.number().nullable(),
  deploymentVersionName: z.string().nullable(),
  executionOrigin: z.enum(['workflow_group']).nullable(),
  level: z.string(),
  status: z.string().nullable(),
  duration: z.string().nullable(),
  trigger: z.string().nullable(),
  createdAt: z.string(),
  workflow: workflowSummarySchema.nullable(),
  jobTitle: z.string().nullable(),
  // Top-level run cost is the cost_total projection of the usage_log ledger,
  // rendered as { total } (dollars). The itemized breakdown lives in costLedger
  // (detail only); per-block costs use the richer costSummarySchema elsewhere.
  cost: z.object({ total: z.number() }).nullable(),
  pauseSummary: pauseSummarySchema,
  hasPendingPause: z.boolean(),
})

export const executionLogDetailSchema = executionLogSummarySchema.extend({
  executionData: executionDataDetailSchema,
  files: z.array(userFileSchema).nullable(),
  // Itemized, ledger-sourced cost breakdown. Null for legacy/pre-ledger runs,
  // where the UI falls back to the (reconciling) cost jsonb.
  costLedger: costLedgerSchema.nullable().optional(),
})

export type ExecutionLogSummary = z.output<typeof executionLogSummarySchema>
export type ExecutionLogDetail = z.output<typeof executionLogDetailSchema>

/**
 * A row that may be either a list-view summary or a fully loaded detail. Used by
 * UI surfaces that render the same log before and after its detail query resolves.
 */
export type ExecutionLogRow = ExecutionLogSummary &
  Partial<Pick<ExecutionLogDetail, 'executionData' | 'files' | 'costLedger'>>

export const listLogsResponseSchema = z.object({
  data: z.array(executionLogSummarySchema),
  nextCursor: z.string().nullable(),
})

export type ListLogsResponse = z.output<typeof listLogsResponseSchema>

export const segmentStatsSchema = z.object({
  timestamp: z.string(),
  totalExecutions: z.number(),
  successfulExecutions: z.number(),
  avgDurationMs: z.number(),
})

export const workflowStatsSchema = z.object({
  workflowId: z.string(),
  workflowName: z.string(),
  segments: z.array(segmentStatsSchema),
  overallSuccessRate: z.number(),
  totalExecutions: z.number(),
  totalSuccessful: z.number(),
})

export const dashboardStatsResponseSchema = z.object({
  workflows: z.array(workflowStatsSchema),
  aggregateSegments: z.array(segmentStatsSchema),
  totalRuns: z.number(),
  totalErrors: z.number(),
  avgLatency: z.number(),
  timeBounds: z.object({
    start: z.string(),
    end: z.string(),
  }),
  segmentMs: z.number(),
})

export const executionSnapshotDataSchema = z.object({
  executionId: z.string(),
  schemaVersion: z.literal('lingxilearn.execution.v1'),
  snapshot: nativeExecutionSnapshotSchema,
  timeline: executionTimelineSchema,
  trajectory: trajectorySchema.optional(),
  status: z.string().optional(),
  taskId: z.string().optional(),
  graphVersion: z.string().optional(),
  executionMetadata: z.object({
    trigger: z.string().nullable(),
    startedAt: z.string().nullable(),
    endedAt: z.string().nullable().optional(),
    totalDurationMs: z.number().nullable().optional(),
    cost: z.unknown().nullable(),
    totalTokens: z.number().nullable().optional(),
  }),
})

export const triggersQuerySchema = z.object({
  workspaceId: z.string(),
})
export type TriggersQuery = z.output<typeof triggersQuerySchema>

export type SegmentStats = z.output<typeof segmentStatsSchema>
export type WorkflowStats = z.output<typeof workflowStatsSchema>
export type DashboardStatsResponse = z.output<typeof dashboardStatsResponseSchema>
export type ExecutionSnapshotData = z.output<typeof executionSnapshotDataSchema>

export const listLogsContract = defineRouteContract({
  method: 'GET',
  path: '/api/logs',
  query: listLogsQuerySchema,
  response: {
    mode: 'json',
    schema: listLogsResponseSchema,
  },
})

export const getLogDetailContract = defineRouteContract({
  method: 'GET',
  path: '/api/logs/[id]',
  params: logIdParamsSchema,
  query: logDetailQuerySchema,
  response: {
    mode: 'json',
    schema: z.object({
      data: executionLogDetailSchema,
    }),
  },
})

export const getLogByExecutionIdContract = defineRouteContract({
  method: 'GET',
  path: '/api/logs/by-execution/[executionId]',
  params: executionIdParamsSchema,
  query: logDetailQuerySchema,
  response: {
    mode: 'json',
    schema: z.object({
      data: executionLogDetailSchema,
    }),
  },
})

export const getDashboardStatsContract = defineRouteContract({
  method: 'GET',
  path: '/api/logs/stats',
  query: statsQueryParamsSchema,
  response: {
    mode: 'json',
    schema: dashboardStatsResponseSchema,
  },
})

export const getExecutionSnapshotContract = defineRouteContract({
  method: 'GET',
  path: '/api/logs/execution/[executionId]',
  params: executionIdParamsSchema,
  response: {
    mode: 'json',
    schema: executionSnapshotDataSchema,
  },
})
