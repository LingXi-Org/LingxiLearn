/**
 * Knowledge domain client.
 *
 * Owns knowledge base and document operations. Issue #40: extracted from
 * the God API object in ``lib/lingxi/api.ts``.
 */

import type { KnowledgeBaseItem, KnowledgeDocumentItem } from '@/lib/lingxi/types'
import { request } from '../transport'

export async function getKnowledgeBases() {
  const result = await request<{
    knowledgeBases?: KnowledgeBaseItem[]
    data?: KnowledgeBaseItem[]
  }>('/knowledge')
  const knowledgeBases = result.knowledgeBases ?? result.data ?? []
  return { knowledgeBases, data: knowledgeBases }
}

export function createKnowledgeBase(name: string, description = '') {
  return request<{ data: KnowledgeBaseItem; knowledgeBase: KnowledgeBaseItem }>('/knowledge', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  })
}

export async function getKnowledgeDocuments(baseId: string) {
  const result = await request<{
    documents?: KnowledgeDocumentItem[]
    data?: KnowledgeDocumentItem[] | { documents?: KnowledgeDocumentItem[] }
  }>(`/knowledge/${encodeURIComponent(baseId)}/documents`)
  const documents =
    result.documents ?? (Array.isArray(result.data) ? result.data : result.data?.documents) ?? []
  return { documents, data: documents }
}

export function createKnowledgeDocument(
  baseId: string,
  name: string,
  content: string,
  mimeType = 'text/plain'
) {
  return request<{ data: KnowledgeDocumentItem; document: KnowledgeDocumentItem }>(
    `/knowledge/${encodeURIComponent(baseId)}/documents`,
    { method: 'POST', body: JSON.stringify({ name, content, mimeType }) }
  )
}

export function updateKnowledgeDocument(
  baseId: string,
  documentId: string,
  content: string
) {
  return request<{ data: KnowledgeDocumentItem; document: KnowledgeDocumentItem }>(
    `/knowledge/${encodeURIComponent(baseId)}/documents/${encodeURIComponent(documentId)}`,
    { method: 'PATCH', body: JSON.stringify({ content }) }
  )
}
