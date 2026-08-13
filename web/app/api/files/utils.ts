import { createLogger } from '@sim/logger'
import { sanitizeFileKey } from '@/lib/uploads/utils/file-utils'

const logger = createLogger('FilesUtils')

export const contentTypeMap: Record<string, string> = {
  txt: 'text/plain',
  csv: 'text/csv',
  json: 'application/json',
  xml: 'application/xml',
  md: 'text/markdown',
  html: 'text/html',
  css: 'text/css',
  js: 'application/javascript',
  ts: 'application/typescript',
  pdf: 'application/pdf',
  doc: 'application/msword',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  xls: 'application/vnd.ms-excel',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  ppt: 'application/vnd.ms-powerpoint',
  pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  svg: 'image/svg+xml',
  webp: 'image/webp',
  avif: 'image/avif',
  ico: 'image/x-icon',
  mp3: 'audio/mpeg',
  m4a: 'audio/mp4',
  wav: 'audio/wav',
  ogg: 'audio/ogg',
  mp4: 'video/mp4',
  mov: 'video/quicktime',
  webm: 'video/webm',
  zip: 'application/zip',
}

export function getContentType(filename: string): string {
  const extension = filename.split('.').pop()?.toLowerCase() || ''
  return contentTypeMap[extension] || 'application/octet-stream'
}

export function encodeFilenameForHeader(storageKey: string): string {
  const filename = storageKey.split('/').pop() || storageKey
  const asciiSafe = filename.replace(/[^\x20-\x7E]/g, '_').replace(/["\\;]/g, '_')
  if (asciiSafe === filename) return `filename="${filename}"`
  return `filename="${asciiSafe}"; filename*=UTF-8''${encodeURIComponent(filename)}`
}

export function getSecureFileHeaders(filename: string, originalContentType: string) {
  const extension = filename.split('.').pop()?.toLowerCase() || ''
  if (['html', 'htm', 'js', 'css', 'xml'].includes(extension)) {
    return { contentType: 'application/octet-stream', disposition: 'attachment' }
  }
  const safeContentType = originalContentType === 'text/html' ? 'text/plain' : originalContentType
  const inlineTypes = new Set([
    'image/png',
    'image/jpeg',
    'image/gif',
    'image/svg+xml',
    'image/webp',
    'image/avif',
    'image/x-icon',
    'application/pdf',
    'text/plain',
    'text/csv',
    'application/json',
  ])
  return {
    contentType: safeContentType,
    disposition: inlineTypes.has(safeContentType) ? 'inline' : 'attachment',
  }
}

export async function findLocalFile(filename: string): Promise<string | null> {
  try {
    const sanitizedFilename = sanitizeFileKey(filename)
    if (!sanitizedFilename) return null
    const { existsSync } = await import('fs')
    const path = await import('path')
    const { UPLOAD_DIR_SERVER } = await import('@/lib/uploads/core/setup.server')
    const resolvedPath = path.join(UPLOAD_DIR_SERVER, sanitizedFilename)
    if (
      !resolvedPath.startsWith(`${UPLOAD_DIR_SERVER}${path.sep}`) ||
      existsSync(resolvedPath) === false
    ) {
      return null
    }
    return resolvedPath
  } catch (error) {
    logger.error('Error in findLocalFile:', error)
    return null
  }
}
