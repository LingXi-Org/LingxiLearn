import { OrchestrationError } from '@/lib/core/orchestration/types'

export const ROOT_FOLDER_PATH = '/'
export const MAX_FOLDER_PATH_SEGMENTS = 64
export const MAX_FOLDER_PATH_BYTES = 4096

export class FolderPathError extends OrchestrationError {
  constructor(message: string) {
    super('validation', message)
    this.name = 'FolderPathError'
  }
}

const encodedByteLength = (value: string): number => new TextEncoder().encode(value).length

export function encodeFolderPathSegment(name: string): string {
  if (!name) throw new FolderPathError('Folder names cannot be empty')
  if (name === '.') return '%2E'
  if (name === '..') return '%2E%2E'
  try {
    return encodeURIComponent(name).replace(
      /[!'()*]/g,
      (character) => `%${character.charCodeAt(0).toString(16).toUpperCase()}`
    )
  } catch {
    throw new FolderPathError('Folder name contains invalid Unicode')
  }
}

export function buildFolderPath(segments: readonly string[]): string {
  if (segments.length === 0) return ROOT_FOLDER_PATH
  if (segments.length > MAX_FOLDER_PATH_SEGMENTS) {
    throw new FolderPathError(`Folder paths cannot exceed ${MAX_FOLDER_PATH_SEGMENTS} segments`)
  }
  const path = `/${segments.map(encodeFolderPathSegment).join('/')}`
  if (encodedByteLength(path) > MAX_FOLDER_PATH_BYTES) {
    throw new FolderPathError(`Folder paths cannot exceed ${MAX_FOLDER_PATH_BYTES} bytes`)
  }
  return path
}

export function parseFolderPath(path: string): string[] {
  if (path === ROOT_FOLDER_PATH) return []
  if (!path.startsWith('/') || path.endsWith('/') || path.includes('//')) {
    throw new FolderPathError('Path must be a canonical folder path')
  }
  if (encodedByteLength(path) > MAX_FOLDER_PATH_BYTES) {
    throw new FolderPathError(`Folder paths cannot exceed ${MAX_FOLDER_PATH_BYTES} bytes`)
  }
  const parts = path.slice(1).split('/')
  if (parts.length > MAX_FOLDER_PATH_SEGMENTS) {
    throw new FolderPathError(`Folder paths cannot exceed ${MAX_FOLDER_PATH_SEGMENTS} segments`)
  }
  return parts.map((part) => {
    let decoded: string
    try {
      decoded = decodeURIComponent(part)
    } catch {
      throw new FolderPathError('Path must be a canonical folder path')
    }
    if (encodeFolderPathSegment(decoded) !== part) {
      throw new FolderPathError('Path must be a canonical folder path')
    }
    return decoded
  })
}

export function requireNonRootFolderPath(path: string): string[] {
  const segments = parseFolderPath(path)
  if (!segments.length) throw new FolderPathError('The root path cannot be mutated')
  return segments
}

export const parentFolderPath = (path: string): string =>
  buildFolderPath(requireNonRootFolderPath(path).slice(0, -1))
export const folderNameFromPath = (path: string): string =>
  requireNonRootFolderPath(path).at(-1) as string
