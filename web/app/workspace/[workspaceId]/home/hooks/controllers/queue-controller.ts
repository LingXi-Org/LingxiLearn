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
