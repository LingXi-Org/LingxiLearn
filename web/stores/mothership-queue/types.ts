import type {
  QueuedMessageEditPatch,
  QueuedMothershipMessage,
} from '@/app/workspace/[workspaceId]/home/chat-queue-types'

export type {
  QueuedMessageEditPatch,
  QueuedMothershipMessage,
  QueuedSendHandoffSeed,
} from '@/app/workspace/[workspaceId]/home/chat-queue-types'

export interface MothershipQueueState {
  queues: Record<string, QueuedMothershipMessage[]>
  editing: Record<string, string>

  enqueue: (chatKey: string, message: QueuedMothershipMessage) => void
  insertAt: (chatKey: string, index: number, message: QueuedMothershipMessage) => void
  replaceAt: (chatKey: string, id: string, patch: QueuedMessageEditPatch) => void
  remove: (chatKey: string, id: string) => void
  setEditing: (chatKey: string, id: string | null) => void
  migrate: (fromKey: string, toKey: string) => void
  clearChat: (chatKey: string) => void
  reset: () => void
}
