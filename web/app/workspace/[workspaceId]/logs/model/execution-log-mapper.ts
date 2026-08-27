import type {
  ExecutionLogDetail,
  ExecutionLogRow,
  ExecutionLogSummary,
  LogTraceSpan,
} from '@/lib/api/contracts/logs'
import { dollarsToCredits } from '@/lib/billing/credits/conversion'
import { timelineSpansToTraceSpans } from '@/lib/lingxi/runtime-graph-adapter'
import type {
  ExecutionLogDetailView,
  ExecutionLogSummaryView,
  ExecutionRunSource,
  RunStatus,
  TriggerPresentation,
} from './execution-log'

/**
 * Pure mapper from the logs wire contract to the Lingxi-native observability
 * view model. No React, no queries, no workflow-editor registries: every
 * display fact is derived from the wire row alone, with stable fallbacks when
 * source metadata is missing.
 */

/** Stable label when no run source can be resolved (e.g. deleted source). */
export const UNKNOWN_RUN_SOURCE_LABEL = 'Unknown source'
/** Stable title fallback for an agent task whose job title is missing. */
export const UNTITLED_AGENT_TASK_LABEL = 'Untitled task'

const DEFAULT_TRIGGER_COLOR = '#6b7280'

/**
 * Core trigger presentation owned by the observability domain. Replaces the
 * former workflow block-registry lookups (`getBlock`) with static, stable
 * metadata.
 */
const CORE_TRIGGER_PRESENTATION: Record<string, { label: string; color: string }> = {
  manual: { label: 'Manual', color: '#6b7280' },
  api: { label: 'API', color: '#2563eb' },
  schedule: { label: 'Schedule', color: '#059669' },
  chat: { label: 'Chat', color: '#7c3aed' },
  webhook: { label: 'Webhook', color: '#ea580c' },
  mcp: { label: 'MCP', color: '#dc2626' },
  copilot: { label: 'Sim agent', color: '#ec4899' },
  mothership: { label: 'Agent', color: '#ec4899' },
  'agent-task': { label: 'Agent', color: '#ec4899' },
  workflow: { label: 'Workflow', color: '#0369a1' },
  custom_block: { label: 'Custom block', color: '#0369a1' },
}

/** Formats an integration/provider id into a display label (e.g. `microsoft_teams` → `Microsoft Teams`). */
function formatProviderLabel(provider: string): string {
  return provider
    .split(/[-_]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

/** Resolves trigger presentation from the wire trigger token. Null when absent. */
export function resolveTriggerPresentation(
  trigger: string | null | undefined
): TriggerPresentation | null {
  if (!trigger) return null
  const core = CORE_TRIGGER_PRESENTATION[trigger]
  if (core) return { type: trigger, label: core.label, color: core.color }
  return { type: trigger, label: formatProviderLabel(trigger), color: DEFAULT_TRIGGER_COLOR }
}

/** Normalizes a raw wire status into the observability run status. */
export function mapRunStatus(status: string | null | undefined): RunStatus {
  switch (status) {
    case 'running':
      return 'running'
    case 'redacting':
      return 'redacting'
    case 'pending':
      return 'pending'
    case 'cancelling':
      return 'cancelling'
    case 'cancelled':
      return 'cancelled'
    case 'failed':
      return 'error'
    case 'awaiting_user':
      // Lingxi-native waiting state: the run is paused on a user interaction.
      return 'pending'
    default:
      return 'info'
  }
}

interface WireDurationFields {
  totalDurationMs?: number | string | null
  duration?: number | string | null
}

/**
 * Parses wall-clock run duration from wire formats (`"1234ms"` strings or raw
 * numbers) into milliseconds. Null when the wire carries no usable value.
 */
export function parseRunDurationMs(wire: WireDurationFields): number | null {
  let candidate: number | null = null

  if (typeof wire.totalDurationMs === 'number') {
    candidate = wire.totalDurationMs
  } else if (typeof wire.duration === 'number') {
    candidate = wire.duration
  } else if (typeof wire.totalDurationMs === 'string') {
    candidate = Number.parseInt(String(wire.totalDurationMs).replace(/[^0-9]/g, ''), 10)
  } else if (typeof wire.duration === 'string') {
    candidate = Number.parseInt(String(wire.duration).replace(/[^0-9]/g, ''), 10)
  }

  return Number.isFinite(candidate) ? candidate : null
}

interface WireSourceFields {
  trigger?: string | null
  jobTitle?: string | null
  workflowId?: string | null
  workflow?: { id?: string; name?: string | null } | null
}

/**
 * Classifies what produced the run. An agent task (mothership trigger) takes
 * its job title; a legacy workflow run takes the workflow name carried on the
 * wire row; anything else degrades to the stable unknown label. Never resolves
 * workflow entities or block registries.
 */
export function resolveExecutionSource(wire: WireSourceFields): ExecutionRunSource {
  // `agent-task` is the current runtime trigger token; `mothership` is the
  // legacy job token still present on older rows.
  if (wire.trigger === 'agent-task' || wire.trigger === 'mothership') {
    return { kind: 'agent-task', title: wire.jobTitle?.trim() || UNTITLED_AGENT_TASK_LABEL }
  }
  if (wire.workflow?.id || wire.workflowId) {
    return { kind: 'workflow', title: wire.workflow?.name || UNKNOWN_RUN_SOURCE_LABEL }
  }
  return { kind: 'unknown', title: UNKNOWN_RUN_SOURCE_LABEL }
}

/**
 * Extracts the owning AgentTask id from the run input payload when the runtime
 * recorded it there (`{ taskId }`). Null when the wire carries no task identity.
 */
function extractTaskId(runInput: unknown, explicitTaskId?: unknown): string | null {
  if (typeof explicitTaskId === 'string' && explicitTaskId.length > 0) return explicitTaskId
  if (!runInput || typeof runInput !== 'object' || Array.isArray(runInput)) return null
  const taskId = (runInput as Record<string, unknown>).taskId
  return typeof taskId === 'string' && taskId.length > 0 ? taskId : null
}

/** Maps a wire summary row to the native list view model. */
export function mapExecutionLogSummary(wire: ExecutionLogSummary): ExecutionLogSummaryView {
  return {
    identity: { logId: wire.id, executionId: wire.executionId },
    source: resolveExecutionSource(wire),
    status: mapRunStatus(wire.status),
    trigger: resolveTriggerPresentation(wire.trigger),
    createdAt: wire.createdAt,
    durationMs: parseRunDurationMs({ duration: wire.duration }),
    costCredits: typeof wire.cost?.total === 'number' ? dollarsToCredits(wire.cost.total) : null,
    costTotalDollars: typeof wire.cost?.total === 'number' ? wire.cost.total : null,
    pause: {
      total: wire.pauseSummary.total,
      resumed: wire.pauseSummary.resumed,
      hasPending: wire.hasPendingPause,
    },
  }
}

/**
 * Maps a wire detail (or a summary mid-load) to the native detail view model.
 * Trajectory, trace spans, and runtime events pass through untouched — they are
 * the canonical projections consumed by the trajectory projector downstream.
 */
export function mapExecutionLogDetail(
  wire: ExecutionLogDetail | ExecutionLogRow
): ExecutionLogDetailView {
  const summary = mapExecutionLogSummary(wire)
  const executionData = wire.executionData
  const runInput = executionData?.workflowInput ?? null
  return {
    ...summary,
    taskId: extractTaskId(runInput, executionData?.taskId),
    hasDetailPayload: executionData != null,
    traceSpans: timelineSpansToTraceSpans(
      executionData?.timeline?.spans
    ) as unknown as LogTraceSpan[],
    trajectory: executionData?.trajectory,
    runtimeEvents: executionData?.runtimeEvents ?? [],
    files: wire.files ?? null,
    costLedger: wire.costLedger ?? null,
    runInput,
    finalOutput: executionData?.finalOutput ?? null,
    deploymentVersionLabel:
      wire.deploymentVersion != null
        ? (wire.deploymentVersionName ?? `v${wire.deploymentVersion}`)
        : null,
  }
}
