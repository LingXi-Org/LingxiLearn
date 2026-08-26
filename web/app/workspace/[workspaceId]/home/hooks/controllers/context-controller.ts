import type { LingxiAttachmentRef } from '@/lib/api/domains/agent-tasks'
import type { ChatContext } from '@/lib/lingxi/chat-context'
import type { FileAttachmentForApi } from '../../types'

function contextSuffix(contexts?: ChatContext[]): string {
  const entries = (contexts ?? [])
    .map((context) => {
      const label = context.label.trim()
      const selectionText =
        'text' in context && typeof context.text === 'string' ? context.text.trim() : ''
      return selectionText ? `${label}:\n${selectionText}` : label
    })
    .filter(Boolean)
  return entries.length ? `\n\n[Context]\n${entries.map((entry) => `- ${entry}`).join('\n')}` : ''
}

export function requestMessage(content: string, contexts?: ChatContext[]): string {
  const normalized = content.trim()
  const maxLength = 4000
  if (normalized.length >= maxLength) return normalized.slice(0, maxLength)
  return `${normalized}${contextSuffix(contexts).slice(0, maxLength - normalized.length)}`
}

export function attachmentRefs(attachments?: FileAttachmentForApi[]): LingxiAttachmentRef[] {
  return (attachments ?? [])
    .filter((attachment) => Boolean(attachment.key && attachment.filename))
    .map((attachment) => ({
      key: attachment.key,
      ...(attachment.path ? { path: attachment.path } : {}),
      filename: attachment.filename,
      media_type: attachment.media_type,
      size: attachment.size,
    }))
}

export function contextOptions(contexts?: ChatContext[]) {
  const resourceRefs: Array<Record<string, unknown>> = []
  const skillIds: string[] = []
  for (const context of contexts ?? []) {
    switch (context.kind) {
      case 'file':
        resourceRefs.push({ type: 'file', id: context.fileId, label: context.label })
        break
      case 'file_selection':
        resourceRefs.push({
          type: 'file',
          id: context.fileId,
          label: context.label,
          selection: {
            text: context.text,
            fileName: context.fileName,
            ...(context.startLine !== undefined ? { startLine: context.startLine } : {}),
            ...(context.endLine !== undefined ? { endLine: context.endLine } : {}),
          },
        })
        break
      case 'table':
        resourceRefs.push({ type: 'table', id: context.tableId, label: context.label })
        break
      case 'table_selection':
        resourceRefs.push({
          type: 'table',
          id: context.tableId,
          label: context.label,
          selection: {
            tableName: context.tableName,
            rowIds: context.rowIds,
            ...(context.columnIds ? { columnIds: context.columnIds } : {}),
          },
        })
        break
      case 'knowledge':
        if (context.knowledgeId) {
          resourceRefs.push({ type: 'knowledge', id: context.knowledgeId, label: context.label })
        }
        break
      case 'past_chat':
        resourceRefs.push({ type: 'task', id: context.chatId, label: context.label })
        break
      case 'skill':
        skillIds.push(context.skillId)
        break
      default:
        break
    }
  }
  return {
    resourceRefs: resourceRefs.filter((ref) => typeof ref.id === 'string' && ref.id.length > 0),
    skillIds: [...new Set(skillIds)],
  }
}
