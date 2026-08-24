import type { ChatContext } from '@/stores/panel'
import type { MothershipResourceType } from './types'

export interface ContextResourceRef {
  type: MothershipResourceType
  id: string
}

export function resourceFromContext(context: ChatContext): ContextResourceRef | null {
  switch (context.kind) {
    case 'knowledge':
      return context.knowledgeId ? { type: 'knowledgebase', id: context.knowledgeId } : null
    case 'table':
    case 'table_selection':
      return context.tableId ? { type: 'table', id: context.tableId } : null
    case 'file':
    case 'file_selection':
      return context.fileId ? { type: 'file', id: context.fileId } : null
    default:
      return null
  }
}

export function resourceTitleFromContext(context: ChatContext): string {
  if (context.kind === 'file_selection') return context.fileName
  if (context.kind === 'table_selection') return context.tableName
  return context.label
}

export function isResourceReferencedByContexts(
  resource: ContextResourceRef,
  contexts: ChatContext[]
): boolean {
  return contexts.some((context) => {
    const candidate = resourceFromContext(context)
    return candidate?.type === resource.type && candidate.id === resource.id
  })
}
