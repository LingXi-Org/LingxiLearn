/**
 * Lingxi Mothership Stream V1 → turn model (issue #18 §18.3).
 *
 * A pure reducer over decoded V1 envelopes.  Every turn independently owns
 * its user text, assistant content blocks, interactions, resources and the
 * AgentRun tree, so the transcript rebuilt after a refresh is structurally
 * identical to the live one — no task-level mega message, no synthetic span
 * identities, no guessing from event order.
 */

import type { ContentBlock, ToolCallInfo, ToolCallStatus } from '../chat-types'
import type { LingxiMothershipEventV1 } from '../generated/mothership-stream-v1'
import { isSpanEnd, isSpanStart } from '../generated/mothership-stream-v1'

export type LingxiV1TurnStatus = 'active' | 'awaiting_user' | 'delivered' | 'failed' | 'cancelled'

export interface LingxiV1InteractionOption {
  id: string
  label: string
}

export interface LingxiV1InteractionQuestion {
  id: string
  type: 'single_select' | 'multi_select'
  prompt: string
  options: LingxiV1InteractionOption[]
  allowFreeText: boolean
}

export interface LingxiV1InteractionCard {
  interactionId: string
  blocking: boolean
  prompt: string
  questions: LingxiV1InteractionQuestion[]
  status: 'pending' | 'resolved'
  /** Structured answers as resumed by the server (drives the recap). */
  answers: Array<Record<string, unknown>>
}

export interface LingxiV1AgentRun {
  agentRunId: string
  providerId: string
  displayName: string
  executionKind: 'model' | 'deterministic'
  capability: string
  presentationRole: 'primary' | 'supporting' | 'background'
  parentAgentRunId: string
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  startedAt?: string
  endedAt?: string
}

export interface LingxiV1Resource {
  id: string
  type: 'file' | 'table' | 'knowledgebase' | 'task' | 'skill'
  title: string
  path?: string
  artifactKind?: string
  sourceAgentRunId?: string
}

export interface LingxiV1Turn {
  turnId: string
  turnIndex: number
  status: LingxiV1TurnStatus
  userText: string
  assistantText: string
  /** Assistant text deltas per stream id; the primary lane renders last. */
  streamText: Record<string, string>
  blocks: ContentBlock[]
  interactions: LingxiV1InteractionCard[]
  resources: LingxiV1Resource[]
  agentRuns: LingxiV1AgentRun[]
  executionIds: string[]
}

export interface LingxiV1ThreadModel {
  chatId: string
  turns: LingxiV1Turn[]
  lastSeq: number
}

/** The option-id encoding that ties a rendered question card to its typed
 * interaction: `interactionId | questionId | optionId`. */
export const INTERACTION_OPTION_PREFIX = 'it_'
const OPTION_ID_SEPARATOR = '|'

export function encodeInteractionOptionId(
  interactionId: string,
  questionId: string,
  optionId: string
): string {
  return [interactionId, questionId, optionId].join(OPTION_ID_SEPARATOR)
}

export function decodeInteractionOptionId(
  value: string
): { interactionId: string; questionId: string; optionId: string } | null {
  if (!value.startsWith(INTERACTION_OPTION_PREFIX)) return null
  const parts = value.split(OPTION_ID_SEPARATOR)
  if (parts.length !== 3) return null
  const [interactionId, questionId, optionId] = parts
  if (!interactionId || !questionId || !optionId) return null
  return { interactionId, questionId, optionId }
}

export function emptyV1ThreadModel(chatId: string): LingxiV1ThreadModel {
  return { chatId, turns: [], lastSeq: 0 }
}

function emptyTurn(turnId: string): LingxiV1Turn {
  return {
    turnId,
    turnIndex: 0,
    status: 'active',
    userText: '',
    assistantText: '',
    streamText: {},
    blocks: [],
    interactions: [],
    resources: [],
    agentRuns: [],
    executionIds: [],
  }
}

function turnOf(model: LingxiV1ThreadModel, envelope: LingxiMothershipEventV1): LingxiV1Turn {
  // Turn events carry their own authoritative turnId; other events scope via
  // the stream envelope.
  const payloadTurnId =
    envelope.type === 'turn' ? str((envelope.payload as Record<string, unknown>).turnId) : ''
  const turnId = payloadTurnId || envelope.stream.turnId || model.chatId
  const existing = model.turns.find((turn) => turn.turnId === turnId)
  if (existing) return existing
  const turn = emptyTurn(turnId)
  model.turns.push(turn)
  model.turns.sort((left, right) => left.turnIndex - right.turnIndex)
  return turn
}

function activeTurn(model: LingxiV1ThreadModel, envelope: LingxiMothershipEventV1): LingxiV1Turn {
  const turnId = envelope.stream.turnId || model.chatId
  const scoped = model.turns.find((turn) => turn.turnId === turnId)
  if (scoped) return scoped
  return model.turns[model.turns.length - 1] ?? turnOf(model, envelope)
}

const TOOL_STATUS_MAP: Record<string, ToolCallStatus> = {
  call: 'executing',
  generating: 'executing',
  executing: 'executing',
  awaiting_approval: 'awaiting_approval',
  success: 'success',
  error: 'error',
  cancelled: 'cancelled',
  skipped: 'skipped',
  rejected: 'rejected',
}

function toolStatusOf(status: string): ToolCallStatus {
  return TOOL_STATUS_MAP[status] ?? 'executing'
}

function displayNameOf(model: LingxiV1ThreadModel, turn: LingxiV1Turn, agentRunId: string): string {
  const run = turn.agentRuns.find((candidate) => candidate.agentRunId === agentRunId)
  if (run) return run.displayName
  for (const other of model.turns) {
    const found = other.agentRuns.find((candidate) => candidate.agentRunId === agentRunId)
    if (found) return found.displayName
  }
  return agentRunId
}

function questionTagFor(card: LingxiV1InteractionCard): string {
  const items = card.questions.map((question) => ({
    type: question.type,
    prompt: question.prompt || card.prompt,
    options: question.options.map((option) => ({
      id: encodeInteractionOptionId(card.interactionId, question.id, option.id),
      label: option.label,
    })),
  }))
  return items.length > 0 ? `<question>${JSON.stringify(items)}</question>` : ''
}

/** Recompose the turn's assistant text: primary stream, then the question
 * card tag, then resource tags — stable order regardless of arrival. */
function refreshAssistantText(turn: LingxiV1Turn): void {
  const parts: string[] = []
  const primary = Object.entries(turn.streamText)
    .filter(([key]) => !key.startsWith('__'))
    .map(([, value]) => value)
    .filter(Boolean)
  if (primary.length > 0) parts.push(primary.join(''))
  const question = turn.streamText.__question__
  if (question) parts.push(question)
  const resources = turn.streamText.__resource__
  if (resources) parts.push(resources)
  turn.assistantText = parts.filter(Boolean).join('\n\n')
}

/** Apply one V1 envelope; returns the same model reference for chaining. */
export function reduceV1Event(
  model: LingxiV1ThreadModel,
  envelope: LingxiMothershipEventV1
): LingxiV1ThreadModel {
  if (envelope.seq <= model.lastSeq && envelope.seq !== 0) {
    // SSE replay after reconnect may redeliver; keep the higher watermark.
    if (model.lastSeq >= envelope.seq && alreadyApplied(model, envelope)) return model
  }
  model.lastSeq = Math.max(model.lastSeq, envelope.seq)
  const payload = envelope.payload as Record<string, unknown>

  switch (envelope.type) {
    case 'turn': {
      const turn = turnOf(model, envelope)
      turn.turnId = str(payload.turnId) || turn.turnId
      turn.turnIndex = num(payload.turnIndex, turn.turnIndex)
      const userText = str(payload.userText)
      if (userText && !turn.userText) turn.userText = userText
      const status = str(payload.status)
      if (status === 'started' || status === 'resumed') turn.status = 'active'
      else if (status === 'awaiting_user') turn.status = 'awaiting_user'
      else if (status === 'delivered') turn.status = 'delivered'
      else if (status === 'failed') turn.status = 'failed'
      else if (status === 'cancelled') turn.status = 'cancelled'
      model.turns.sort((left, right) => left.turnIndex - right.turnIndex)
      return model
    }
    case 'span': {
      const turn = activeTurn(model, envelope)
      if (isSpanStart(payload)) {
        const run: LingxiV1AgentRun = {
          agentRunId: payload.agentRunId,
          providerId: payload.providerId ?? '',
          displayName: payload.displayName || payload.providerId || payload.agentRunId,
          executionKind: payload.executionKind ?? 'model',
          capability: payload.capability ?? '',
          presentationRole: payload.presentationRole ?? 'supporting',
          parentAgentRunId: payload.parentAgentRunId ?? '',
          status: 'running',
          startedAt: envelope.ts,
        }
        if (!turn.agentRuns.some((candidate) => candidate.agentRunId === run.agentRunId)) {
          turn.agentRuns.push(run)
        }
        turn.blocks.push({
          type: 'subagent',
          subagent: run.displayName,
          spanId: run.agentRunId,
          parentSpanId: run.parentAgentRunId || undefined,
          timestamp: Date.parse(envelope.ts) || undefined,
        })
      } else if (isSpanEnd(payload)) {
        const run = turn.agentRuns.find((candidate) => candidate.agentRunId === payload.agentRunId)
        if (run) {
          run.status =
            payload.status === 'completed'
              ? 'completed'
              : payload.status === 'cancelled'
                ? 'cancelled'
                : 'failed'
          run.endedAt = envelope.ts
        }
        turn.blocks.push({
          type: 'subagent_end',
          subagent: displayNameOf(model, turn, payload.agentRunId),
          spanId: payload.agentRunId,
          endedAt: true,
          timestamp: Date.parse(envelope.ts) || undefined,
        })
      }
      return model
    }
    case 'text': {
      const turn = activeTurn(model, envelope)
      const channel = str(payload.channel)
      if (channel === 'narration') {
        const text = str(payload.text) || str(payload.delta)
        if (!text) return model
        turn.blocks.push({
          type: 'subagent_text',
          content: text,
          subagent: displayNameOf(model, turn, envelope.scope.agentRunId),
          spanId: envelope.scope.agentRunId || undefined,
          timestamp: Date.parse(envelope.ts) || undefined,
        })
        return model
      }
      // assistant: append into the turn's primary stream buffer
      const streamId = str(payload.streamId) || '__primary__'
      const delta = str(payload.delta)
      const full = str(payload.text)
      const buffer = turn.streamText[streamId] ?? ''
      turn.streamText[streamId] = full || buffer + delta
      refreshAssistantText(turn)
      return model
    }
    case 'tool': {
      const turn = activeTurn(model, envelope)
      const toolCall: ToolCallInfo = {
        id: str(payload.toolCallId),
        name: str(payload.toolName),
        displayTitle: str(payload.displayTitle) || undefined,
        status: toolStatusOf(str(payload.status)),
        params: (payload.safeParams as Record<string, unknown> | undefined) ?? {},
      }
      const safeResult = payload.safeResult as Record<string, unknown> | undefined
      if (safeResult) {
        toolCall.result = {
          success: toolCall.status !== 'error',
          output: safeResult,
        }
      }
      const existing = turn.blocks.findIndex(
        (block) => block.type === 'tool_call' && block.toolCall?.id === toolCall.id
      )
      const block: ContentBlock = {
        type: 'tool_call',
        toolCall,
        spanId: envelope.scope.agentRunId || undefined,
        timestamp: Date.parse(envelope.ts) || undefined,
      }
      if (existing >= 0) turn.blocks[existing] = block
      else turn.blocks.push(block)
      return model
    }
    case 'interaction': {
      const turn = activeTurn(model, envelope)
      const interactionId = str(payload.interactionId)
      if (!interactionId) return model
      if (payload.questions !== undefined) {
        const card: LingxiV1InteractionCard = {
          interactionId,
          blocking: payload.blocking !== false,
          prompt: str(payload.prompt) || str(payload.title),
          questions: (Array.isArray(payload.questions) ? payload.questions : []).map((raw) => {
            const question = raw as Record<string, unknown>
            return {
              id: str(question.id),
              type: str(question.type) === 'multi_select' ? 'multi_select' : 'single_select',
              prompt: str(question.prompt),
              options: (Array.isArray(question.options) ? question.options : []).map((option) => {
                const record = option as Record<string, unknown>
                return { id: str(record.id), label: str(record.label) }
              }),
              allowFreeText: question.allowFreeText === true,
            }
          }),
          status: 'pending',
          answers: [],
        }
        turn.interactions = [
          ...turn.interactions.filter((item) => item.interactionId !== interactionId),
          card,
        ]
        if (card.blocking) {
          turn.status = 'awaiting_user'
          const tag = questionTagFor(card)
          if (tag && !turn.streamText.__question__) {
            turn.streamText.__question__ = tag
            refreshAssistantText(turn)
          }
        }
      } else {
        // resolved: keep the card for the recap
        const card = turn.interactions.find((item) => item.interactionId === interactionId)
        const answers = Array.isArray(payload.answers)
          ? (payload.answers as Array<Record<string, unknown>>)
          : []
        if (card) {
          card.status = 'resolved'
          card.answers = answers
        }
        if (turn.status === 'awaiting_user') turn.status = 'active'
      }
      return model
    }
    case 'resource': {
      const turn = activeTurn(model, envelope)
      const raw = payload.resource as Record<string, unknown> | undefined
      if (!raw) return model
      const resource: LingxiV1Resource = {
        id: str(raw.id),
        type: (['file', 'table', 'knowledgebase', 'task', 'skill'].includes(str(raw.type))
          ? str(raw.type)
          : 'file') as LingxiV1Resource['type'],
        title: str(raw.title) || str(raw.artifactKind) || str(raw.id),
        path: str(raw.path) || undefined,
        artifactKind: str(raw.artifactKind) || undefined,
        sourceAgentRunId: str(raw.sourceAgentRunId) || undefined,
      }
      if (resource.id) {
        turn.resources = [...turn.resources.filter((item) => item.id !== resource.id), resource]
        if (resource.type === 'file' && resource.id.startsWith('file_')) {
          const tag = `<workspace_resource type="file" id="${resource.id}" title="${resource.title}"></workspace_resource>`
          const existing = str(turn.streamText.__resource__ ?? '')
          if (!existing.includes(tag)) {
            turn.streamText.__resource__ = [existing, tag].filter(Boolean).join('\n')
            refreshAssistantText(turn)
          }
        }
      }
      return model
    }
    case 'run': {
      const turn = activeTurn(model, envelope)
      const executionId = str(payload.executionId) || envelope.stream.executionId
      if (executionId && !turn.executionIds.includes(executionId)) {
        turn.executionIds.push(executionId)
      }
      const status = str(payload.status)
      if (status === 'checkpoint_pause') turn.status = 'awaiting_user'
      else if (status === 'started' || status === 'resumed') {
        if (turn.status !== 'awaiting_user') turn.status = 'active'
      }
      return model
    }
    case 'error': {
      const turn = activeTurn(model, envelope)
      if (payload.fatal === true) turn.status = 'failed'
      return model
    }
    case 'complete': {
      const turn = activeTurn(model, envelope)
      const status = str(payload.status)
      if (status === 'failed') turn.status = 'failed'
      else if (status === 'cancelled') turn.status = 'cancelled'
      else if (status === 'awaiting_user') turn.status = 'awaiting_user'
      else if (turn.status === 'active') turn.status = 'delivered'
      return model
    }
    default:
      return model
  }
}

function alreadyApplied(_model: LingxiV1ThreadModel, _envelope: LingxiMothershipEventV1): boolean {
  // Sequence-ordered replay makes redelivery structurally idempotent for the
  // reducer's upserts; spans and tools key by id, turns by turnId.
  return true
}

function str(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function num(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

export function reduceV1Events(
  model: LingxiV1ThreadModel,
  envelopes: Array<LingxiMothershipEventV1 | null | undefined>
): LingxiV1ThreadModel {
  for (const envelope of envelopes) {
    if (envelope) reduceV1Event(model, envelope)
  }
  return model
}

/** The left-side chat's visible agent identities (issue #18 §14.5 parity). */
export function visibleAgentRunIds(model: LingxiV1ThreadModel): Set<string> {
  const ids = new Set<string>()
  for (const turn of model.turns) {
    for (const run of turn.agentRuns) ids.add(run.agentRunId)
  }
  return ids
}

/** Answer labels for a resolved interaction card (drives the recap). */
export function interactionAnswerLabels(card: LingxiV1InteractionCard): string[] {
  if (card.status !== 'resolved') return []
  const byOption = new Map<string, string>()
  for (const question of card.questions) {
    for (const option of question.options) byOption.set(option.id, option.label)
  }
  const labels: string[] = []
  for (const answer of card.answers) {
    const selected = Array.isArray(answer.selectedOptionIds)
      ? answer.selectedOptionIds.map((id) => byOption.get(String(id)) ?? String(id))
      : []
    const text = typeof answer.text === 'string' && answer.text.trim() ? answer.text.trim() : ''
    const joined = [...selected, text].filter(Boolean).join('、')
    if (joined) labels.push(joined)
  }
  return labels
}

/** One question's answer as the card reports it: option ids, never labels. */
export interface LingxiV1SubmittedAnswer {
  questionIndex: number
  selectedOptionIds: string[]
  text: string
}

export interface LingxiV1InteractionAnswerRequest {
  interactionId: string
  answers: Array<{ questionId: string; selectedOptionIds: string[]; text: string | null }>
  /** Labels for the optimistic user bubble; display only. */
  labels: string[]
}

/** The thread's open blocking interaction, if it has one. */
export function pendingInteraction(
  model: LingxiV1ThreadModel
): LingxiV1InteractionCard | undefined {
  for (let index = model.turns.length - 1; index >= 0; index -= 1) {
    const card = model.turns[index].interactions.find(
      (item) => item.status === 'pending' && item.blocking
    )
    if (card) return card
  }
  return undefined
}

/**
 * Turn a question card's submission into the typed interaction answer request
 * (issue #18 §10.4).
 *
 * Option ids arriving from a rendered card are the encoded
 * `interactionId|questionId|optionId` triples; they are decoded back to the
 * real option identity here.  Returns null when this batch is not the open
 * typed interaction, which is the caller's signal to fall back to an ordinary
 * message rather than guess.
 */
export function buildInteractionAnswerRequest(
  model: LingxiV1ThreadModel,
  submitted: LingxiV1SubmittedAnswer[]
): LingxiV1InteractionAnswerRequest | null {
  if (submitted.length === 0) return null
  const card = pendingInteraction(model)
  if (!card || card.questions.length === 0) return null

  const answers: LingxiV1InteractionAnswerRequest['answers'] = []
  const labels: string[] = []
  for (const item of submitted) {
    const question = card.questions[item.questionIndex]
    if (!question) continue
    const optionIds: string[] = []
    for (const encoded of item.selectedOptionIds) {
      const optionId = decodeInteractionOptionId(encoded)?.optionId ?? encoded
      optionIds.push(optionId)
      const option = question.options.find((candidate) => candidate.id === optionId)
      if (option) labels.push(option.label)
    }
    const text = item.text.trim()
    if (text) labels.push(text)
    if (optionIds.length === 0 && !text) continue
    answers.push({ questionId: question.id, selectedOptionIds: optionIds, text: text || null })
  }
  if (answers.length === 0) return null
  return { interactionId: card.interactionId, answers, labels }
}

export function buildV1ThreadModel(
  chatId: string,
  envelopes: Array<LingxiMothershipEventV1 | null | undefined>
): LingxiV1ThreadModel {
  return reduceV1Events(emptyV1ThreadModel(chatId), envelopes)
}
