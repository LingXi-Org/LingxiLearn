/**
 * Python ↔ TypeScript contract gate for Lingxi Mothership Stream V1 (issue #18).
 *
 * The fixtures in `contracts/fixtures/mothership-stream-v1/` are produced by
 * the *Python* projector (see `scripts/gen_mothership_v1_fixtures.py`).  This
 * test proves the TypeScript decoder accepts exactly that wire format; the
 * mirrored Python test (`server/tests/test_mothership_stream_v1.py`) proves
 * the projector still emits it.  Neither side may drift alone.
 */

import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  decodeLingxiMothershipEvent,
  isAssistantText,
  isNarrationText,
  isSkillTool,
  isSpanEnd,
  isSpanStart,
  type LingxiMothershipEventV1,
} from './mothership-stream-v1'

// vitest runs with cwd = web/, so the shared contract fixtures sit one level up.
const FIXTURE_DIR = path.resolve(
  process.cwd(),
  '..',
  'contracts',
  'fixtures',
  'mothership-stream-v1'
)

function loadFixtures(): Array<{ name: string; events: LingxiMothershipEventV1[] }> {
  const files = readdirSync(FIXTURE_DIR).filter((name) => name.endsWith('.json'))
  expect(files.length).toBeGreaterThan(0)
  return files.map((name) => {
    const raw = JSON.parse(readFileSync(path.join(FIXTURE_DIR, name), 'utf-8')) as unknown[]
    const events = raw.map((item) => {
      const decoded = decodeLingxiMothershipEvent(item)
      expect(decoded, `${name}: every envelope must decode`).not.toBeNull()
      return decoded as LingxiMothershipEventV1
    })
    return { name, events }
  })
}

describe('mothership stream v1 contract fixtures', () => {
  it('decodes every shared fixture with strictly increasing sequence numbers', () => {
    for (const { name, events } of loadFixtures()) {
      let previous = 0
      for (const event of events) {
        expect(event.seq, `${name}: seq must increase`).toBeGreaterThan(previous)
        previous = event.seq
        expect(event.stream.chatId.length, `${name}: chatId is required`).toBeGreaterThan(0)
      }
    }
  })

  it('decodes the single primary agent scenario end to end', () => {
    const fixture = loadFixtures().find(({ name }) => name === 'single-primary-agent.json')
    expect(fixture).toBeDefined()
    const events = fixture?.events ?? []

    const spanStart = events.find(
      (event) => event.type === 'span' && isSpanStart(event.payload)
    )
    expect(spanStart).toBeDefined()
    if (!spanStart) return
    expect(isSpanStart(spanStart.payload)).toBe(true)
    expect(spanStart.scope.agentRunId).toBe(
      (spanStart.payload as { agentRunId?: string }).agentRunId
    )
    expect((spanStart.payload as { presentationRole?: string }).presentationRole).toBe('primary')

    const skillTools = events.filter(
      (event) => event.type === 'tool' && isSkillTool(event.payload)
    )
    expect(skillTools.length).toBeGreaterThanOrEqual(2)

    const assistant = events.filter(
      (event) => event.type === 'text' && isAssistantText(event.payload)
    )
    expect(assistant.length).toBeGreaterThan(0)

    const narration = events.filter(
      (event) => event.type === 'text' && isNarrationText(event.payload)
    )
    expect(narration.length).toBeGreaterThan(0)
    expect(narration[0].scope.agentRunId).not.toBe('')

    const complete = events.find((event) => event.type === 'complete')
    expect(complete).toBeDefined()
    expect((complete?.payload as { status?: string })?.status).toBe('delivered')
  })

  it('decodes parallel siblings with distinct agent run identities', () => {
    const fixture = loadFixtures().find(({ name }) => name === 'parallel-siblings.json')
    const events = fixture?.events ?? []
    const starts = events.filter((event) => event.type === 'span' && isSpanStart(event.payload))
    expect(starts).toHaveLength(2)
    const ids = starts.map(
      (event) => (event.payload as { agentRunId: string }).agentRunId
    )
    expect(new Set(ids).size).toBe(2)
    const ends = events.filter((event) => event.type === 'span' && isSpanEnd(event.payload))
    expect(ends).toHaveLength(2)
  })

  it('decodes a multi-turn thread with per-turn user text', () => {
    const fixture = loadFixtures().find(({ name }) => name === 'multi-turn-thread.json')
    const events = fixture?.events ?? []
    const started = events.filter(
      (event) =>
        event.type === 'turn' && (event.payload as { status?: string }).status === 'started'
    )
    expect(started).toHaveLength(2)
    expect((started[0].payload as { userText?: string }).userText).toBe('什么是量子叠加？')
    expect((started[1].payload as { userText?: string }).userText).toBe('那测量之后为什么坍缩？')
    // The thread stays open between turns: exactly one complete event.
    expect(events.filter((event) => event.type === 'complete')).toHaveLength(1)
  })

  it('never leaks checkpoint or plan state through the pause fixture', () => {
    const fixture = loadFixtures().find(({ name }) => name === 'blocking-question-pause.json')
    const pause = fixture?.events.find(
      (event) =>
        event.type === 'run' &&
        (event.payload as { status?: string }).status === 'checkpoint_pause'
    )
    expect(pause).toBeDefined()
    const payload = pause?.payload as Record<string, unknown>
    expect(Object.keys(payload).every((key) => ['status', 'executionId', 'interactionId'].includes(key))).toBe(
      true
    )
  })

  it('rejects malformed envelopes instead of guessing', () => {
    expect(decodeLingxiMothershipEvent(null)).toBeNull()
    expect(decodeLingxiMothershipEvent('span')).toBeNull()
    expect(decodeLingxiMothershipEvent({ v: 2, seq: 1, ts: 't', type: 'run', payload: {} })).toBeNull()
    expect(
      decodeLingxiMothershipEvent({ v: 1, seq: 1, ts: 't', type: 'whisper', payload: {} })
    ).toBeNull()
    expect(
      decodeLingxiMothershipEvent({ v: 1, seq: -1, ts: 't', type: 'run', payload: {} })
    ).toBeNull()
    expect(
      decodeLingxiMothershipEvent({ v: 1, seq: 1, ts: 't', type: 'run', payload: 'not-an-object' })
    ).toBeNull()
  })
})
