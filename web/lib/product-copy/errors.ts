import { workspaceCopy } from './zh-cn'

export type WorkspaceErrorMessage = keyof typeof workspaceCopy.common.errors

interface StructuredError {
  status?: unknown
  code?: unknown
}

const CODE_MESSAGES: Readonly<Record<string, WorkspaceErrorMessage>> = {
  forbidden: 'permissionDenied',
  permission_denied: 'permissionDenied',
  not_found: 'notFound',
  conflict: 'conflict',
  payload_too_large: 'payloadTooLarge',
  rate_limited: 'rateLimited',
}

function structuredError(error: unknown): StructuredError | null {
  return error !== null && typeof error === 'object' ? (error as StructuredError) : null
}

export function userFacingError(
  error: unknown,
  fallback: WorkspaceErrorMessage = 'unexpected'
): string {
  const structured = structuredError(error)
  const code = typeof structured?.code === 'string' ? structured.code.toLowerCase() : null
  const mappedCode = code ? CODE_MESSAGES[code] : undefined
  if (mappedCode) return workspaceCopy.common.errors[mappedCode]

  const status = typeof structured?.status === 'number' ? structured.status : null
  if (status === 401 || status === 403) return workspaceCopy.common.errors.permissionDenied
  if (status === 404) return workspaceCopy.common.errors.notFound
  if (status === 409 || status === 423) return workspaceCopy.common.errors.conflict
  if (status === 413) return workspaceCopy.common.errors.payloadTooLarge
  if (status === 429) return workspaceCopy.common.errors.rateLimited
  if (status !== null && status >= 500) return workspaceCopy.common.errors.unexpected
  return workspaceCopy.common.errors[fallback]
}
