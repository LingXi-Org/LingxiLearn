import {
  decodeLingxiMothershipEvent,
  type LingxiMothershipEventV1,
  type LingxiV1EventType,
} from '../generated/mothership-stream-v1'

export type LingxiV1DecodeErrorCode =
  | 'invalid_envelope'
  | 'unsupported_version'
  | 'invalid_field'
  | 'unknown_field'
  | 'invalid_payload'
  | 'missing_identity'
  | 'identity_mismatch'

export interface LingxiV1DecodeError {
  code: LingxiV1DecodeErrorCode
  path: string
  message: string
}

export type LingxiV1DecodeResult =
  | { ok: true; event: LingxiMothershipEventV1 }
  | { ok: false; error: LingxiV1DecodeError }

type RecordValue = Record<string, unknown>

const EVENT_TYPES = new Set<LingxiV1EventType>([
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

const ENVELOPE_KEYS = new Set(['v', 'seq', 'ts', 'type', 'stream', 'scope', 'trace', 'payload'])
const STREAM_KEYS = new Set(['chatId', 'turnId', 'executionId', 'streamId'])
const SCOPE_KEYS = new Set(['agentRunId', 'parentAgentRunId', 'skillRunId'])
const TRACE_KEYS = new Set(['requestId', 'runId'])

const PAYLOAD_KEYS: Record<LingxiV1EventType, ReadonlySet<string>> = {
  turn: new Set(['turnId', 'turnIndex', 'status', 'userText']),
  text: new Set(['channel', 'delta', 'text', 'streamId', 'source', 'code']),
  span: new Set([
    'kind',
    'event',
    'agentRunId',
    'providerId',
    'displayName',
    'executionKind',
    'capability',
    'presentationRole',
    'parentAgentRunId',
    'skillIds',
    'status',
    'detail',
  ]),
  tool: new Set([
    'toolCallId',
    'toolKind',
    'toolName',
    'displayTitle',
    'status',
    'safeParams',
    'safeResult',
    'startedAt',
    'endedAt',
  ]),
  interaction: new Set([
    'interactionId',
    'purpose',
    'presentation',
    'blocking',
    'title',
    'prompt',
    'questions',
    'reasonCode',
    'dismissible',
    'answers',
  ]),
  resource: new Set(['resource', 'removed']),
  run: new Set(['status', 'executionId', 'interactionId', 'detail']),
  error: new Set(['message', 'code', 'fatal']),
  complete: new Set(['status', 'finishedReason']),
}
const SPAN_START_KEYS = new Set([
  'kind',
  'event',
  'agentRunId',
  'providerId',
  'displayName',
  'executionKind',
  'capability',
  'presentationRole',
  'parentAgentRunId',
  'skillIds',
])
const SPAN_END_KEYS = new Set(['kind', 'event', 'agentRunId', 'status', 'detail'])
const INTERACTION_REQUEST_KEYS = new Set([
  'interactionId',
  'purpose',
  'presentation',
  'blocking',
  'title',
  'prompt',
  'questions',
  'reasonCode',
  'dismissible',
])
const INTERACTION_RESOLVED_KEYS = new Set(['interactionId', 'answers'])

const TURN_STATUSES = new Set([
  'started',
  'awaiting_user',
  'resumed',
  'delivered',
  'failed',
  'cancelled',
])
const TOOL_STATUSES = new Set([
  'call',
  'generating',
  'executing',
  'awaiting_approval',
  'success',
  'error',
  'cancelled',
  'skipped',
  'rejected',
])
const SPAN_STATUSES = new Set([
  'queued',
  'running',
  'awaiting_user',
  'completed',
  'failed',
  'cancelled',
])
const RUN_STATUSES = new Set([
  'started',
  'checkpoint_pause',
  'resumed',
  'completed',
  'failed',
  'cancelled',
])
const COMPLETE_STATUSES = new Set(['delivered', 'failed', 'cancelled', 'awaiting_user'])
const RESOURCE_TYPES = new Set(['file', 'table', 'knowledgebase', 'task', 'skill'])

function fail(code: LingxiV1DecodeErrorCode, path: string, message: string): LingxiV1DecodeResult {
  return { ok: false, error: { code, path, message } }
}

function isRecord(value: unknown): value is RecordValue {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function unknownKey(value: RecordValue, allowed: ReadonlySet<string>): string | undefined {
  return Object.keys(value).find((key) => !allowed.has(key))
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

function optionalString(value: unknown): boolean {
  return value === undefined || typeof value === 'string'
}

function inSet(value: unknown, allowed: ReadonlySet<string>): value is string {
  return typeof value === 'string' && allowed.has(value)
}

function validateEnvelopeRecords(value: RecordValue): LingxiV1DecodeResult | undefined {
  const extraEnvelopeKey = unknownKey(value, ENVELOPE_KEYS)
  if (extraEnvelopeKey) {
    return fail('unknown_field', extraEnvelopeKey, 'V1 envelope contains an unknown field')
  }
  if (!isRecord(value.stream)) return fail('invalid_field', 'stream', 'stream must be an object')
  if (!isRecord(value.scope)) return fail('invalid_field', 'scope', 'scope must be an object')
  if (!isRecord(value.trace)) return fail('invalid_field', 'trace', 'trace must be an object')
  if (!isRecord(value.payload))
    return fail('invalid_payload', 'payload', 'payload must be an object')

  for (const [path, record, allowed] of [
    ['stream', value.stream, STREAM_KEYS],
    ['scope', value.scope, SCOPE_KEYS],
    ['trace', value.trace, TRACE_KEYS],
  ] as const) {
    const extra = unknownKey(record, allowed)
    if (extra) return fail('unknown_field', `${path}.${extra}`, `${path} contains an unknown field`)
  }

  for (const key of STREAM_KEYS) {
    if (!nonEmptyString(value.stream[key])) {
      return fail('missing_identity', `stream.${key}`, `stream.${key} must be a non-empty string`)
    }
  }
  for (const key of SCOPE_KEYS) {
    if (typeof value.scope[key] !== 'string') {
      return fail('invalid_field', `scope.${key}`, `scope.${key} must be a string`)
    }
  }
  for (const key of TRACE_KEYS) {
    if (typeof value.trace[key] !== 'string') {
      return fail('invalid_field', `trace.${key}`, `trace.${key} must be a string`)
    }
  }
  return undefined
}

function validateCommonPayload(
  type: LingxiV1EventType,
  payload: RecordValue
): LingxiV1DecodeResult | undefined {
  const allowed =
    type === 'span'
      ? payload.event === 'start'
        ? SPAN_START_KEYS
        : SPAN_END_KEYS
      : type === 'interaction'
        ? 'answers' in payload
          ? INTERACTION_RESOLVED_KEYS
          : INTERACTION_REQUEST_KEYS
        : PAYLOAD_KEYS[type]
  const extra = unknownKey(payload, allowed)
  if (extra)
    return fail('unknown_field', `payload.${extra}`, `${type} payload contains an unknown field`)
  return undefined
}

function validatePayload(
  type: LingxiV1EventType,
  payload: RecordValue,
  scope: RecordValue
): LingxiV1DecodeResult | undefined {
  const commonError = validateCommonPayload(type, payload)
  if (commonError) return commonError

  switch (type) {
    case 'turn':
      if (!nonEmptyString(payload.turnId))
        return fail('missing_identity', 'payload.turnId', 'turnId is required')
      if (!Number.isInteger(payload.turnIndex) || (payload.turnIndex as number) < 0)
        return fail(
          'invalid_payload',
          'payload.turnIndex',
          'turnIndex must be a non-negative integer'
        )
      if (!inSet(payload.status, TURN_STATUSES))
        return fail('invalid_payload', 'payload.status', 'invalid turn status')
      if (!optionalString(payload.userText))
        return fail('invalid_payload', 'payload.userText', 'userText must be a string')
      return undefined
    case 'text':
      if (!inSet(payload.channel, new Set(['assistant', 'narration'])))
        return fail('invalid_payload', 'payload.channel', 'invalid text channel')
      for (const key of ['delta', 'text', 'streamId', 'code']) {
        if (!optionalString(payload[key]))
          return fail('invalid_payload', `payload.${key}`, `${key} must be a string`)
      }
      if (payload.source !== undefined && !inSet(payload.source, new Set(['agent', 'system'])))
        return fail('invalid_payload', 'payload.source', 'invalid text source')
      return undefined
    case 'span': {
      if (payload.kind !== 'agent')
        return fail('invalid_payload', 'payload.kind', 'span kind must be agent')
      if (payload.event !== 'start' && payload.event !== 'end')
        return fail('invalid_payload', 'payload.event', 'span event must be start or end')
      if (!nonEmptyString(payload.agentRunId))
        return fail('missing_identity', 'payload.agentRunId', 'agentRunId is required')
      if (!nonEmptyString(scope.agentRunId))
        return fail('missing_identity', 'scope.agentRunId', 'span requires agent run scope')
      if (payload.agentRunId !== scope.agentRunId)
        return fail(
          'identity_mismatch',
          'payload.agentRunId',
          'agentRunId must match scope.agentRunId'
        )
      if (payload.event === 'start') {
        if (!optionalString(payload.providerId) || !optionalString(payload.displayName))
          return fail('invalid_payload', 'payload', 'span labels must be strings')
        if (!inSet(payload.executionKind, new Set(['model', 'deterministic'])))
          return fail('invalid_payload', 'payload.executionKind', 'invalid execution kind')
        if (!inSet(payload.presentationRole, new Set(['primary', 'supporting', 'background'])))
          return fail('invalid_payload', 'payload.presentationRole', 'invalid presentation role')
        if (!optionalString(payload.capability) || !optionalString(payload.parentAgentRunId))
          return fail('invalid_payload', 'payload', 'span metadata must be strings')
        if (
          payload.skillIds !== undefined &&
          (!Array.isArray(payload.skillIds) ||
            !payload.skillIds.every((id) => typeof id === 'string'))
        )
          return fail('invalid_payload', 'payload.skillIds', 'skillIds must be an array of strings')
      } else if (!inSet(payload.status, SPAN_STATUSES)) {
        return fail('invalid_payload', 'payload.status', 'invalid span status')
      }
      return undefined
    }
    case 'tool':
      if (!nonEmptyString(payload.toolCallId))
        return fail('missing_identity', 'payload.toolCallId', 'toolCallId is required')
      if (!nonEmptyString(scope.agentRunId))
        return fail('missing_identity', 'scope.agentRunId', 'tool events require agent run scope')
      if (!inSet(payload.toolKind, new Set(['skill', 'tool'])))
        return fail('invalid_payload', 'payload.toolKind', 'invalid tool kind')
      if (!nonEmptyString(payload.toolName))
        return fail('invalid_payload', 'payload.toolName', 'toolName is required')
      if (!inSet(payload.status, TOOL_STATUSES))
        return fail('invalid_payload', 'payload.status', 'invalid tool status')
      if (payload.safeParams !== undefined && !isRecord(payload.safeParams))
        return fail('invalid_payload', 'payload.safeParams', 'safeParams must be an object')
      if (payload.safeResult !== undefined && !isRecord(payload.safeResult))
        return fail('invalid_payload', 'payload.safeResult', 'safeResult must be an object')
      return undefined
    case 'interaction':
      if (!nonEmptyString(payload.interactionId))
        return fail('missing_identity', 'payload.interactionId', 'interactionId is required')
      if ('answers' in payload) {
        if (!Array.isArray(payload.answers) || !payload.answers.every(isRecord))
          return fail('invalid_payload', 'payload.answers', 'answers must be an array of objects')
      } else {
        if (!inSet(payload.purpose, new Set(['clarification', 'assessment', 'confirmation'])))
          return fail('invalid_payload', 'payload.purpose', 'invalid interaction purpose')
        if (!inSet(payload.presentation, new Set(['question', 'options'])))
          return fail('invalid_payload', 'payload.presentation', 'invalid interaction presentation')
        if (typeof payload.blocking !== 'boolean')
          return fail('invalid_payload', 'payload.blocking', 'blocking must be a boolean')
        for (const key of ['title', 'prompt', 'reasonCode']) {
          if (!optionalString(payload[key]))
            return fail('invalid_payload', `payload.${key}`, `${key} must be a string`)
        }
        if (payload.dismissible !== undefined && typeof payload.dismissible !== 'boolean')
          return fail('invalid_payload', 'payload.dismissible', 'dismissible must be a boolean')
        if (payload.questions !== undefined) {
          if (!Array.isArray(payload.questions))
            return fail('invalid_payload', 'payload.questions', 'questions must be an array')
          for (let index = 0; index < payload.questions.length; index += 1) {
            const question = payload.questions[index]
            const base = `payload.questions.${index}`
            if (!isRecord(question))
              return fail('invalid_payload', base, 'question must be an object')
            const extra = unknownKey(
              question,
              new Set(['id', 'type', 'prompt', 'options', 'allowFreeText'])
            )
            if (extra)
              return fail('unknown_field', `${base}.${extra}`, 'question contains an unknown field')
            if (!nonEmptyString(question.id) || !nonEmptyString(question.prompt))
              return fail('invalid_payload', base, 'question id and prompt are required')
            if (!inSet(question.type, new Set(['single_select', 'multi_select'])))
              return fail('invalid_payload', `${base}.type`, 'invalid question type')
            if (typeof question.allowFreeText !== 'boolean')
              return fail(
                'invalid_payload',
                `${base}.allowFreeText`,
                'allowFreeText must be boolean'
              )
            if (!Array.isArray(question.options))
              return fail('invalid_payload', `${base}.options`, 'options must be an array')
            for (let optionIndex = 0; optionIndex < question.options.length; optionIndex += 1) {
              const option = question.options[optionIndex]
              const optionBase = `${base}.options.${optionIndex}`
              if (!isRecord(option))
                return fail('invalid_payload', optionBase, 'option must be an object')
              const optionExtra = unknownKey(option, new Set(['id', 'label']))
              if (optionExtra)
                return fail(
                  'unknown_field',
                  `${optionBase}.${optionExtra}`,
                  'option contains an unknown field'
                )
              if (!nonEmptyString(option.id) || !nonEmptyString(option.label))
                return fail('invalid_payload', optionBase, 'option id and label are required')
            }
          }
        }
      }
      return undefined
    case 'resource': {
      if (!isRecord(payload.resource))
        return fail('invalid_payload', 'payload.resource', 'resource must be an object')
      const allowed = new Set([
        'id',
        'type',
        'title',
        'path',
        'sourceAgentRunId',
        'artifactKind',
        'mimeType',
      ])
      const extra = unknownKey(payload.resource, allowed)
      if (extra)
        return fail(
          'unknown_field',
          `payload.resource.${extra}`,
          'resource contains an unknown field'
        )
      if (!nonEmptyString(payload.resource.id))
        return fail('missing_identity', 'payload.resource.id', 'resource id is required')
      if (!inSet(payload.resource.type, RESOURCE_TYPES))
        return fail('invalid_payload', 'payload.resource.type', 'invalid resource type')
      if (typeof payload.resource.title !== 'string')
        return fail('invalid_payload', 'payload.resource.title', 'resource title must be a string')
      if (payload.removed !== undefined && typeof payload.removed !== 'boolean')
        return fail('invalid_payload', 'payload.removed', 'removed must be a boolean')
      return undefined
    }
    case 'run':
      if (!inSet(payload.status, RUN_STATUSES))
        return fail('invalid_payload', 'payload.status', 'invalid run status')
      if (!optionalString(payload.executionId) || !optionalString(payload.interactionId))
        return fail('invalid_payload', 'payload', 'run identities must be strings')
      return undefined
    case 'error':
      if (!nonEmptyString(payload.message))
        return fail('invalid_payload', 'payload.message', 'error message is required')
      if (
        !optionalString(payload.code) ||
        (payload.fatal !== undefined && typeof payload.fatal !== 'boolean')
      )
        return fail('invalid_payload', 'payload', 'invalid error payload')
      return undefined
    case 'complete':
      if (!inSet(payload.status, COMPLETE_STATUSES))
        return fail('invalid_payload', 'payload.status', 'invalid completion status')
      if (!optionalString(payload.finishedReason))
        return fail('invalid_payload', 'payload.finishedReason', 'finishedReason must be a string')
      return undefined
  }
}

/** Decode only canonical V1 events. A malformed current event is an explicit
 * error; callers must not reinterpret it through a compatibility reader. */
export function decodeLingxiV1Event(value: unknown): LingxiV1DecodeResult {
  if (!isRecord(value)) return fail('invalid_envelope', '$', 'V1 event must be an object')
  if (value.v !== 1) return fail('unsupported_version', 'v', 'only protocol version 1 is accepted')
  if (!Number.isInteger(value.seq) || (value.seq as number) < 0)
    return fail('invalid_field', 'seq', 'seq must be a non-negative integer')
  if (!nonEmptyString(value.ts)) return fail('invalid_field', 'ts', 'ts must be a non-empty string')
  if (typeof value.type !== 'string' || !EVENT_TYPES.has(value.type as LingxiV1EventType))
    return fail('invalid_field', 'type', 'unknown V1 event type')

  const recordsError = validateEnvelopeRecords(value)
  if (recordsError) return recordsError

  const type = value.type as LingxiV1EventType
  const payloadError = validatePayload(
    type,
    value.payload as RecordValue,
    value.scope as RecordValue
  )
  if (payloadError) return payloadError

  const event = decodeLingxiMothershipEvent(value)
  if (!event) return fail('invalid_envelope', '$', 'generated V1 decoder rejected the event')
  return { ok: true, event }
}
