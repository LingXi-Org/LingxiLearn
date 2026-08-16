/**
 * Lingxi Mothership Stream V1 — TypeScript mirror of the backend contract.
 *
 * Generated in lockstep with
 * `server/lingxilearn/contracts/mothership_stream_v1.py`; both sides must
 * accept the shared fixtures in `contracts/fixtures/mothership-stream-v1/`
 * (issue #18).  The decoder is deliberately strict: unknown event types or
 * malformed envelopes return `null` instead of being half-rendered.
 */

export const PROTOCOL_VERSION = 1

export type LingxiV1EventType =
  | 'turn'
  | 'text'
  | 'span'
  | 'tool'
  | 'interaction'
  | 'resource'
  | 'run'
  | 'error'
  | 'complete'

export type LingxiV1TextChannel = 'assistant' | 'narration'
export type LingxiV1PresentationRole = 'primary' | 'supporting' | 'background'
export type LingxiV1ExecutionKind = 'model' | 'deterministic'
export type LingxiV1SpanStatus =
  | 'queued'
  | 'running'
  | 'awaiting_user'
  | 'completed'
  | 'failed'
  | 'cancelled'
export type LingxiV1ToolKind = 'skill' | 'tool'
export type LingxiV1ToolStatus =
  | 'call'
  | 'generating'
  | 'executing'
  | 'awaiting_approval'
  | 'success'
  | 'error'
  | 'cancelled'
  | 'skipped'
  | 'rejected'
export type LingxiV1RunStatus =
  | 'started'
  | 'checkpoint_pause'
  | 'resumed'
  | 'completed'
  | 'failed'
  | 'cancelled'
export type LingxiV1TurnStatus =
  | 'started'
  | 'awaiting_user'
  | 'resumed'
  | 'delivered'
  | 'failed'
  | 'cancelled'

export interface LingxiV1StreamScope {
  chatId: string
  turnId: string
  executionId: string
  streamId: string
}

export interface LingxiV1EventScope {
  agentRunId: string
  parentAgentRunId: string
  skillRunId: string
}

export interface LingxiV1TraceScope {
  requestId: string
  runId: string
}

export interface LingxiV1TurnPayload {
  turnId: string
  turnIndex: number
  status: LingxiV1TurnStatus
}

export interface LingxiV1TextPayload {
  channel: LingxiV1TextChannel
  delta?: string
  text?: string
  streamId?: string
  source?: 'agent' | 'system'
  code?: string
}

export interface LingxiV1SpanStartPayload {
  kind: 'agent'
  event: 'start'
  agentRunId: string
  providerId: string
  displayName: string
  executionKind: LingxiV1ExecutionKind
  capability: string
  presentationRole: LingxiV1PresentationRole
  parentAgentRunId?: string
  skillIds?: string[]
}

export interface LingxiV1SpanEndPayload {
  kind: 'agent'
  event: 'end'
  agentRunId: string
  status: LingxiV1SpanStatus
  detail?: string
}

export type LingxiV1SpanPayload = LingxiV1SpanStartPayload | LingxiV1SpanEndPayload

export interface LingxiV1ToolPayload {
  toolCallId: string
  toolKind: LingxiV1ToolKind
  toolName: string
  displayTitle?: string
  status: LingxiV1ToolStatus
  safeParams?: Record<string, unknown>
  safeResult?: Record<string, unknown>
  startedAt?: string
  endedAt?: string
}

export interface LingxiV1InteractionQuestion {
  id: string
  type: 'single_select' | 'multi_select'
  prompt: string
  options: Array<{ id: string; label: string }>
  allowFreeText: boolean
}

export interface LingxiV1InteractionRequestedPayload {
  interactionId: string
  purpose: 'clarification' | 'assessment' | 'confirmation'
  presentation: 'question' | 'options'
  blocking: boolean
  title?: string
  prompt?: string
  questions?: LingxiV1InteractionQuestion[]
  reasonCode?: string
  dismissible?: boolean
}

export interface LingxiV1InteractionResolvedPayload {
  interactionId: string
  answers: Array<Record<string, unknown>>
}

export type LingxiV1InteractionPayload =
  | LingxiV1InteractionRequestedPayload
  | LingxiV1InteractionResolvedPayload

export interface LingxiV1ResourceDescriptor {
  id: string
  type: 'file' | 'table' | 'knowledgebase' | 'task' | 'skill'
  title: string
  path?: string
  sourceAgentRunId?: string
  artifactKind?: string
  mimeType?: string
}

export interface LingxiV1ResourceUpsertPayload {
  resource: LingxiV1ResourceDescriptor
  removed: boolean
}

export interface LingxiV1RunPayload {
  status: LingxiV1RunStatus
  executionId?: string
  interactionId?: string
  detail?: string
}

export interface LingxiV1ErrorPayload {
  message: string
  code?: string
  fatal?: boolean
}

export interface LingxiV1CompletePayload {
  status: 'delivered' | 'failed' | 'cancelled' | 'awaiting_user'
  finishedReason?: string
}

export type LingxiV1EventPayload =
  | LingxiV1TurnPayload
  | LingxiV1TextPayload
  | LingxiV1SpanPayload
  | LingxiV1ToolPayload
  | LingxiV1InteractionPayload
  | LingxiV1ResourceUpsertPayload
  | LingxiV1RunPayload
  | LingxiV1ErrorPayload
  | LingxiV1CompletePayload

export interface LingxiMothershipEventV1 {
  v: 1
  seq: number
  ts: string
  type: LingxiV1EventType
  stream: LingxiV1StreamScope
  scope: LingxiV1EventScope
  trace: LingxiV1TraceScope
  payload: LingxiV1EventPayload & Record<string, unknown>
}

const EVENT_TYPES: ReadonlySet<string> = new Set([
  'turn',
  'text',
  'span',
  'tool',
  'interaction',
  'resource',
  'run',
  'error',
  'complete',
])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/**
 * Decode one public event.  Returns `null` for anything that is not a valid
 * V1 envelope — the caller drops it rather than guessing (issue #18 §3.2).
 */
export function decodeLingxiMothershipEvent(value: unknown): LingxiMothershipEventV1 | null {
  if (!isRecord(value)) return null
  if (value.v !== PROTOCOL_VERSION) return null
  if (typeof value.seq !== 'number' || !Number.isInteger(value.seq) || value.seq < 0) return null
  if (typeof value.ts !== 'string' || value.ts.length === 0) return null
  if (typeof value.type !== 'string' || !EVENT_TYPES.has(value.type)) return null
  if (!isRecord(value.stream) || typeof value.stream.chatId !== 'string') return null
  if (!isRecord(value.payload)) return null

  const scope = isRecord(value.scope) ? value.scope : {}
  const trace = isRecord(value.trace) ? value.trace : {}
  const stream = value.stream as Record<string, unknown>

  return {
    v: 1,
    seq: value.seq,
    ts: value.ts,
    type: value.type as LingxiV1EventType,
    stream: {
      chatId: String(stream.chatId ?? ''),
      turnId: String(stream.turnId ?? ''),
      executionId: String(stream.executionId ?? ''),
      streamId: String(stream.streamId ?? ''),
    },
    scope: {
      agentRunId: String(scope.agentRunId ?? ''),
      parentAgentRunId: String(scope.parentAgentRunId ?? ''),
      skillRunId: String(scope.skillRunId ?? ''),
    },
    trace: {
      requestId: String(trace.requestId ?? ''),
      runId: String(trace.runId ?? ''),
    },
    payload: value.payload as LingxiMothershipEventV1['payload'],
  }
}

/** Narrow helpers the turn model will build on in the V1 frontend stage. */

export function isSpanStart(payload: LingxiV1EventPayload): payload is LingxiV1SpanStartPayload {
  return isRecord(payload) && payload.kind === 'agent' && payload.event === 'start'
}

export function isSpanEnd(payload: LingxiV1EventPayload): payload is LingxiV1SpanEndPayload {
  return isRecord(payload) && payload.kind === 'agent' && payload.event === 'end'
}

export function isNarrationText(payload: LingxiV1EventPayload): payload is LingxiV1TextPayload {
  return isRecord(payload) && payload.channel === 'narration'
}

export function isAssistantText(payload: LingxiV1EventPayload): payload is LingxiV1TextPayload {
  return isRecord(payload) && payload.channel === 'assistant'
}

export function isSkillTool(payload: LingxiV1EventPayload): payload is LingxiV1ToolPayload {
  return isRecord(payload) && payload.toolKind === 'skill'
}
