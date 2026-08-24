import { describe, expect, it } from 'vitest'
import { PRODUCT_LOCALE, userFacingError, workspaceCopy } from '.'

describe('workspace product copy', () => {
  it('has a single explicit locale and non-empty resource copy', () => {
    expect(PRODUCT_LOCALE).toBe('zh-CN')
    for (const resource of [
      workspaceCopy.resources.files,
      workspaceCopy.resources.knowledge,
      workspaceCopy.resources.tables,
      workspaceCopy.resources.logs,
    ]) {
      expect(resource.title.length).toBeGreaterThan(0)
    }
  })

  it.each([
    [{ status: 403, message: 'SQL password leaked' }, 'permissionDenied'],
    [{ status: 404, detail: 'https://internal.example/trace' }, 'notFound'],
    [{ status: 413, message: 'stack trace' }, 'payloadTooLarge'],
    [{ status: 429, rawBody: 'secret' }, 'rateLimited'],
    [{ code: 'conflict', message: 'SELECT * FROM users' }, 'conflict'],
  ] as const)('maps stable error metadata without exposing technical text', (error, key) => {
    const result = userFacingError(error)
    expect(result).toBe(workspaceCopy.common.errors[key])
    expect(result).not.toContain('SQL')
    expect(result).not.toContain('http')
    expect(result).not.toContain('SELECT')
  })

  it('uses a caller-selected safe fallback for unknown errors', () => {
    expect(userFacingError(new Error('database password'), 'uploadFailed')).toBe(
      workspaceCopy.common.errors.uploadFailed
    )
  })
})
