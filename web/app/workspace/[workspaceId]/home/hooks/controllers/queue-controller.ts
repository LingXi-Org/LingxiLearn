export function pendingQueueKey(workspaceId: string): string {
  return `lingxi:pending:${workspaceId}`
}

export function queueKeyFor(workspaceId: string, taskId?: string): string {
  return taskId || pendingQueueKey(workspaceId)
}

export function queueMigration(workspaceId: string, taskId: string) {
  return { from: pendingQueueKey(workspaceId), to: taskId }
}

export function lingxiIdempotencyKey(messageId: string, revision = ''): string {
  return `lingxi-message:${messageId}${revision ? `:${revision}` : ''}`
}

export function queueHead<T extends { id: string }>(
  queue: readonly T[],
  editingId: string | null | undefined,
  dispatchingId: string | null | undefined,
  turnState: string
): T | null {
  if (dispatchingId || !['idle', 'awaiting_user'].includes(turnState)) return null
  const head = queue[0]
  return head && editingId !== head.id ? head : null
}

export function queueKeysContaining<T extends { id: string }>(
  queues: Readonly<Record<string, readonly T[]>>,
  messageId: string
): string[] {
  return Object.entries(queues)
    .filter(([, queue]) => queue.some((message) => message.id === messageId))
    .map(([key]) => key)
}
