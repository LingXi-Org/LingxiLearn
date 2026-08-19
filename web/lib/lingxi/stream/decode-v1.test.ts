import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

import { decodeLingxiV1Event } from './decode-v1'

const FIXTURE_DIR = path.resolve(process.cwd(), '..', 'contracts', 'fixtures', 'mothership-stream-v1')

function fixtureEvents(): unknown[] {
  return readdirSync(FIXTURE_DIR)
    .filter((name) => name.endsWith('.json'))
    .flatMap((name) => JSON.parse(readFileSync(path.join(FIXTURE_DIR, name), 'utf8')) as unknown[])
}

function firstEvent(type: string): Record<string, unknown> {
  const event = fixtureEvents().find(
    (candidate) => typeof candidate === 'object' && candidate !== null && (candidate as { type?: unknown }).type === type
  )
  expect(event).toBeDefined()
  return structuredClone(event) as Record<string, unknown>
}

function eventFrom(type: string, payload: Record<string, unknown>): Record<string, unknown> {
  const event = firstEvent('run')
  event.type = type
  event.payload = payload
  return event
}

function expectError(value: unknown, code: string, errorPath: string): void {
  const result = decodeLingxiV1Event(value)
  expect(result.ok).toBe(false)
  if (result.ok) return
  expect(result.error).toMatchObject({ code, path: errorPath })
}

describe('strict V1 stream decoder', () => {
  it('preserves every shared backend fixture', () => {
    for (const value of fixtureEvents()) {
      const result = decodeLingxiV1Event(value)
      expect(result.ok, result.ok ? undefined : `${result.error.path}: ${result.error.message}`).toBe(true)
    }
  })

  it('returns structured envelope errors instead of null', () => {
    expectError(null, 'invalid_envelope', '$')
    expectError({ v: 0 }, 'unsupported_version', 'v')
    const event = firstEvent('run')
    delete (event.stream as Record<string, unknown>).executionId
    expectError(event, 'missing_identity', 'stream.executionId')
  })

  it('rejects unknown envelope and payload fields', () => {
    const envelope = firstEvent('run')
    envelope.protocol_version = 0
    expectError(envelope, 'unknown_field', 'protocol_version')

    const payload = firstEvent('run')
    ;(payload.payload as Record<string, unknown>).checkpoint = 'internal-state'
    expectError(payload, 'unknown_field', 'payload.checkpoint')
  })

  it('requires canonical span identity and equality with its scope', () => {
    const missing = firstEvent('span')
    ;(missing.payload as Record<string, unknown>).agentRunId = ''
    expectError(missing, 'missing_identity', 'payload.agentRunId')

    const mismatched = firstEvent('span')
    ;(mismatched.scope as Record<string, unknown>).agentRunId = 'guessed-run'
    expectError(mismatched, 'identity_mismatch', 'payload.agentRunId')
  })

  it('requires a canonical tool call id and agent run scope', () => {
    const missingCall = firstEvent('tool')
    delete (missingCall.payload as Record<string, unknown>).toolCallId
    expectError(missingCall, 'missing_identity', 'payload.toolCallId')

    const unscoped = firstEvent('tool')
    ;(unscoped.scope as Record<string, unknown>).agentRunId = ''
    expectError(unscoped, 'missing_identity', 'scope.agentRunId')
  })

  it.each([
    ['turn', 'turnId', 'payload.turnId'],
  ])('requires %s canonical identity', (type, field, errorPath) => {
    const event = firstEvent(type)
    delete (event.payload as Record<string, unknown>)[field]
    expectError(event, 'missing_identity', errorPath)
  })

  it('requires canonical interaction identity', () => {
    const event = eventFrom('interaction', {
      purpose: 'clarification',
      presentation: 'question',
      blocking: true,
    })
    expectError(event, 'missing_identity', 'payload.interactionId')
  })

  it('rejects malformed interaction questions and mixed union variants', () => {
    const nullQuestion = eventFrom('interaction', {
      interactionId: 'interaction-1',
      purpose: 'clarification',
      presentation: 'question',
      blocking: true,
      questions: [null],
    })
    expectError(nullQuestion, 'invalid_payload', 'payload.questions.0')

    const nullOption = eventFrom('interaction', {
      interactionId: 'interaction-1',
      purpose: 'clarification',
      presentation: 'options',
      blocking: true,
      questions: [{
        id: 'question-1',
        type: 'single_select',
        prompt: 'Choose',
        options: [null],
        allowFreeText: false,
      }],
    })
    expectError(nullOption, 'invalid_payload', 'payload.questions.0.options.0')

    const mixed = eventFrom('interaction', {
      interactionId: 'interaction-1',
      answers: [],
      purpose: 'clarification',
    })
    expectError(mixed, 'unknown_field', 'payload.purpose')
  })

  it('rejects fields from the other span union variant', () => {
    const event = firstEvent('span')
    ;(event.payload as Record<string, unknown>).status = 'completed'
    expectError(event, 'unknown_field', 'payload.status')
  })

  it('requires canonical resource identity', () => {
    const event = firstEvent('resource')
    delete ((event.payload as Record<string, unknown>).resource as Record<string, unknown>).id
    expectError(event, 'missing_identity', 'payload.resource.id')
  })

  it('does not silently reinterpret malformed V1 as V0', () => {
    const event = firstEvent('span')
    ;(event.payload as Record<string, unknown>).agentRunId = ''
    const result = decodeLingxiV1Event(event)
    expect(result).toMatchObject({
      ok: false,
      error: { code: 'missing_identity', path: 'payload.agentRunId' },
    })
  })
})
