import type { ContentBlock } from '@/lib/lingxi/chat-types'
import {
  type AgentTaskEvent,
  type AgentTaskSnapshot,
  isAgentTaskTerminal,
} from '@/lib/lingxi/types'

export interface LingxiGraphV0Projection {
  blocks: ContentBlock[]
  assistantText: string
  isTerminal: boolean
}

/**
 * Minimal read-only reader for retained pre-V1 history.
 *
 * It deliberately does not reconstruct AgentRun, SkillRun, ToolCall, plan, or
 * interrupt identity. Those facts did not exist canonically in V0 and must not
 * be guessed from labels, ordering, or synthesized span ids.
 *
 * Delete this module after all deployments have stopped V0 dual writes and
 * retained `protocol_version = 0` rows have drained through the support window.
 */

const LEARNER_FACING_AGENTS = new Set(['answer_user', 'learning_companion', 'learner_interview'])

const V1_EVENT_TYPES = new Set([
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

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function explicitText(payload: Record<string, unknown>): string {
  return (
    text(payload.message) || text(payload.text) || text(payload.content) || text(payload.summary)
  )
}

function carriesV1Envelope(event: AgentTaskEvent): boolean {
  const candidates = [record(event), record(event.payload)].filter(
    (candidate): candidate is Record<string, unknown> => candidate !== null
  )
  return candidates.some((candidate) => {
    if (candidate.v === 1 || candidate.protocol_version === 1 || candidate.protocolVersion === 1) {
      return true
    }
    return (
      typeof candidate.seq === 'number' &&
      V1_EVENT_TYPES.has(text(candidate.type)) &&
      record(candidate.stream) !== null &&
      record(candidate.scope) !== null
    )
  })
}

/** Malformed/current V1 rows may never enter the heuristic compatibility path. */
export function assertV0History(events: AgentTaskEvent[]): void {
  if (events.some(carriesV1Envelope)) {
    throw new TypeError('LingxiGraph V0 reader rejects Mothership Stream V1 envelopes')
  }
}

export function projectLingxiGraphV0History(
  task: AgentTaskSnapshot,
  inputEvents: AgentTaskEvent[] = []
): LingxiGraphV0Projection {
  assertV0History(inputEvents)
  const events = [...new Map(inputEvents.map((event) => [event.sequence, event])).values()].sort(
    (left, right) => left.sequence - right.sequence
  )
  const paragraphs: string[] = []
  let question = ''

  for (const event of events) {
    const payload = record(event.payload) ?? {}
    if (
      (event.kind === 'agent.output' || event.kind === 'agent.output.delta') &&
      LEARNER_FACING_AGENTS.has(String(event.agent ?? ''))
    ) {
      const output = explicitText(payload)
      if (output) paragraphs.push(output)
      continue
    }
    if (event.kind === 'task.completed' && paragraphs.length === 0) {
      const summary = explicitText(payload)
      if (summary) paragraphs.push(summary)
      continue
    }
    if (event.kind === 'interrupt.raised' && !question) {
      question = text(payload.prompt) || text(payload.question)
    }
  }

  if (question) paragraphs.push(question)
  const assistantText = paragraphs.join('\n\n')
  const blocks: ContentBlock[] = assistantText
    ? [{ type: 'text', content: assistantText, timestamp: events.at(-1)?.sequence }]
    : []

  return {
    blocks,
    assistantText,
    isTerminal: isAgentTaskTerminal(task),
  }
}
