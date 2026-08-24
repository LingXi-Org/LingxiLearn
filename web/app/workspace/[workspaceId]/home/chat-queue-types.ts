import type { QueuedMessage } from './types'

export interface QueuedSendHandoffSeed {
  id: string
  chatId?: string
  supersededStreamId: string | null
  userMessageId?: string
}

export type QueuedMothershipMessage = QueuedMessage & {
  idempotencyKey?: string
  queuedSendHandoff?: QueuedSendHandoffSeed
  resumeUserMessageId?: string
}

export type QueuedMessageEditPatch = Pick<
  QueuedMessage,
  'content' | 'fileAttachments' | 'contexts'
> & {
  idempotencyKey?: string
}
