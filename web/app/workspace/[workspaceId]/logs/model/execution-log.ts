import type { z } from 'zod'
import type {
  CostLedger,
  ExecutionLogDetail,
  ExecutionTimelineSpan,
  runtimeEventSchema,
  Trajectory,
} from '@/lib/api/contracts/logs'

/**
 * Lingxi-native observability view model for the Logs surface.
 *
 * The wire contract (`ExecutionLogSummary`/`ExecutionLogDetail`) still carries
 * legacy field names (`workflowId`, `workflow`, `jobTitle`) for backend
 * compatibility. This view model is the only shape Logs presentation consumes:
 * identity is the execution (`logId` + `executionId`), the run source is a
 * classified Lingxi entity (agent task, legacy workflow, or unknown), and every
 * derived display value (status, duration, cost, pause) is precomputed by the
 * pure mapper — components never re-derive domain facts.
 */

/** Canonical identity of one observed execution row. */
export interface ExecutionLogIdentity {
  /** Log record id (row identity within the logs list). */
  logId: string
  /** Canonical runtime execution identity; null for rows that never started. */
  executionId: string | null
}

/**
 * What produced the run. `agent-task` is the Lingxi-native identity (a
 * mothership AgentTask run); `workflow` marks a legacy Sim-workflow execution;
 * `unknown` is the stable fallback when no source metadata survives.
 */
export type ExecutionSourceKind = 'agent-task' | 'workflow' | 'unknown'

export interface ExecutionRunSource {
  kind: ExecutionSourceKind
  /** Display title resolved by the mapper (job title, legacy name, or fallback). */
  title: string
}

/** Normalized run status for observability display. */
export type RunStatus =
  | 'error'
  | 'pending'
  | 'running'
  | 'redacting'
  | 'info'
  | 'cancelled'
  | 'cancelling'

/** Presentation-ready trigger metadata (no workflow block-registry lookups). */
export interface TriggerPresentation {
  type: string
  label: string
  color: string
}

/** Interaction-pause projection for a run (waiting-for-user semantics). */
export interface RunPauseState {
  total: number
  resumed: number
  hasPending: boolean
}

/**
 * List-row view model. Timing is wall-clock run timing sourced from the
 * execution record (`createdAt` + `durationMs`); cost is the canonical
 * usage-ledger total already converted to display credits.
 */
export interface ExecutionLogSummaryView {
  identity: ExecutionLogIdentity
  source: ExecutionRunSource
  status: RunStatus
  trigger: TriggerPresentation | null
  /** Run start timestamp (ISO 8601). */
  createdAt: string
  /** Wall-clock run duration in milliseconds; null while running/unknown. */
  durationMs: number | null
  /** Total run cost in display credits; null when not yet billed. */
  costCredits: number | null
  /** Total run cost in dollars (usage-ledger projection); null when unknown. */
  costTotalDollars: number | null
  pause: RunPauseState
}

/** One canonical runtime event attached to an execution. */
export type RuntimeEvent = z.output<typeof runtimeEventSchema>

/**
 * Detail view model. Trajectory and trace data are passed through untouched
 * from the canonical wire projection — the detail controller feeds them
 * straight into the canonical trajectory projector (`buildTrajectoryModel`).
 */
export interface ExecutionLogDetailView extends ExecutionLogSummaryView {
  /** Owning AgentTask id, when the wire row carries one (detail payload only). */
  taskId: string | null
  /** Whether the detail payload (executionData) has loaded, even if empty. */
  hasDetailPayload: boolean
  timelineSpans: ExecutionTimelineSpan[] | undefined
  trajectory: Trajectory | undefined
  runtimeEvents: RuntimeEvent[]
  files: ExecutionLogDetail['files']
  costLedger: CostLedger | null
  /** Input the run was started with (wire `workflowInput`), normalized. */
  runInput: unknown
  /** Final run output (wire `finalOutput`). */
  finalOutput: unknown
  /** Deployed version label (e.g. `v3` or a named version); null when absent. */
  deploymentVersionLabel: string | null
}
