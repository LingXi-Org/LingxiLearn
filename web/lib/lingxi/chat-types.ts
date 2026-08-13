/**
 * The small transcript contract shared by the LingxiGraph adapter and the
 * browser renderer. It intentionally contains no server contracts.
 */

export const ToolCallStatus = {
  executing: 'executing',
  success: 'success',
  error: 'error',
  cancelled: 'cancelled',
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
  | 'stopped'

export interface ContentBlock {
  type: ContentBlockType
  content?: string
  subagent?: string
  toolCall?: ToolCallInfo
  reasoningStep?: ReasoningStep
  timestamp?: number
  endedAt?: number
  spanId?: string
  parentSpanId?: string
}

export interface LingxiChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  contentBlocks?: ContentBlock[]
  requestId?: string
}
