import type { LingxiAttachmentRef, LingxiTaskContextOptions } from '@/lib/api/domains/agent-tasks'
import {
  cancelAgentTask,
  createAgentTask,
  getAgentTask,
  getAgentTaskEvents,
  sendAgentMessage,
  subscribeAgentEvents,
  updateAgentTask,
} from '@/lib/api/domains/agent-tasks'
import type { AgentTaskEvent, AgentTaskSnapshot } from '@/lib/lingxi/types'

export interface LingxiTaskSubscriptionOptions {
  from?: number
  onEvent: (event: AgentTaskEvent) => void
  onEnd?: (status: string) => void
}

/** Protocol-neutral I/O boundary. Transcript projection belongs to a decoder/reducer. */
export interface LingxiTaskTransport {
  createTask(
    prompt: string,
    attachments?: LingxiAttachmentRef[],
    options?: LingxiTaskContextOptions
  ): Promise<{ id: string; status: string }>
  loadTask(taskId: string): Promise<AgentTaskSnapshot>
  loadEvents(taskId: string): Promise<AgentTaskEvent[]>
  sendMessage(
    taskId: string,
    message: string,
    attachments?: LingxiAttachmentRef[],
    options?: LingxiTaskContextOptions
  ): Promise<{ status: string }>
  cancelTask(taskId: string): Promise<{ id: string; status: string }>
  updateTaskMetadata(
    taskId: string,
    patch: { resources?: Array<Record<string, unknown>> }
  ): Promise<unknown>
  subscribe(taskId: string, options: LingxiTaskSubscriptionOptions): () => void
}

export function createLingxiTaskTransport(): LingxiTaskTransport {
  return {
    createTask: createAgentTask,
    loadTask: getAgentTask,
    loadEvents: async (taskId) => (await getAgentTaskEvents(taskId)).events,
    sendMessage: sendAgentMessage,
    cancelTask: cancelAgentTask,
    updateTaskMetadata: (taskId, patch) => updateAgentTask(taskId, patch),
    subscribe(taskId, options) {
      return subscribeAgentEvents(taskId, options.onEvent, {
        from: options.from,
        onEnd: options.onEnd,
      })
    },
  }
}
