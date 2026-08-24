import type { Dispatch, SetStateAction } from 'react'
import type { FilePreviewSession } from '@/lib/copilot/request/session/file-preview-session-contract'
import type { ChatContext } from '@/lib/lingxi/chat-context'
import type { LingxiTaskTransport } from '@/lib/lingxi/lingxi-task-transport'
import type { LingxiV1ThreadModel } from '@/lib/lingxi/stream/turn-model'
import type { LingxiTurnState } from '@/lib/lingxi/turn-state'
import type { AgentTaskEvent, AgentTaskSnapshot } from '@/lib/lingxi/types'
import type { TypedQuestionAnswer } from '../components/message-content/components/question/typed-answers'
import type {
  ChatMessage,
  FileAttachmentForApi,
  GenericResourceData,
  MothershipResource,
  MothershipResourceType,
  QueuedMessage,
} from '../types'

export interface SendMessageOptions {
  resumeUserMessageId?: string
}

export interface UseChatOptions {
  adapter?: LingxiTaskTransport
  onResourceEvent?: (resourceId: string, eventKind?: 'artifact.ready' | 'delivery.unlocked') => void
  initialActiveResourceId?: string | null
  activeResourceState?: [string | null, Dispatch<SetStateAction<string | null>>]
  onStreamEnd?: (chatId: string, messages: ChatMessage[]) => void
  onRequestStarted?: (info: { requestId: string; userMessageId: string }) => void
}

export interface UseChatReturn {
  messages: ChatMessage[]
  isSending: boolean
  isReconnecting: boolean
  error: string | null
  resolvedChatId: string | undefined
  desktopScopeId: string
  sendMessage: (
    message: string,
    fileAttachments?: FileAttachmentForApi[],
    contexts?: ChatContext[],
    options?: SendMessageOptions
  ) => Promise<void>
  answerInteraction?: (answers: TypedQuestionAnswer[]) => boolean | Promise<boolean>
  stopGeneration: () => Promise<void>
  resources: MothershipResource[]
  activeResourceId: string | null
  setActiveResourceId: (id: string | null) => void
  addResource: (resource: MothershipResource) => boolean
  removeResource: (resourceType: MothershipResourceType, resourceId: string) => void
  reorderResources: (resources: MothershipResource[]) => void
  messageQueue: QueuedMessage[]
  removeFromQueue: (id: string) => void
  sendNow: (id: string) => Promise<void>
  editQueuedMessage: (id: string) => QueuedMessage | undefined
  cancelQueueEdit: () => void
  editingQueuedId: string | null
  dispatchingHeadId: string | null
  previewSession: FilePreviewSession | null
  genericResourceData: GenericResourceData | null
  lingxiRuntime?: {
    task: AgentTaskSnapshot | null
    events: AgentTaskEvent[]
    workflowState?: Record<string, unknown> | null
    turnState?: LingxiTurnState
    v1Model?: LingxiV1ThreadModel | null
  }
  getCurrentRequestId: () => string | undefined
}
