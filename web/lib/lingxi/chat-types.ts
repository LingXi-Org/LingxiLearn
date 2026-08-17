/**
 * The small transcript contract shared by the LingxiGraph adapter and the
 * browser renderer. It intentionally contains no server contracts.
 */

export const ToolCallStatus = {
  executing: 'executing',
  awaiting_approval: 'awaiting_approval',
  success: 'success',
  error: 'error',
  cancelled: 'cancelled',
  skipped: 'skipped',
  rejected: 'rejected',
  interrupted: 'interrupted',
} as const

export type ToolCallStatus = (typeof ToolCallStatus)[keyof typeof ToolCallStatus]

export interface ToolCallResult {
  success: boolean
  output?: unknown
  error?: string
}

export interface ToolCallInfo {
  id: string
  name: string
  displayTitle?: string
  status: ToolCallStatus
  params?: Record<string, unknown>
  calledBy?: string
  result?: ToolCallResult
  /** Model-authored phrase for an integration/tool gateway call. */
  integrationDescription?: string
  /** JSON argument bytes received before the call is complete. */
  streamingArgs?: string
  /** Durable learner-facing prompt for a native graph interrupt. */
  userPrompt?: string
  startedAtMs?: number
}

export type ReasoningStepStatus = 'pending' | 'active' | 'complete' | 'error'

export interface ReasoningStep {
  id: string
  title: string
  summary: string
  status: ReasoningStepStatus
  timestamp?: number
  endedAt?: number
}

export type ContentBlockType =
  | 'text'
  | 'thinking'
  | 'tool_call'
  | 'subagent'
  | 'subagent_end'
  | 'subagent_text'
  | 'subagent_thinking'
  | 'options'
  | 'stopped'

export interface ContentBlock {
  type: ContentBlockType
  content?: string
  subagent?: string
  toolCall?: ToolCallInfo
  reasoningStep?: ReasoningStep
  options?: Array<{ id: string; label: string }>
  timestamp?: number
  endedAt?: number
  parentToolCallId?: string
  spanId?: string
  parentSpanId?: string
  /** Stable V1 text lane identity, used to upsert streamed assistant prose. */
  streamId?: string
}

export interface LingxiChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  contentBlocks?: ContentBlock[]
  requestId?: string
}
