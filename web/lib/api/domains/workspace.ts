/**
 * Workspace domain client.
 *
 * Owns all workspace/files/folders/tables operations. Issue #40: extracted
 * from the God API object in ``lib/lingxi/api.ts``.
 */

import type {
  WorkspaceFileItem,
  WorkspaceFolderItem,
  WorkspaceTableItem,
} from '@/lib/lingxi/types'
import { request } from '../transport'
import { API_BASE } from '@/lib/api/config'

function normalizeWorkspaceFile(file: WorkspaceFileItem): WorkspaceFileItem {
  if (!file.url || !file.url.startsWith('/api/')) return file
  return { ...file, url: `${API_BASE}${file.url}` }
}

// ---------------------------------------------------------------------------
// Workspace metadata
// ---------------------------------------------------------------------------

export function getWorkspace() {
  return request<{ workspace: Record<string, unknown>; data: Record<string, unknown> }>(
    '/workspaces/lingxi'
  )
}

export function updateWorkspace(patch: { name?: string; appearance?: Record<string, unknown> }) {
  return request<{ workspace: Record<string, unknown>; data: Record<string, unknown> }>(
    '/workspaces/lingxi',
    { method: 'PATCH', body: JSON.stringify(patch) }
  )
}

// ---------------------------------------------------------------------------
// Folders
// ---------------------------------------------------------------------------

export function getWorkspaceFolders(scope: 'active' | 'archived' = 'active') {
  return request<{ folders: WorkspaceFolderItem[] }>(
    `/workspaces/lingxi/files/folders?scope=${scope}`
  )
}

export function createWorkspaceFolder(name: string, parentId?: string | null) {
  return request<{ folder: WorkspaceFolderItem }>('/workspaces/lingxi/files/folders', {
    method: 'POST',
    body: JSON.stringify({ name, parentId: parentId ?? null }),
  })
}

export function updateWorkspaceFolder(
  folderId: string,
  body: { name?: string; parentId?: string | null }
) {
  return request<{ folder: WorkspaceFolderItem }>(
    `/workspaces/lingxi/files/folders/${encodeURIComponent(folderId)}`,
    { method: 'PATCH', body: JSON.stringify(body) }
  )
}

export function archiveWorkspaceFolder(folderId: string) {
  return request<{ success: boolean }>(
    `/workspaces/lingxi/files/folders/${encodeURIComponent(folderId)}`,
    { method: 'DELETE' }
  )
}

export function restoreWorkspaceFolder(folderId: string) {
  return request<{ folder: WorkspaceFolderItem }>(
    `/workspaces/lingxi/files/folders/${encodeURIComponent(folderId)}/restore`,
    { method: 'POST' }
  )
}

export function moveWorkspaceItems(
  fileIds: string[],
  folderIds: string[],
  targetFolderId?: string | null
) {
  return request<{ movedItems: { files: number; folders: number } }>(
    '/workspaces/lingxi/files/move',
    {
      method: 'POST',
      body: JSON.stringify({ fileIds, folderIds, targetFolderId: targetFolderId ?? null }),
    }
  )
}

// ---------------------------------------------------------------------------
// Files
// ---------------------------------------------------------------------------

export async function getWorkspaceFiles(
  scope: 'active' | 'archived' = 'active',
  folderId?: string | null
) {
  const result = await request<{ files: WorkspaceFileItem[] }>(
    `/workspaces/lingxi/files?scope=${scope}${folderId ? `&folderId=${encodeURIComponent(folderId)}` : ''}`
  )
  return { ...result, files: result.files.map(normalizeWorkspaceFile) }
}

export async function createWorkspaceFile(
  name: string,
  content: string,
  type?: string,
  encoding?: 'utf-8' | 'base64',
  folderId?: string | null
) {
  const result = await request<{ file: WorkspaceFileItem }>('/workspaces/lingxi/files', {
    method: 'POST',
    body: JSON.stringify({
      name,
      content,
      type: type || 'text/plain',
      contentType: type || 'text/plain',
      encoding: encoding || 'utf-8',
      folderId: folderId ?? null,
    }),
  })
  return { ...result, file: normalizeWorkspaceFile(result.file) }
}

export async function getWorkspaceFile(fileId: string) {
  const result = await request<{ file: WorkspaceFileItem }>(
    `/workspaces/lingxi/files/${encodeURIComponent(fileId)}`
  )
  return { ...result, file: normalizeWorkspaceFile(result.file) }
}

export async function getWorkspaceFileContent(fileId: string) {
  const result = await request<{ content: string; encoding: string; file: WorkspaceFileItem }>(
    `/workspaces/lingxi/files/${encodeURIComponent(fileId)}/content`
  )
  return { ...result, file: normalizeWorkspaceFile(result.file) }
}

export function updateWorkspaceFileContent(fileId: string, content: string) {
  return request<{ file: WorkspaceFileItem }>(
    `/workspaces/lingxi/files/${encodeURIComponent(fileId)}/content`,
    { method: 'PUT', body: JSON.stringify({ content }) }
  )
}

export function archiveWorkspaceFile(fileId: string) {
  return request<{ success: boolean }>(
    `/workspaces/lingxi/files/${encodeURIComponent(fileId)}`,
    { method: 'DELETE' }
  )
}

// ---------------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------------

export function getWorkspaceTables() {
  return request<{ tables: WorkspaceTableItem[]; data: unknown }>('/table?workspaceId=lingxi')
}

export function createWorkspaceTable(
  name: string,
  columns = [{ name: '内容', type: 'string' }]
) {
  return request<{ data: { table: WorkspaceTableItem } }>('/table', {
    method: 'POST',
    body: JSON.stringify({ workspaceId: 'lingxi', name, schema: { columns } }),
  })
}

export function getWorkspaceTable(tableId: string) {
  return request<{ data: { table: WorkspaceTableItem } }>(
    `/table/${encodeURIComponent(tableId)}?workspaceId=lingxi`
  )
}

export function getWorkspaceTableRows(tableId: string) {
  return request<{ data: { rows: Array<Record<string, unknown>>; totalCount: number } }>(
    `/table/${encodeURIComponent(tableId)}/rows`
  )
}

export function createWorkspaceRows(tableId: string, rows: Array<Record<string, unknown>>) {
  return request<{ data: { rows: Array<Record<string, unknown>> } }>(
    `/table/${encodeURIComponent(tableId)}/rows`,
    { method: 'POST', body: JSON.stringify({ rows }) }
  )
}

export function updateWorkspaceRow(tableId: string, rowId: string, data: Record<string, unknown>) {
  return request<{ data: { row: Record<string, unknown> } }>(
    `/table/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}`,
    { method: 'PATCH', body: JSON.stringify({ data }) }
  )
}
